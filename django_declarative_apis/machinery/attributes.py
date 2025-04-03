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
import pydantic
import logging

from . import errors
from . import tasks

logger = logging.getLogger(__name__)


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
        super().__init__()

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
        super().__init__(**kwargs)

        self.property_getter = property_getter

        # Capture the hidden attribute name within each RequestProperty
        # instance, so lookups work through being pickled
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


class TypedEndpointAttributeMixin:
    def __init__(self, *args, **kwargs):
        self.field_type = kwargs.pop("type", str)
        if not any(
            issubclass(self.field_type, t) for t in RequestField.VALID_FIELD_TYPES
        ):
            raise NotImplementedError(
                "Request fields of type {0} not supported".format(
                    self.field_type.__name__
                )
            )
        super().__init__(*args, **kwargs)

    def coerce_value_to_type(self, raw_value):
        """Coerce a raw value to the expected field type.

        Args:
            raw_value: The value to coerce

        Returns:
            The coerced value of the expected type

        Raises:
            ClientErrorInvalidFieldValues: If the value cannot be coerced to the expected type
        """
        # handle tricksy quickly right off the bat
        if raw_value is None:
            return None

        try:
            if self.field_type == bool:
                if isinstance(raw_value, bool):
                    return raw_value
                if isinstance(raw_value, str):
                    return raw_value.lower() in ("true", "1", "yes", "on")
                # handle ints and floats too
                if isinstance(raw_value, (int, float)):
                    return bool(raw_value)
                raise ValueError(f"Cannot convert {raw_value} to boolean")

            if issubclass(self.field_type, pydantic.BaseModel):
                return self.field_type.parse_obj(raw_value)

            if isinstance(raw_value, collections.abc.Iterable) and not isinstance(
                raw_value, (str, dict)
            ):
                return list(self.field_type(r) for r in raw_value)

            return self.field_type(raw_value)
        except Exception as e:
            name = self.name or self.api_name
            logger.info(
                'ev=dda, loc=coerce_value_to_type, name=%s, raw="%s", error="%s"',
                name,
                raw_value,
                e,
            )
            raise errors.ClientErrorInvalidFieldValues(
                [name],
                "Could not parse {val} as type {type}".format(
                    val=raw_value,
                    type=self.field_type.__name__,
                ),
            )


class RequestUrlField(TypedEndpointAttributeMixin, EndpointAttribute):
    """A specialized type of field that takes any parameter that directly appears in the
    URL path.

    :param name: Allows the name of the field in HTTP API to be different from its name
        defined on the EndpointDefinition. Defaults to :code:`None`
    :type name: optional

    **Example:**
    URL defined in :code:`urls.py`

    .. code-block:: python

        url_patterns = [
            url(
                r"^tasks/(?P<id>{0})/$".format(r"[0-9]{1}"),
                handlers.TodoDetailEndpoint,
                )
        ]

    :code:`url_field` is used to extract the id of a single task from the above URL for
    deleting that task.

    .. code-block:: python

        from django_declarative_apis.machinery import url_field

        class TodoDeleteSingleTaskDefinition(
            TodoResourceMixin,
            machinery.ResourceEndpointDefinition,
        ):
            resource_id = url_field(name='id')

            @endpoint_resource(type=Todo)
            def resource(self):
                task = Todo.objects.delete(id=self.resource_id)
                return django.http.HttpResponse(status=http.HTTPStatus.OK)
    """

    def __init__(self, *args, **kwargs):
        self.api_name = kwargs.pop("name", None)
        self.value = None
        super().__init__(*args, **kwargs)

    def set_value(self, value):
        self.value = value

    def get_instance_value(self, owner_instance, owner_class):
        return self.coerce_value_to_type(self.value)


class RequestAdhocQuerySet(RequestUrlField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, type=dict, **kwargs)
        self.value = {}


class RequestField(TypedEndpointAttributeMixin, RequestProperty):
    """Endpoint properties are called fields. Fields can be simple types such as int,
    or they can be used as a decorator on a function.

    **Valid field types:** A subclass of :code:`int`, :code:`bool`, :code:`float`,
    :code:`str`, :code:`dict`, :code:`complex`, :code:`pydantic.BaseModel`

    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import field

        task = field(required=True, type=str)


    :param required: Determines whether the field is required for the
        EndpointDefinition. Defaults to :code:`False`.
    :type required: optional

    :param name: Allows the name of the field in HTTP API to be different from its name
        defined on the EndpointDefinition. Defaults to :code:`None`.
    :type name: optional

    :param type: Determines the type of the field. Type needs to be on of the *valid
        field types* listed above. Defaults to :code:`String`
    :type type: optional

    :param default: Sets the default value for the field. Defaults to :code:`None`.
    :type default: optional

    :param description: Describes the purpose of the field. Defaults to :code:`None`.
    :type description: optional

    :param multivalued: Allows a field to be specified multiple times in the request.
        With multivalued set to True, the EndpointHandler will receive a list of values
        instead of a single value. Defaults to :code:`False`.
    :type multivalued: optional

    **Example**

    Request:

    .. code-block::

        GET https://example.com?foo=bar1&foo=bar2

    EndpointDefinition:

    .. code-block:: python

        from django_declarative_apis.machinery import field

        class FooDefinition(EndpointDefinition):
            foo = field(multivalued=True)

    In the :code:`EndpointDefinition`, :code:`self.foo` would be equal to ['bar1',
    'bar2']

    """

    VALID_FIELD_TYPES = (bool, int, float, complex, str, dict, pydantic.BaseModel)

    def __init__(self, *args, **kwargs):
        self.default_value = kwargs.pop("default", None)
        self.api_name = kwargs.pop("name", None)
        self.multivalued = kwargs.pop("multivalued", False)
        super().__init__(property_getter=self.get_field, **kwargs)
        self.post_processor = None

    def __call__(self, post_processor):
        self.post_processor = post_processor
        return self

    @property
    def documentation(self):
        result = super().documentation
        result["type"] = self.field_type
        result["multivalued"] = self.multivalued
        if self.api_name:
            result["name"] = self.api_name
        if self.default_value is not None:
            result["default_value"] = self.default_value
        return result

    def get_without_default(self, owner_instance, request):
        """Get the field value from the request without applying default value.

        Args:
            owner_instance: The instance of the endpoint definition
            request: The Django request object

        Returns:
            The coerced value of the field, or None if not found
        """
        if not request:
            return None

        query_dict = request.POST if request.method == "POST" else request.GET
        # handle errors during MIME type translation or data deserialization
        if not query_dict:
            return None

        field_name = self.api_name or self.name
        if not field_name:
            return None

        if field_name in query_dict:
            if not self.multivalued:
                raw_value = query_dict.get(field_name)
            else:
                raw_value = query_dict.getlist(field_name)
            typed_value = self.coerce_value_to_type(raw_value)
        else:
            typed_value = None

        if self.post_processor:
            return self.post_processor(owner_instance, typed_value)

        return typed_value

    def get_field(self, owner_instance, request):
        raw_value = self.get_without_default(owner_instance, request)
        if raw_value is not None:
            return raw_value
        return self.default_value


class ResourceField(RequestField):
    pass


class RequestAttribute(RequestProperty):
    """Used to initialize a consumer object for an endpoint definition.

    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import request_attribute

        consumer = request_attribute()
    """

    def __init__(self, attribute_getter=None, required=True, default=None, **kwargs):
        super().__init__(
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
    """Creates a requester/authenticator object for an endpoint definition.

    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import consumer_attribute

        requester = consumer_attribute()
    """

    def __init__(self, *args, field_name=None, **kwargs):
        self.field_name = field_name
        super().__init__(*args, **kwargs)

    def get_without_default(self, owner_instance, request):
        consumer = request.consumer
        if self.attribute_getter:
            return self.attribute_getter(owner_instance, consumer)
        else:
            return getattr(consumer, self.field_name or self.name, None)


class RawRequestObjectProperty(RequestAttribute):
    """Creates a request object for an endpoint definition.

    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import RawRequestObjectProperty

        request = RawRequestObjectProperty()
    """

    class SafeRequestWrapper:
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
    """:code:`task` is used as a decorator on a function. It encapsulate the side-effect
    operations of an endpoint. For instance, if hitting an endpoint causes an operation
    to happen in another resource or it causes an operation to be queued and run as a
    background task.

    :code:`task` runs **synchronously**, which means it will be executed before the
    response is returned to the user. It can also affect the response by making changes
    to the :code:`EndpointDefinition.resource()`.


    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import task

        class SampleClass:
            # code

            @task
            def sample_function():
                # your code goes here



    :param task_runner: A callable that dictates how the task is executed. Defaults to
        :code:`None`.
    :type task_runner: optional

    :param depends_on: A reference to another task that should be run before this one.
        Overrides :code:`priority`. Defaults to :code:`None`. It is important to note
        that :code:`deferrable_task` cannot be used as a :code:`depends_on` argument.
    :type depends_on: optional

    :param priority: Specifies the priority of the task. Tasks with lower priority are
        executed first. Defaults to :code:`0`.
    :type priority: optional

    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import task

        class SampleEndpointDefinition:
           def is_authorized(self):
             return True

           @task
           def set_response_filter(self):
                self.response._api_filter = filters.SampleFilters
    """

    STATE_NOT_RUN = 0
    STATE_RUNNING = 1
    STATE_COMPLETED = 2

    def __init__(
        self,
        task_runner=None,
        depends_on=None,  # Reference to another task that should be run before this one. Overrides priority
        priority=0,  # lower priority gets executed first
        **kwargs,
    ):
        super().__init__(**kwargs)
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
    """:code:`deferrable_task` is used as a decorator on a function. It is similar to
    :code:`task` in that it encapsulates side-effects, but can be automatically executed
    in a deferred queue outside of the request-response cycle.

    :code:`deferrable_task` runs **asynchronously** and because of that it is used for
    operations that take time and when we want to avoid delaying the response to the
    user.

    **Deferrable Task Rules**:

    * Deferrable task methods must always be a :code:`staticmethod`. Therefore, anything
      a deferrable task needs to know should be saved in the
      :code:`EndpointDefinition.resource()`.

    * The :code:`staticmethod` decorator should come after :code:`deferrable_task`
      decorator.

        .. code-block:: python

          from django_declarative_apis.machinery import deferrable_task

          class SampleClass:
            # code

            @deferrable_task
            @staticmethod
            def sample_method(arg):
               # your code goes here

    * Works only with a Django Model instance as the resource


    .. note:: Depending on the parameters used, a deferrable task can be run in
        different time intervals. In some cases, it can be made to run synchronously.

    :param task_runner: A callable that dictates how the task is executed. Defaults to
        :code:`None`.
    :type task_runner: optional

    :param delay: Sets the delay in seconds before running the task. Requires
        :code:`always_defer=True.` Defaults to :code:`None`.
    :type delay: optional

    :param always_defer: Runs task in deferred queue even when :code:`delay=0.` Defaults
        to :code:`False`.
    :type always_defer: optional

    :param task_args_factory: Stores task args and kwargs. :code:`task_args_factory`
        must be a **callable**. Defaults to :code:`None`.
    :type task_args_factory: optional

    :param queue: Sets the celery queue that will be used for storing the tasks.
        Defaults to :code:`None`.
    :type queue: optional

    :param routing_key: It is used to determine which queue the task should be routed
        to. Defaults to :code:`None`.
    :type routing_key: optional

    :param retries: Specifies the number of times the current task has been retried.
        Defaults to :code:`0`
    :type retries: optional

    :param retry_exception_filter: It is used to store retry exception information that
        is used in logs. Defaults to :code:`()` - empty tuple.
    :type retry_exception_filter: optional

    :param execute_unless: Execute the task unless a condition is met.It must be a
        **callable**. Defaults to  :code:`None`.
    :type execute_unless: optional

    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import deferrable_task

        class SampleClass:
            # code

            @deferrable_task(execute_unless=<condition>)
            @staticmethod
            def sample_method(arg):
                # your code goes here

    """

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
        **kwargs,
    ):
        super().__init__(**kwargs)
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
            assert (
                inspect.getfullargspec(execute_unless).args == ["self"]
            ), "execute_unless MUST be an instance method that takes only the 'self' argument"

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


class DeferrableGenericEndpointTask(DeferrableEndpointTask):
    # very similar to DeferrableEndpointTask, but doesn't assume that the resource is a Django model instance

    def __init__(
        self,
        task_args_packer=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        assert (
            task_args_packer is not None
        ), "task_args_packer required for DeferrableGenericEndpointTask"
        self.task_args_packer = task_args_packer

    def _run_task(self, owner_instance):
        if self.execute_unless and self.execute_unless(owner_instance):
            return

        delay = self._resolve_maybe_callable(owner_instance, self.delay) or 0
        always_defer = self._resolve_maybe_callable(owner_instance, self.always_defer)
        packed_args = self.task_args_packer.pack(owner_instance)

        if delay == 0 and not always_defer:
            unpacked_args, unpacked_kwargs = self.task_args_packer.unpack(packed_args)
            self.task_runner(*unpacked_args, **unpacked_kwargs)
        else:
            packer_name = "{0}.{1}".format(
                self.task_args_packer.__module__, self.task_args_packer.__name__
            )

            endpoint_class_name = "{0}.{1}".format(
                owner_instance.__module__, owner_instance.__class__.__name__
            )
            task_runner_args = (
                endpoint_class_name,
                self.task_runner.__name__,
                packed_args,
                packer_name,
            )
            task_runner_kwargs = {
                "task_creation_time": time.time(),
                "scheduled_execution_delay": delay,
            }
            tasks.schedule_generic_future_task_runner(
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
        super().__init__(property_getter=self.get_value, **kwargs)
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
        missing_fields = []
        for getter in self.component_field_getters:
            result = getter.get_without_default(owner_instance, request)
            if result is None:
                missing_fields.append(getter.name)
        return missing_fields


class RequireOneAttribute(RequestFieldGroup):
    """Exactly one of the given fields must be present.

    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import require_one

        sample_field_1 = field()
        sample_field_2 = field()

        sample_require_one = require_one(
                sample_field_1,
                sample_field_2,
            )
    """

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
    """All fields must be populated."""

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
    """Either all fields must be present or all fields must be missing."""

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
    """DDA uses aggregates to perform memoization to avoid repeated calculations,
    querying, or any task that can be performed once and the result cached. Aggregates
    retrieve or create a related object based on one or more field that is in use in the
    EndpointDefinition. An aggregate is calculated only once and then the data is cached
    for future retrieval.

    **Aggregates are used as decorators on functions.**

    .. code-block:: python

        from django_declarative_apis.machinery import aggregate

        class SampleClass:
            # code

            @aggregate
            def sample_function():
                # code

    :param required: Defines whether the aggregate is required or not. Defaults to
        :code:`False`.
    :type required: optional

    :param depends_on: Reference to another aggregate that should be run before this
        aggregate. Defaults to :code:`None`.
    :type depends_on: optional

    **Example:**
    We want to query a user only once and cache that information for future use.

    .. code-block:: python

        from django_declarative_apis.machinery import aggregate

        class SampleClass:
            user_id = url_field()

            @aggregate(required=True)
            def get_user(self):
                try:
                    user = models.User.objects.get(id=self.user_id)
                except:
                    raise Exception("User with matching id not found")
                return user
    """

    def __init__(self, aggregation_function=None, **kwargs):
        self.aggregation_function = aggregation_function
        self.depends_on = kwargs.pop("depends_on", None)
        super().__init__(**kwargs)

    def __call__(self, aggregation_function):
        self.aggregation_function = aggregation_function
        return self

    def get_instance_value(self, owner_instance, owner_class):
        if not RequestProperty.request_has_been_bound(owner_instance):
            raise Exception(
                "Request must be bound to endpoint before accessing aggregate values"
            )

        return self.aggregation_function(owner_instance)
