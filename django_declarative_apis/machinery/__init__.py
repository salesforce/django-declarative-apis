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
import django.db.models
from django.conf import settings
from django.http import HttpResponse

from dirtyfields.dirtyfields import reset_state

from django_declarative_apis.machinery.filtering import apply_filters_to_object
from django_declarative_apis.models import BaseConsumer
from django_declarative_apis.resources.utils import HttpStatusCode
from . import errors
from .attributes import (
    Aggregate,
    ConsumerAttribute,
    DeferrableEndpointTask,
    DeferrableGenericEndpointTask,
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

# these imports are unused in this file but may be used in other projects
# that use `machinery` as an interface
from .attributes import TypedEndpointAttributeMixin, RequestFieldGroup  # noqa
from .utils import locate_object, rate_limit_exceeded


logger = logging.getLogger(__name__)


# TODO:
# * Make it generically handle database write failures (updating the http_status to be 5XX)
# * Create new error for deadline exceeded and catch it in the same place as writes
# * Make deferred tasks actually run deferred


class EndpointResourceAttribute(EndpointAttribute):
    """Used as a decorator on a resource function. Specifies the attributes of that
    resource.

    :param type: Specifies the model type. It is used only for documentation generation
        purposes.
    :type type: required

    :param filter: Defines the class filters. Overrides the default filters. Defaults to
        :code:`None`.
    :type filter: optional

    :param returns_list:  It is used for documentation generation purposes. Defaults to
        :code:`False`
    :type returns_list: optional

    **Example**

    .. code-block::

        from django_declarative_apis.machinery import endpoint_resource

        class TodoSingleTaskDefinition(
            TodoResourceMixin,
            machinery.ResourceEndpointDefinition
        ):
            resource_id = url_field(name='id')  # grabs the id from url

            @endpoint_resource(type=Todo)
            def resource(self):
                return Todo.objects.get(id=self.resource_id)
    """

    def __init__(self, type=None, filter=None, returns_list=False, **kwargs):
        super().__init__(**kwargs)
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
        except django.core.exceptions.ObjectDoesNotExist as e:  # noqa: F841
            try:
                message = f"{self.type.__name__} instance not found"
            except AttributeError as e:  # noqa: F841
                message = "Resource instance not found"
            raise errors.ClientErrorNotFound(message)

        if value.__class__ == dict:
            return value

        if not getattr(value, "_api_filter", False):
            value._api_filter = self.filter

        return value


class EndpointResponseAttribute(EndpointAttribute):
    """Used as a decorator on a response function. Specifies the attributes of the
    response.

    :param type: Specifies the response type, which can be dictionary, list, or
        type. It is used only for documentation generation purposes.
    :type type: required

    :param filter: Defines the class filters. Overrides the default filters.
        Defaults to :code:`None`.
    :type filter: optional

    **Example**

    .. code-block::

        from django_declarative_apis.machinery import endpoint_response

        @endpoint_response(type=dict)
        def response(self):
            return http.status.OK
    """

    def __init__(self, type, filter=None, **kwargs):
        super().__init__(**kwargs)
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

        # This metaclass sets EndpointAttributeDescriptor's names if they haven't
        # otherwise been set. This will walk parent classes as well so that attributes
        # can be defined through inheritance
        ancestor_attribs = (ancestor.__dict__.items() for ancestor in cls.mro())
        for name, attribute in itertools.chain(dict.items(), *ancestor_attribs):
            try:
                if not attribute.name:
                    attribute.name = name
            except AttributeError as e:  # noqa
                pass


def current_dirty_dict(resource):
    """Get the `current` (in-memory) values for fields that have not yet been written to the database."""
    new_data = resource.get_dirty_fields(check_relationship=True, verbose=True)
    field_name_to_att_name = {f.name: f.attname for f in resource._meta.concrete_fields}
    return {
        field_name_to_att_name[key]: values["current"]
        for key, values in new_data.items()
    }


def update_dirty(resource):
    """Write dirty fields to the database."""
    dirty_dict = current_dirty_dict(resource)
    resource_next, created = type(resource).objects.update_or_create(
        pk=resource.pk, defaults=dirty_dict
    )

    # update fields in memory that changed on save to the database
    field_name_to_att_name = {f.name: f.attname for f in resource._meta.concrete_fields}
    for k, v in resource_next._as_dict(check_relationship=True).items():
        att_key = field_name_to_att_name[k]
        if getattr(resource, att_key, None) != v:
            setattr(resource, att_key, v)
    resource._state.adding = False
    resource._state.db = resource_next._state.db
    resource._state.fields_cache = {}
    reset_state(type(resource), resource)


class EndpointBinder:
    class BoundEndpointManager:
        def __init__(self, manager, bound_endpoint):
            self.manager = manager
            self.bound_endpoint = bound_endpoint
            self.binding_exc_info = None
            self.validation_exc_info = None

        # TODO: make this method less complex and remove the `noqa`
        def get_response(self):  # noqa: C901
            error = self.binding_exc_info or self.validation_exc_info
            if error:
                exc_type, exc_value, exc_traceback = error
                if isinstance(exc_value, errors.ClientError):
                    logger.warning(exc_value.error_message)
                else:
                    logger.error(str(exc_value.args) + "\n" + str(exc_traceback))

                raise exc_value.with_traceback(exc_traceback)

            resource = self.bound_endpoint.resource

            if isinstance(resource, django.db.models.Model) and hasattr(
                resource, "is_dirty"
            ):
                if resource and resource.is_dirty(check_relationship=True):
                    update_dirty(resource)

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
                if (
                    ce.save_changes
                    and resource
                    and hasattr(resource, "is_dirty")
                    and resource.is_dirty()
                ):
                    update_dirty(resource)
                raise

            if isinstance(resource, django.db.models.Model) and hasattr(
                resource, "is_dirty"
            ):
                if resource and resource.is_dirty(check_relationship=True):
                    update_dirty(resource)

            # all synchronous tasks are done, finalize the endpoint before launching async tasks
            self.bound_endpoint.finalize()

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
                try:
                    x_expand = self.bound_endpoint.request.META.get("HTTP_X_EXPAND")
                except AttributeError:
                    x_expand = ""

                return (
                    status_code,
                    apply_filters_to_object(data, filter_def, x_expand),
                )

    def __init__(self, endpoint_definition):
        super().__init__()
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

        # Bind the request object within the instance (this allows RequestProperties to
        # access the request without the endpoint definition having direct access to it)
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
        # Access all request properties (this validates a request using the definition
        # and caches the values)
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


class _EndpointRequestLifecycleManager:
    def __init__(self, endpoint_definition):
        super().__init__()
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


class BehavioralEndpointDefinitionRouter:
    def __init__(self, *endpoint_definitions):
        super().__init__()
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
                "ev=dda, method=%s, path=%s, handler=%s",
                request.method,
                request.path,
                bound_endpoint.bound_endpoint.__class__.__name__,
            )
            result = bound_endpoint.get_response()
            return result
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
    """The base class for implementing Endpoints. At the very least a developer needs to
    inherit from :code:`BaseEndpointDefinition` class. This is how the EndpointBinder
    will know how to communicate with the endpoint and query its fields.
    """

    @abc.abstractmethod
    def is_authorized(self):
        """The authentication layer of DDA that is tied to the resource adapter is only
        responsible for validating the requester. We still need to determine whether the
        requester is authorized to perform certain actions, which is the reason behind
        implementation of :code:`is_authorized`.

        :code:`is_authorized` performs an authorization check on the request to decide
        whether or not the user should have access to the resource and returns a boolean
        value.

        :code:`is_authorized` implementation should be overridden by the endpoint
        definition inheriting from :code:`BaseEndpointDefinition`

        **Default Value |** :code:`False`

        **Example:**
        To implement an open API, set the is_authorized to always return True.

        .. code-block:: python

            from django_declarative_apis import machinery

            class SampleEndpointDefinition(machinery.BaseEndpointDefinition):
                def is_authorized(self):
                    return True
        """
        return False

    def is_permitted(self):
        """Similar to :code:`is_authorized`, it checks whether a user has the permission
        to access the resource. Returns a boolean value.

        **Default Value |** :code:`True`
        """
        return True

    def is_valid(self):
        """Used in scenarios where a request binds correctly but there are combination
        of parameters that would make the request invalid. Returns a boolean value.

        For example, if the valid value for a field is from 1 to 10, this cannot be
        expressed through :code:`field`. However, we can use the :code:`is_valid` to
        express it.

        An alternative to :code:`is_valid` would be to use the :code:`@field` as a
        decorator on a function and express this restriction there.

        **Default Value |** :code:`True`

        **Example**

        .. code-block:: python

            from django_declarative_apis import machinery

            class SampleEndpointDefinition(machinery.BaseEndpointDefinition):
                valid_int = field(required=True, type=int)

                def is_authorized(self):
                    return True

                def is_valid(self):
                    if self.valid_int < 1 or self.valid_in > 10:
                        raise ValueError
                    return True
        """
        return True

    def rate_limit_key(self):
        """Returns a unique key used for rate-limiting requests to this endpoint.
        Returns :code:`None` if the request should **not** be rate-limited.

        **Default Value |** :code:`None`
        """
        return None

    def rate_limit_period(self):
        """Specifies and returns the number of seconds to enforce between requests with
        the same :code:`rate_limit_key`.

        **Default Value |** 1
        """
        return 1

    @property
    def response_filter(self):
        """Returns the filter that will be applied to the response."""
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
        """Returns a HTTP 200 OK success status."""
        return http.client.OK

    @property
    @abc.abstractmethod
    def resource(self):
        """Instance of a resource should either be a dictionary or instance of a Django
        Model or QuerySet.

        This property **must** be implemented by all endpoint definitions. If not
        implemented, it will raise a NotImplementedError.

        .. note::
            **Important**: The DDA framework will by default return self.resource as the
            response, unless response is overridden to return something else.

        **Example**

        .. code-block:: python

            from django_declarative_apis import machinery

            class TodoDefinition(machinery.BaseEndpointDefinition):
                resource_model = Todo

                @endpoint_resource(type=Todo)
                def resource(self):
                    return Todo.objects.all()
        """
        raise NotImplementedError("Endpoints must implement self.resource property")

    @property
    def response(self):
        """
        By default it returns :code:`self.resource` unless it is overridden.
        """
        return self.resource

    def finalize(self):
        """
        Called immediately before a response is returned.  Override this method in an
        Endpoint Definition to perform any clean-up not handled automatically by the framework.
        """
        pass

    @classmethod
    def get_endpoint_attributes(cls):
        """Returns a list of endpoint attributes

        **Example**
        Let’s define an endpoint that updates a single task in a todo list.

        .. code-block:: python

            from django_declarative_apis import machinery

            class TodoUpdateSingleTaskDefinition(
                TodoResourceMixin,
                machinery.ResourceEndpointDefinition,
            ):
                task = field(required=True, type=str)
                priority = field(required=True, type=str)
                completion_status = field(type=bool, default=False)
                resource_id = url_field(name='id')

                @endpoint_resource(type=Todo)
                def resource(self):
                    task = Todo.objects.get(id=self.resource_id)
                    task.task = self.task
                    task.priority = self.priority
                    task.completion_status = self.completion_status
                    task.save()
                    return task

        Using :code:`get_endpoint_attributes` to find all the attributes of this
        endpoint and print it:

        .. code-block:: python

            endpoint_object = resources.TodoUpdateSingleTaskDefinition
            attributes = endpoint_object.get_endpoint_attributes()

            for attribute in attributes:
                print(attribute.name)

            # It will print:
            # request
            # task
            # priority
            # completion_status
            # resource_id
            # resource
        """
        endpoint_attributes = filter(
            lambda attribute: isinstance(attribute, EndpointAttribute),
            [getattr(cls, name) for name in dir(cls)],
        )
        return sorted(
            endpoint_attributes, key=lambda attribute: attribute.attribute_number
        )

    @classmethod
    def get_request_properties(cls):
        """Returns a list of request properties

        **Example**

        .. code-block:: python

            endpoint_object = resources.TodoUpdateSingleTaskDefinition
            properties = endpoint_object.get_request_properties()

            for property in properties:
                print(property.name)

            # It will print:
            # request
            # task
            # priority
            # completion_status
        """
        return list(
            filter(
                lambda attribute: isinstance(attribute, RequestProperty),
                cls.get_endpoint_attributes(),
            )
        )

    @classmethod
    def get_required_request_properties(cls):
        """Returns a list of required request properties

        **Example**

        .. code-block:: python

            endpoint_object = resources.TodoUpdateSingleTaskDefinition
            properties = endpoint_object.get_required_request_properties()

            for property in properties:
                print(property.name)

            # It will print:
            # request
            # task
            # priority
        """
        return list(
            filter(lambda property: property.required, cls.get_request_properties())
        )

    @classmethod
    def get_request_fields(cls):
        """Returns a list of request fields

        **Example**

        .. code-block:: python

            endpoint_object = resources.TodoUpdateSingleTaskDefinition
            fields = endpoint_object.get_request_field()

            for field in fields:
                print(field.name)

            # It will print:
            # request
            # task
            # priority
            # completion_status
        """
        return list(
            filter(
                lambda property: isinstance(property, RequestField),
                cls.get_request_properties(),
            )
        )

    @classmethod
    def get_resource_fields(cls):
        """Returns a list of resource fields"""
        return list(
            filter(
                lambda property: isinstance(property, ResourceField),
                cls.get_request_properties(),
            )
        )

    @classmethod
    def get_required_request_fields(cls):
        """Returns a list of required request fields

        **Example**

        .. code-block:: python

            endpoint_object = resources.TodoUpdateSingleTaskDefinition
            properties = endpoint_object.get_required_request_fields()

            for property in properties:
                print(property.name)

            # It will print:
            # task
            # priority
        """
        return list(
            filter(
                lambda property: isinstance(property, RequestField),
                cls.get_required_request_properties(),
            )
        )

    @classmethod
    def get_tasks(cls):
        """Returns endpoint tasks"""
        endpoint_tasks = filter(
            lambda property: isinstance(property, EndpointTask),
            cls.get_endpoint_attributes(),
        )

        return sorted(endpoint_tasks, key=lambda task: task.priority)

    @classmethod
    def get_url_fields(cls):
        """Returns a list of URL fields

        **Example**

        .. code-block:: python

            endpoint_object = resources.TodoUpdateSingleTaskDefinition
            url_fields = endpoint_object.get_url_fields()

            for field in url_fields:
                print(field.name)

            # It will print:
            # resource_id
        """
        return list(
            filter(
                lambda property: isinstance(property, RequestUrlField),
                cls.get_endpoint_attributes(),
            )
        )

    @classmethod
    def documentation(cls):
        """Returns a dictionary containing the class name and endpoint fields that can
        be used for documentation purposes.

        **Example**::

            {'class_name': 'TodoUpdateSingleTaskDefinition',
            'fields': [{'name': 'request'},
                       {'name': 'task', 'type': <class 'str'>, 'multivalued': False},
                       {'name': 'priority', 'type': <class 'str'>, 'multivalued': False},
                       {'name': 'completion_status', 'type': <class 'bool'>,
                        'multivalued': False, 'default_value': False}
                       ],
            'consumer_type': 'unknown'}
        """
        return {
            "class_name": cls.__name__,
            "fields": [p.documentation for p in cls.get_request_properties()],
        }

    @classmethod
    def get_adhoc_queries(cls):
        """Returns a list of ad hoc queries."""
        return [
            prop
            for prop in cls.get_endpoint_attributes()
            if isinstance(prop, RequestAdhocQuerySet)
        ]


class EndpointDefinition(BaseEndpointDefinition):
    """This base class can be used for implementing endpoints that are not tied to a
    model. It also implements a basic consumer-based authentication.
    """

    request = RawRequestObjectProperty()
    """Initialize request using :code:`RawRequestObjectProperty()`"""

    _consumer_type = ConsumerAttribute(field_name="type", default="RW")
    """Defines the consumer type with the default privileges of read and write.

    .. note::
        If you do not want to define a consumer for your api, set
        :code:`consumer` and :code:`_consumer_type` to :code:`None`.
    """

    is_read_only = False
    """ Determines whether the consumer has read-only privileges or not.

    **Default Value |** :code:`False`
    """

    def is_permitted(self):
        """Checks whether user has permission to access the resource."""
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
        """Returns a list of consumer attributes"""
        return list(
            filter(
                lambda property: isinstance(property, ConsumerAttribute),
                cls.get_request_properties(),
            )
        )

    @classmethod
    def get_consumer_type(cls):
        """Returns consumer type. If consumer is set to :code:`None` it will return
        unknown.
        """
        consumer_attribute = cls.get_consumer_attributes()
        if len(consumer_attribute) == 1:
            consumer_attribute = consumer_attribute[0]
            return consumer_attribute.name
        else:
            return "unknown"

    @classmethod
    def documentation(cls):
        """Returns a dictionary containing class name, fields, and consumer type. Used
        for documentation purposes.
        """
        docs = super().documentation()
        docs["consumer_type"] = cls.get_consumer_type()
        return docs


class ResourceCreationMixin:
    @property
    def http_status(self):
        return http.client.CREATED


class ResourceEndpointDefinition(EndpointDefinition):
    """It is a specialization of :code:`EndpointDefinition` that performs
    queries on the URL. It can be used when defining endpoints bound to models.

    :code:`ResourceEndpointDefinition` is mainly used for :code:`GET`.
    """

    consumer = RequestAttribute()
    """Initialize consumer using :code:`request_attribute()`. It can also be set to
    :code:`None`.
    """

    resource_id = RequestUrlField(
        name="id", description="UUID of the resource to retrieve"
    )
    """ The ID of the resource being fetched from the URL or being updated.
    """
    resource_model = None
    """ The model to attach to the resource endpoint definition.
    It must extend or implement the Django ORM model interface as required.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cached_resource = None

    @EndpointResourceAttribute()
    def resource(self):
        """Queries the object manager of `self.resource_model` for the given id
        (`self.resource_id`).
        """
        if not self._cached_resource:
            self._cached_resource = self.resource_model.objects.get(id=self.resource_id)
        return self._cached_resource


class ResourceUpdateEndpointDefinition(ResourceEndpointDefinition):
    """Handles the changes to the resource that happened from the request, and saves the
    resource. It can be used for :code:`POST` and :code:`PUT`.
    """

    @EndpointTask(priority=-100)
    def mutate(self):
        """Modifies values of the resource fields by mapping the values of endpoint
        attributes to the resource.
        """
        resource = self.resource
        for resource_field in self.get_resource_fields():
            field_value = getattr(self, resource_field.name)
            if field_value is not None:
                setattr(resource, resource_field.name, field_value)

    @EndpointTask(priority=-101)
    def validate_input(self):
        """Checks whether there are any unexpected resource fields present. If so,
        raises an error and returns the unexpected fields.
        """
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
deferrable_generic_task = DeferrableGenericEndpointTask
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
