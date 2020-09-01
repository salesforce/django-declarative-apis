#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#
import abc
import http.client
import itertools
import logging
import sys

import django
from django.conf import settings
from django.db import models
from django.http import HttpResponse

from django_declarative_apis.machinery.filtering import apply_filters_to_object
from django_declarative_apis.models import BaseConsumer
from django_declarative_apis.resources.utils import HttpStatusCode
from . import errors
from .attributes import (
    Aggregate,
    ConsumerAttribute,
    DeferrableEndpointTask,
    EndpointAttribute,
    EndpointTask,
    RawRequestObjectProperty,
    RequestAdhocQuerySet,
    RequestAttribute,
    RequestField,
    RequestProperty,
    RequestUrlField,
    RequireAllAttribute,
    RequireAllIfAnyAttribute,
    RequireOneAttribute,
    ResourceField,
)

# these imports are unusued in this file but may be used in other projects
# that use `machinery` as an interface
from .attributes import TypedEndpointAttributeMixin, RequestFieldGroup  # noqa
from .utils import locate_object, rate_limit_exceeded


logger = logging.getLogger(__name__)


# TODO:
# * Make it generically handle database write failures (updating the http_status to be 5XX)
# * Create new error for deadline exceeded and catch it in the same place as writes
# * Make deferred tasks actually run deferred


class EndpointResourceAttribute(EndpointAttribute):
    def __init__(self, type, filter=None, returns_list=False, **kwargs):
        super(EndpointResourceAttribute, self).__init__(**kwargs)
        self.type = type
        self.filter = filter
        self.func = None
        self.returns_list = returns_list

    def __call__(self, func):
        self.func = func
        return self

    def get_instance_value(self, owner_instance, owner_class):
        if not owner_instance:
            return self
        try:
            value = self.func(owner_instance)
        except django.core.exceptions.ObjectDoesNotExist:
            raise errors.ClientErrorNotFound(
                "{0} instance not found".format(self.type.__name__)
            )

        if value.__class__ == dict:
            return value

        if not getattr(value, "_api_filter", False):
            value._api_filter = self.filter

        return value


class EndpointResponseAttribute(EndpointAttribute):
    def __init__(self, type, filter=None, **kwargs):
        super(EndpointResponseAttribute, self).__init__(**kwargs)
        self.type = type
        self.filter = filter
        self.func = None

    def __call__(self, func):
        self.func = func
        return self

    def get_instance_value(self, owner_instance, owner_class):
        if not owner_instance:
            return self
        value = self.func(owner_instance)
        if not getattr(value, "_api_filter", False):
            if self.filter:
                value._api_filter = self.filter
        return value


class EndpointDefinitionMeta(abc.ABCMeta, metaclass=abc.ABCMeta):
    def __init__(cls, class_name, bases=None, dict=None):
        super(EndpointDefinitionMeta, cls).__init__(class_name, bases, dict)

        # This metaclass sets EndpointAttributeDiscriptor's names if they haven't otherwise been set
        # This will walk parent classes as well so that attributes can be defined through inheritance
        ancestor_attribs = (ancestor.__dict__.items() for ancestor in cls.mro())
        for name, attribute in itertools.chain(dict.items(), *ancestor_attribs):
            try:
                if not attribute.name:
                    attribute.name = name
            except AttributeError as e:  # noqa
                pass


class EndpointBinder(object):
    class BoundEndpointManager(object):
        def __init__(self, manager, bound_endpoint):
            self.manager = manager
            self.bound_endpoint = bound_endpoint
            self.binding_exc_info = None
            self.validation_exc_info = None

        def get_response(self):
            error = self.binding_exc_info or self.validation_exc_info
            if error:
                exc_type, exc_value, exc_traceback = error
                if isinstance(exc_value, errors.ClientError):
                    logger.warning(exc_value.error_message)
                else:
                    logger.error(str(exc_value.args) + "\n" + str(exc_traceback))

                raise exc_value.with_traceback(exc_traceback)

            resource = self.bound_endpoint.resource

            if hasattr(resource, "is_dirty"):
                if resource and resource.is_dirty(check_relationship=True):
                    resource.save()

            endpoint_tasks = sorted(
                self.manager.endpoint_tasks, key=lambda t: t.priority
            )
            immediate_tasks = filter(
                lambda t: not isinstance(t, DeferrableEndpointTask), endpoint_tasks
            )
            deferred_tasks = filter(
                lambda t: isinstance(t, DeferrableEndpointTask), endpoint_tasks
            )
            try:
                for immediate_task in immediate_tasks:
                    immediate_task.run(self.bound_endpoint)

            except errors.ClientError as ce:
                if ce.save_changes and resource and resource.is_dirty():
                    resource.save()
                raise

            if hasattr(resource, "is_dirty"):
                if resource and resource.is_dirty(check_relationship=True):
                    resource.save()

            for deferred_task in deferred_tasks:
                deferred_task.run(self.bound_endpoint)

            if getattr(resource, "_api_filter", False):
                filter_def = resource._api_filter
            else:
                filter_def = self.bound_endpoint.response_filter

            data = self.bound_endpoint.response
            status_code = self.bound_endpoint.http_status

            if isinstance(data, HttpResponse):
                if 200 <= status_code <= 299:
                    return status_code, data
                else:
                    raise HttpStatusCode(data)
            else:
                return (
                    status_code,
                    apply_filters_to_object(
                        data,
                        filter_def,
                        self.bound_endpoint.request.META.get("HTTP_X_EXPAND"),
                    ),
                )

    def __init__(self, endpoint_definition):
        super(EndpointBinder, self).__init__()
        self.endpoint_definition = endpoint_definition
        self.endpoint_attributes = endpoint_definition.get_endpoint_attributes()
        self.request_properties = endpoint_definition.get_request_properties()
        self.required_request_properties = (
            endpoint_definition.get_required_request_properties()
        )
        try:
            self.consumer_attributes = endpoint_definition.get_consumer_attributes()
        except AttributeError:
            self.consumer_attributes = []
        self.request_fields = endpoint_definition.get_request_fields()
        self.required_request_fields = endpoint_definition.get_required_request_fields()
        self.endpoint_tasks = endpoint_definition.get_tasks()
        self.url_fields = endpoint_definition.get_url_fields()
        self.adhoc_queries = endpoint_definition.get_adhoc_queries()

    def create_bound_endpoint(self, manager, request, *args, **kwargs):
        endpoint = self.endpoint_definition()

        for url_field in self.url_fields:
            if (url_field.api_name or url_field.name) in kwargs:
                url_field.set_value(kwargs.get(url_field.api_name or url_field.name))

        for adhoc_query_field in self.adhoc_queries:
            adhoc_query_field.set_value(
                {
                    key: val
                    for (key, val) in request.GET.items()
                    if key.startswith(adhoc_query_field.name)
                }
            )

        # Bind the request object within the instance (this allows RequestProperties to access the request
        # without the endpoint definition having direct access to it)
        RequestProperty.bind_request_to_instance(endpoint, request)

        bound_endpoint_manager = EndpointBinder.BoundEndpointManager(manager, endpoint)

        try:
            self._bind_endpoint(endpoint)
        except Exception as e:  # noqa
            bound_endpoint_manager.binding_exc_info = sys.exc_info()
            return bound_endpoint_manager

        try:
            self._validate_endpoint(endpoint)
        except Exception as e:  # noqa
            bound_endpoint_manager.validation_exc_info = sys.exc_info()

        return bound_endpoint_manager

    def _bind_endpoint(self, endpoint):
        # Access all request properties (this validates a request using the definition and caches the values)
        extra_error_message = ""
        missing_required_properties = []
        invalid_value_properties = []
        for request_property in self.request_properties:
            try:
                value = getattr(endpoint, request_property.name)
                if value is None and request_property.required:
                    if isinstance(request_property, ConsumerAttribute):
                        # A missing required consumer attribute should fail quickly as forbidden
                        raise errors.ClientErrorForbidden()
                    else:
                        # Otherwise collect missing properties and report them all together
                        missing_required_properties.append(request_property)
            except errors.ClientErrorMissingFields as mfe:  # TODO: seems unreachable
                extra_error_message += mfe.error_message  # pragma: nocover
            except (ValueError, errors.ClientErrorInvalidFieldValues) as ve:  # noqa
                # Collect invalid values and report them all together
                invalid_value_properties.append(request_property)  # pragma: nocover

        if missing_required_properties or extra_error_message:
            raise errors.ClientErrorMissingFields(
                [property.name for property in missing_required_properties],
                extra_message=extra_error_message,
            )

        if invalid_value_properties:
            raise errors.ClientErrorInvalidFieldValues(
                [request_property.name for request_property in invalid_value_properties]
            )

    def _validate_endpoint(self, endpoint):
        # Run standard validators
        try:
            if not (
                endpoint.is_authorized()
                and endpoint.is_permitted()
                and endpoint.is_valid()
            ):
                raise errors.ClientErrorForbidden(
                    additional_info=getattr(endpoint, "_validation_error_message", None)
                )

        except django.core.exceptions.ObjectDoesNotExist:
            raise errors.ClientErrorNotFound()

        # check ratelimit
        rate_limit_key = endpoint.rate_limit_key()
        if (rate_limit_key is not None) and rate_limit_exceeded(
            rate_limit_key, endpoint.rate_limit_period()
        ):
            raise errors.ClientErrorRequestThrottled()


class _EndpointRequestLifecycleManager(object):
    def __init__(self, endpoint_definition):
        super(_EndpointRequestLifecycleManager, self).__init__()
        self.endpoint_definition = endpoint_definition
        self.binder = EndpointBinder(endpoint_definition)
        self.endpoint_tasks = endpoint_definition.get_tasks()

    def bind_endpoint_to_request(self, request, *args, **kwargs):
        return self.binder.create_bound_endpoint(self, request, *args, **kwargs)

    def process_request_and_get_response(self, request, *args, **kwargs):
        bound_endpoint = self.bind_endpoint_to_request(request, *args, **kwargs)
        return bound_endpoint.get_response()

    def __str__(self):  # pragma: nocover
        return self.endpoint_definition.__name__


class BehavioralEndpointDefinitionRouter(object):
    def __init__(self, *endpoint_definitions):
        super(BehavioralEndpointDefinitionRouter, self).__init__()
        self.endpoint_definitions = endpoint_definitions
        self.endpoint_managers = [
            _EndpointRequestLifecycleManager(endpoint)
            for endpoint in endpoint_definitions
        ]
        self.endpoint_manager_names = "({0})".format(
            ",".join(map(lambda e: e.__name__, endpoint_definitions))
        )

    def bind_endpoint_to_request(self, request, *args, **kwargs):
        bound_endpoint = None
        for candidate_endpoint_manager in self.endpoint_managers:
            bound_endpoint = candidate_endpoint_manager.bind_endpoint_to_request(
                request, *args, **kwargs
            )
            if bound_endpoint.binding_exc_info is None:
                break
        return bound_endpoint

    def process_request_and_get_response(self, request, *args, **kwargs):
        try:
            bound_endpoint = self.bind_endpoint_to_request(request, *args, **kwargs)
            logger.info(
                "Processing request with handler %s",
                bound_endpoint.bound_endpoint.__class__.__name__,
            )
            return bound_endpoint.get_response()

        except errors.ApiError:
            raise
        except Exception as e:  # pragma: nocover
            raise errors.ServerError() from e

    def __call__(self, *args, **kwargs):
        return self.process_request_and_get_response(*args, **kwargs)

    def __str__(self):  # pragma: nocover
        return self.endpoint_manager_names

    @property
    def documentation(self):
        return [x.documentation() for x in self.endpoint_definitions]


class EndpointDefinitionMixin(metaclass=EndpointDefinitionMeta):
    pass


class BaseEndpointDefinition(metaclass=EndpointDefinitionMeta):
    @abc.abstractmethod
    def is_authorized(self):
        """ Authorization check. Should be overridden by endpoint definition implementations.

        Returns:
            ``bool``: Whether or not the user should be able to access the resource. Defaults to ``False``.
        """
        return False

    def is_permitted(self):
        return True

    def is_valid(self):
        return True

    def rate_limit_key(self):
        """
        Should return a unique key that is used for rate-limiting requests to this endpoint.
        Return None if the request should not be rate-limited
        """
        return None

    def rate_limit_period(self):
        """
        number of seconds to enforce between requests with the same rate_limit_key
        """
        return 1

    @property
    def response_filter(self):
        filter_def_name = getattr(
            settings, "DECLARATIVE_ENDPOINT_DEFAULT_FILTERS", None
        )
        if filter_def_name:
            filter_def = locate_object(filter_def_name)
        else:
            filter_def = {}
        return filter_def

    @property
    def http_status(self):
        return http.client.OK

    @property
    @abc.abstractmethod
    def resource(self):
        """ The instance of a resource. Should either be a ``dict`` or instance of a Django Model or QuerySet.

        This property *must* be implemented by all endpoint definitions.
        """
        raise NotImplementedError("Endpoints must implement self.resource property")

    @property
    def response(self):
        return self.resource

    @classmethod
    def get_endpoint_attributes(cls):
        endpoint_attributes = filter(
            lambda attribute: isinstance(attribute, EndpointAttribute),
            [getattr(cls, name) for name in dir(cls)],
        )
        return sorted(
            endpoint_attributes, key=lambda attribute: attribute.attribute_number
        )

    @classmethod
    def get_request_properties(cls):
        return list(
            filter(
                lambda attribute: isinstance(attribute, RequestProperty),
                cls.get_endpoint_attributes(),
            )
        )

    @classmethod
    def get_required_request_properties(cls):
        return list(
            filter(lambda property: property.required, cls.get_request_properties())
        )

    @classmethod
    def get_request_fields(cls):
        return list(
            filter(
                lambda property: isinstance(property, RequestField),
                cls.get_request_properties(),
            )
        )

    @classmethod
    def get_resource_fields(cls):
        return list(
            filter(
                lambda property: isinstance(property, ResourceField),
                cls.get_request_properties(),
            )
        )

    @classmethod
    def get_required_request_fields(cls):
        return list(
            filter(
                lambda property: isinstance(property, RequestField),
                cls.get_required_request_properties(),
            )
        )

    @classmethod
    def get_tasks(cls):
        endpoint_tasks = filter(
            lambda property: isinstance(property, EndpointTask),
            cls.get_endpoint_attributes(),
        )

        return sorted(endpoint_tasks, key=lambda task: task.priority)

    @classmethod
    def get_url_fields(cls):
        return list(
            filter(
                lambda property: isinstance(property, RequestUrlField),
                cls.get_endpoint_attributes(),
            )
        )

    @classmethod
    def documentation(cls):
        return {
            "class_name": cls.__name__,
            "fields": [p.documentation for p in cls.get_request_properties()],
        }

    @classmethod
    def get_adhoc_queries(cls):
        return [
            prop
            for prop in cls.get_endpoint_attributes()
            if isinstance(prop, RequestAdhocQuerySet)
        ]


class EndpointDefinition(BaseEndpointDefinition):
    """ A base class to be used when defining endpoints.

    Base class to be used implementing endpoints that aren't necessarily tied to a model. Also implements
    basic consumer-based authentication.
    """

    request = RawRequestObjectProperty()
    _consumer_type = ConsumerAttribute(field_name="type", default="RW")
    is_read_only = False
    """ Used to determine accessibility for the current consumer.
    """

    def is_permitted(self):
        """ Checks authorization for the current consumer.

        Returns:
            ``bool``: Whether or not the user has permission to the resource.
        """
        if (
            self._consumer_type is None
            or self._consumer_type == BaseConsumer.TYPE_READ_WRITE
        ):
            return True
        if self._consumer_type == BaseConsumer.TYPE_READ_ONLY:
            if self.is_read_only:
                return True
            if self.request.method == "GET":
                return True
            else:
                self._validation_error_message = (
                    "Action not allowed for read-only consumer"
                )
                return False
        return False

    @classmethod
    def get_consumer_attributes(cls):
        return list(
            filter(
                lambda property: isinstance(property, ConsumerAttribute),
                cls.get_request_properties(),
            )
        )

    @classmethod
    def get_consumer_type(cls):
        consumer_attribute = cls.get_consumer_attributes()
        if len(consumer_attribute) == 1:
            consumer_attribute = consumer_attribute[0]
            return consumer_attribute.name
        else:
            return "unknown"

    @classmethod
    def documentation(cls):
        docs = super().documentation()
        docs["consumer_type"] = cls.get_consumer_type()
        return docs


class ResourceCreationMixin(object):
    @property
    def http_status(self):
        return http.client.CREATED


class ResourceEndpointDefinition(EndpointDefinition):
    """ A base class to be used when defining endpoints bound to models.
    """

    consumer = RequestAttribute()

    resource_id = RequestUrlField(
        name="id", description="UUID of the resource to retrieve"
    )
    """ The ID of the resource being fetched or updated.
    """
    resource_model = None
    """ The model to attach to the resource endpoint definition.

    Must extend or implement the Django ORM model interface as required.
    """

    def __init__(self, *args, **kwargs):
        super(ResourceEndpointDefinition, self).__init__()
        self._cached_resource = None

    @property
    def resource(self):
        """ Resource implementation

        Queries the object manager of `self.resource_model` for the given id (`self.resource_id`).
        """
        if not self._cached_resource:
            self._cached_resource = self.resource_model.objects.get(id=self.resource_id)
        return self._cached_resource


class ResourceUpdateEndpointDefinition(ResourceEndpointDefinition):
    @EndpointTask(priority=-100)
    def mutate(self):
        resource = self.resource
        for resource_field in self.get_resource_fields():
            field_value = getattr(self, resource_field.name)
            if field_value is not None:
                setattr(resource, resource_field.name, field_value)

    @EndpointTask(priority=-101)
    def validate_input(self):
        resource = self.resource
        expected_fields = set(
            list(field.name for field in self.get_resource_fields())
            + list(field.name for field in self.get_request_fields())
        )
        unexpected = self.request.body_field_names - expected_fields
        if unexpected:
            raise errors.ClientErrorUnprocessableEntity(
                "Unexpected fields: {}".format(", ".join(unexpected))
            )


task = EndpointTask
deferrable_task = DeferrableEndpointTask
request_attribute = RequestAttribute
consumer_attribute = ConsumerAttribute
field = RequestField
resource_field = ResourceField
url_field = RequestUrlField
adhoc_queryset = RequestAdhocQuerySet
aggregate = Aggregate
require_one = RequireOneAttribute
require_all = RequireAllAttribute
require_all_if_any = RequireAllIfAnyAttribute
endpoint_resource = EndpointResourceAttribute
endpoint_response = EndpointResponseAttribute
