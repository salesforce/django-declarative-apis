#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import abc
import collections.abc
import inspect
import random
import string
import time

from django.db import models as django_models

from . import errors
from . import tasks


class EndpointAttribute(metaclass=abc.ABCMeta):
    _next_attribute_number = 0

    @classmethod
    def claim_attribute_number(cls):
        next_serial_number = cls._next_attribute_number
        cls._next_attribute_number += 1
        return next_serial_number

    def __init__(
        self, name=None, required=False, description=None, hidden=False, advanced=False
    ):
        super(EndpointAttribute, self).__init__()

        self.hidden = hidden
        self.name = name  # will be populated by EndpointDefinitionMeta
        self.advanced = advanced
        self.required = required
        self.description = description
        self.attribute_number = EndpointAttribute.claim_attribute_number()

    def __get__(self, owner_instance, owner_class):
        if not owner_instance:
            # If accessed from the class, return the EndpointAttribute itself
            return self

        if not self.name:
            raise ValueError(
                "All EndpointAttribute objects must have a name before they can be accessed "
                "from an instance"
            )

        # The instance dictionary is used as a cache
        if self.name in owner_instance.__dict__:
            return owner_instance.__dict__[self.name]

        # Delegate to _get_value_for_instance and cache the result within the instance's dict
        value = self.get_instance_value(owner_instance, owner_class)
        owner_instance.__dict__[self.name] = value
        return value

    @abc.abstractmethod
    def get_instance_value(self, owner_instance, owner_class):
        raise NotImplementedError()


class RequestProperty(EndpointAttribute):
    __hidden_request_attribute_name = "_" + "".join(
        random.choice(string.printable) for _ in range(10)
    )

    @classmethod
    def bind_request_to_instance(cls, instance, request):
        # Hide the request within the instance
        setattr(instance, cls.__hidden_request_attribute_name, request)

    @classmethod
    def request_has_been_bound(cls, instance):
        return cls.__hidden_request_attribute_name in instance.__dict__

    def __init__(self, property_getter, **kwargs):
        super(RequestProperty, self).__init__(**kwargs)

        self.property_getter = property_getter

        # Capture the hidden attribute name within each RequestProperty instance, so lookups work through being pickled
        self.__hidden_request_attribute_name = (
            RequestProperty.__hidden_request_attribute_name
        )

    def __extract_request_from_instance(self, instance):
        return getattr(instance, self.__hidden_request_attribute_name, None)

    def get_instance_value(self, owner_instance, owner_class):
        request = self.__extract_request_from_instance(owner_instance)
        if not request:
            raise ValueError(
                "A request must be bound with the instance before accessing this property"
            )

        return self.property_getter(owner_instance, request)

    @property
    def documentation(self):
        result = {"name": self.name}
        if self.description is not None:
            result["description"] = self.description
        return result


class TypedEndpointAttributeMixin(object):
    def __init__(self, *args, **kwargs):
        self.field_type = kwargs.pop("type", str)
        if self.field_type not in RequestField.VALID_FIELD_TYPES:
            raise NotImplementedError(
                "Request fields of type {0} not supported".format(
                    self.field_type.__name__
                )
            )
        super(TypedEndpointAttributeMixin, self).__init__(*args, **kwargs)

    def coerce_value_to_type(self, raw_value):
        try:
            if self.field_type == bool and not isinstance(raw_value, self.field_type):
                return "rue" in raw_value
            else:
                if isinstance(raw_value, collections.abc.Iterable) and not isinstance(
                    raw_value, (str, dict)
                ):
                    return list(self.field_type(r) for r in raw_value)
                else:
                    return self.field_type(raw_value)
        except Exception as e:  # noqa
            raise errors.ClientErrorInvalidFieldValues(
                [self.name],
                "Could not parse {val} as type {type}".format(
                    val=raw_value, type=self.field_type.__name__
                ),
            )


class RequestUrlField(TypedEndpointAttributeMixin, EndpointAttribute):
    def __init__(self, *args, **kwargs):
        self.api_name = kwargs.pop("name", None)
        self.value = None
        super(RequestUrlField, self).__init__(*args, **kwargs)

    def set_value(self, value):
        self.value = value

    def get_instance_value(self, owner_instance, owner_class):
        return self.coerce_value_to_type(self.value)


class RequestAdhocQuerySet(RequestUrlField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type=dict, **kwargs)
        self.value = {}


class RequestField(TypedEndpointAttributeMixin, RequestProperty):
    VALID_FIELD_TYPES = (bool, int, float, complex, str, dict)

    def __init__(self, *args, **kwargs):
        self.default_value = kwargs.pop("default", None)
        self.api_name = kwargs.pop("name", None)
        self.multivalued = kwargs.pop("multivalued", False)
        super(RequestField, self).__init__(property_getter=self.get_field, **kwargs)
        self.post_processor = None

    def __call__(self, post_processor):
        self.post_processor = post_processor
        return self

    @property
    def documentation(self):
        result = super(RequestField, self).documentation
        result["type"] = self.field_type
        result["multivalued"] = self.multivalued
        if self.api_name:
            result["name"] = self.api_name
        if self.default_value is not None:
            result["default_value"] = self.default_value
        return result

    def get_without_default(self, owner_instance, request):
        if request.method == "POST":
            query_dict = request.POST
        else:
            query_dict = request.GET

        if (self.api_name or self.name) in query_dict:
            if not self.multivalued:
                raw_value = query_dict.get(self.api_name or self.name)
            else:
                raw_value = query_dict.getlist(self.api_name or self.name)
            typed_value = self.coerce_value_to_type(raw_value)
        else:
            typed_value = None

        if self.post_processor:
            return self.post_processor(owner_instance, typed_value)
        else:
            return typed_value

    def get_field(self, owner_instance, request):
        raw_value = self.get_without_default(owner_instance, request)
        if raw_value is not None:
            return raw_value
        else:
            return self.default_value


class ResourceField(RequestField):
    pass


class RequestAttribute(RequestProperty):
    def __init__(self, attribute_getter=None, required=True, default=None, **kwargs):
        super(RequestAttribute, self).__init__(
            property_getter=self.get_request_attribute, required=required, **kwargs
        )

        self.attribute_getter = attribute_getter
        self.default = default

    # Facilitated use as a decorator with arguments
    def __call__(self, attribute_getter):
        self.attribute_getter = attribute_getter
        return self

    def get_without_default(self, owner_instance, request):
        if self.attribute_getter:
            result = self.attribute_getter(owner_instance, request)
        else:
            result = getattr(request, self.name, None)
        return result

    def get_request_attribute(self, owner_instance, request):
        result = self.get_without_default(owner_instance, request)
        if result is not None:
            return result
        else:
            return self.default


class ConsumerAttribute(RequestAttribute):
    def __init__(self, *args, field_name=None, **kwargs):
        self.field_name = field_name
        super(ConsumerAttribute, self).__init__(*args, **kwargs)

    def get_without_default(self, owner_instance, request):
        consumer = request.consumer
        if self.attribute_getter:
            return self.attribute_getter(owner_instance, consumer)
        else:
            return getattr(consumer, self.field_name or self.name, None)


class RawRequestObjectProperty(RequestAttribute):
    class SafeRequestWrapper(object):
        __hidden_request_attribute_name = "_" + "".join(
            random.choice(string.printable) for _ in range(10)
        )
        __permitted_request_properties = ("build_absolute_uri", "method", "META")

        def __init__(self, request, additional_safe_fields=()):
            setattr(self, self.__hidden_request_attribute_name, request)
            self.additional_safe_fields = additional_safe_fields

        @property
        def body_field_names(self):
            return set(getattr(self, self.__hidden_request_attribute_name).POST.keys())

        def __getattr__(self, name):
            if (
                name
                in RawRequestObjectProperty.SafeRequestWrapper.__permitted_request_properties
                or name in self.additional_safe_fields
            ):
                hidden_request = getattr(self, self.__hidden_request_attribute_name)
                return getattr(hidden_request, name)
            else:
                raise AttributeError()

    def __init__(self, *args, additional_safe_fields=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.additional_safe_fields = additional_safe_fields

    def get_without_default(self, owner_instance, request):
        return RawRequestObjectProperty.SafeRequestWrapper(
            request, additional_safe_fields=self.additional_safe_fields
        )


class EndpointTask(EndpointAttribute):
    STATE_NOT_RUN = 0
    STATE_RUNNING = 1
    STATE_COMPLETED = 2

    def __init__(
        self,
        task_runner=None,
        depends_on=None,  # Reference to another task that should be run before this one.  Overrides priority
        priority=0,  # lower priority gets executed first
        **kwargs
    ):
        super(EndpointTask, self).__init__(**kwargs)
        self.task_runner = task_runner
        self.depends_on = depends_on
        self.task_state = EndpointTask.STATE_NOT_RUN
        self.priority = priority

    def __call__(self, task_runner):
        self.task_runner = task_runner
        return self

    def _run_task(self, owner_instance):
        self.task_runner(owner_instance)

    def run(self, owner_instance):
        assert (
            self.task_state != EndpointTask.STATE_RUNNING
        ), "Circular task reference detected!"
        try:
            self.task_state = EndpointTask.STATE_RUNNING

            depends_on = self.depends_on
            if isinstance(depends_on, str):
                depends_on = getattr(owner_instance, depends_on)

            if depends_on and (depends_on.task_state != EndpointTask.STATE_COMPLETED):
                assert not isinstance(
                    depends_on, DeferrableEndpointTask
                ), "DeferredEndpointTask cannot be used as depends_on arg"
                depends_on.run(owner_instance)

            self._run_task(owner_instance)

        finally:
            self.task_state = EndpointTask.STATE_COMPLETED

    def get_instance_value(self, owner_instance, owner_class):
        return self


class DeferrableEndpointTask(EndpointTask):
    @staticmethod
    def unwrap_staticmethod(method):
        assert isinstance(method, staticmethod), (
            "Deferrable task methods MUST be staticmethods.  Hint: the staticmethod "
            "decorator should come after the deferrable task decorator "
        )
        # we're effectively unwrapping the staticmethod here...
        return method.__func__

    def __init__(
        self,
        task_runner=None,
        delay=None,  # delay in seconds before running the task.  Requires deferred=True
        always_defer=True,  # True: run task in deferred queue even when delay=0
        task_args_factory=None,
        queue=None,
        routing_key=None,
        retries=0,
        retry_exception_filter=(),
        execute_unless=None,
        **kwargs
    ):
        super(DeferrableEndpointTask, self).__init__(**kwargs)
        if task_runner:
            self.task_runner = DeferrableEndpointTask.unwrap_staticmethod(task_runner)
        else:
            self.task_runner = None

        self.delay = delay
        self.always_defer = always_defer
        self.queue = queue
        self.routing_key = routing_key
        self.retries = retries
        self.retry_exception_filter = retry_exception_filter

        if execute_unless:
            assert callable(execute_unless), "execute_unless MUST be callable"
            assert inspect.getfullargspec(execute_unless).args == [
                "self"
            ], "execute_unless MUST be an instance method that takes only the 'self' argument"

        self.execute_unless = execute_unless

        assert task_args_factory is None or callable(task_args_factory)
        self.task_args_factory = task_args_factory

    def __call__(self, task_runner):
        self.task_runner = DeferrableEndpointTask.unwrap_staticmethod(task_runner)
        return self

    def _resolve_maybe_callable(self, owner_instance, maybe_callable):
        if callable(maybe_callable):
            return maybe_callable(owner_instance)
        else:
            return maybe_callable

    def _run_task(self, owner_instance):
        if self.execute_unless and self.execute_unless(owner_instance):
            return

        resource = owner_instance.resource

        assert isinstance(
            resource, django_models.Model
        ), "resource must be an instance of django.db.models.Model to run as deferred task"

        delay = self._resolve_maybe_callable(owner_instance, self.delay) or 0
        always_defer = self._resolve_maybe_callable(owner_instance, self.always_defer)

        if self.task_args_factory:
            task_args, task_kwargs = self.task_args_factory(owner_instance)
        else:
            task_args, task_kwargs = [], {}

        if delay == 0 and not always_defer:
            self.task_runner(*([resource] + list(task_args)), **task_kwargs)
        else:
            if resource.pk is None:
                resource.save()
            resource_id = resource.pk
            resource_class_name = "{0}.{1}".format(
                resource.__module__, resource.__class__.__name__
            )
            endpoint_class_name = "{0}.{1}".format(
                owner_instance.__module__, owner_instance.__class__.__name__
            )
            task_runner_args = (
                endpoint_class_name,
                self.task_runner.__name__,
                resource_class_name,
                str(resource_id),
            )
            task_runner_kwargs = {
                "task_creation_time": time.time(),
                "scheduled_execution_delay": delay,
                "task_args": (task_args, task_kwargs),
            }
            tasks.schedule_future_task_runner(
                task_runner_args,
                task_runner_kwargs,
                retries=self.retries,
                retry_exception_filter=self.retry_exception_filter,
                delay=delay,
                queue=self.queue,
                routing_key=self.routing_key,
            )


class RequestFieldGroup(RequestProperty):
    def __init__(self, *component_field_getters, **kwargs):
        super(RequestFieldGroup, self).__init__(
            property_getter=self.get_value, **kwargs
        )
        self.component_field_getters = component_field_getters
        self.component_field_names = []
        for component_field_getter in self.component_field_getters:
            component_field_getter.required = False

    def __call__(self, *component_field_getters):
        self.component_field_getters = component_field_getters
        return self

    def _get_request_dict(self, request):
        if request.method == "GET":
            return request.GET
        elif request.method == "POST":
            return request.POST
        else:
            return {}

    def _get_missing_component_fields(self, owner_instance, request):
        self.component_field_names = map(lambda x: x.name, self.component_field_getters)
        request_dict = self._get_request_dict(request)
        missing_fields = []
        for getter in self.component_field_getters:
            result = getter.get_without_default(owner_instance, request)
            if result is None:
                missing_fields.append(getter.name)
        return missing_fields


class RequireOneAttribute(RequestFieldGroup):
    def get_value(self, owner_instance, request):
        missing_fields = self._get_missing_component_fields(owner_instance, request)

        # all but one field should be missing from the request
        if len(self.component_field_getters) - len(missing_fields) == 1:
            return True
        else:
            raise errors.ClientErrorMissingFields(
                self.component_field_names,
                extra_message="Exactly one field must be populated",
            )


class RequireAllAttribute(RequestFieldGroup):
    def get_value(self, owner_instance, request):
        missing_fields = self._get_missing_component_fields(owner_instance, request)

        # no fields should be missing from the request
        if len(missing_fields) == 0:
            return True
        else:
            raise errors.ClientErrorMissingFields(
                self.component_field_names, extra_message="All fields must be populated"
            )


class RequireAllIfAnyAttribute(RequestFieldGroup):
    def get_value(self, owner_instance, request):
        missing_fields = self._get_missing_component_fields(owner_instance, request)

        # either all present or all missing
        if (len(missing_fields) == 0) or (
            len(missing_fields) == len(self.component_field_getters)
        ):
            return True
        else:
            raise errors.ClientErrorMissingFields(
                self.component_field_names, extra_message="All fields must be populated"
            )


class Aggregate(EndpointAttribute):
    def __init__(self, aggregation_function=None, **kwargs):
        self.aggregation_function = aggregation_function
        self.depends_on = kwargs.pop("depends_on", None)
        super(Aggregate, self).__init__(**kwargs)

    def __call__(self, aggregation_function):
        self.aggregation_function = aggregation_function
        return self

    def get_instance_value(self, owner_instance, owner_class):
        if not RequestProperty.request_has_been_bound(owner_instance):
            raise Exception(
                "Request must be bound to endpoint before accessing aggregate values"
            )

        return self.aggregation_function(owner_instance)
