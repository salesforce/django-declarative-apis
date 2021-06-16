Endpoint Definitions
====================

Once :code:`EndpointBinder` binds a request to an :code:`EndpointDefinition`, the request is then processed by the endpoint definition.

An important concept in endpoint definitions is :code:`resource`. Resources are abstract representations of underlying objects that are exposed by an API. They may or
may not be tied to a model.

.. note::
    **Important:** Throughout the document, :code:`resource` is referring to :code:`<endpoint_definition>.resource()`.

Built-in Endpoint Definitions
-----------------------------
There are four built-in DDA endpoint definitions with different functionalities that a developer can inherit from to construct their own endpoint definitions.


1. BaseEndpointDefinition
~~~~~~~~~~~~~~~~~~~~~~~~~

It is the base class for implementing Endpoints. At the very least a developer needs to inherit from :code:`BaseEndpointDefinition` class. This is how the EndpointBinder will know how to communicate with the endpoint and query its fields.

**Properties**

:code:`resource()`
    Instance of a resource should either be a dictionary or instance of a Django Model or QuerySet.

    This property **must** be implemented by all endpoint definitions. If not implemented, it will raise a NotImplementedError.

    .. note::
        **Important**: The DDA framework will by default return self.resource as the response, unless response is overridden to return something else.

    **Example**

    .. code-block:: python

        from django_declarative_apis import machinery

        class TodoDefinition(machinery.BaseEndpointDefinition):
            resource_model = Todo

            @endpoint_resource(type=Todo)
            def resource(self):
                return Todo.objects.all()


:code:`response`
    By default it returns :code:`self.resource` unless it is overridden.

:code:`http_status`
    Returns a HTTP 200 OK success status.

:code:`response_filter`
    Returns the filter that will be applied to the response.

**Methods**

:code:`is_authorized()`
    The authentication layer of DDA that is tied to the resource adapter is only responsible for validating the requester. We still need to determine whether the requester is authorized to perform certain actions, which is the reason behind implementation of :code:`is_authorized`.

    :code:`is_authorized` performs authorization check on the request to decide whether or not the user should have access to the resource, and returns a boolean value.


    :code:`is_authorized` implementation should be overridden by the endpoint definition inheriting from :code:`BaseEndpointDefinition`

    **Default Value |** :code:`False`

    **Example:**
    To implement an open API, set the is_authorized to always return True.

    .. code-block:: python

        from django_declarative_apis import machinery

        SampleEndpointDefinition(machinery.BaseEndpointDefinition):
            def is_authorized(self):
                return True

:code:`is_permitted()`
    Similar to code:`is_authorized`, it checks whether a user has the permission to access the resource. Returns a boolean value.

    **Default Value |** :code:`True`

:code:`is_valid()`
    It can be used for scenarios where a request binds correctly, however, there are combination of parameters that would make the request invalid. Returns a boolean value.

    For example, if the valid value for a field is from 1 to 10, this cannot be expressed through :code:`field`. However, we can use the :code:`is_valid` to express it.

    An alternative to :code:`is_valid` would be to use the :code:`@field` as a decorator on a function and express this restriction there.

    **Default Value |** :code:`True`

    **Example**

    .. code-block:: python

        from django_declarative_apis import machinery

        SampleEndpointDefinition(machinery.BaseEndpointDefinition):
            valid_int = field(required=True, type=int)

            def is_authorized(self):
                return True

            def is_valid(self):
                if self.valid_int < 1 or self.valid_in > 10:
                    raise ValueError
                return True


:code:`rate_limit_key()`
    Returns a unique key used for rate-limiting requests to this endpoint. Return :code:`None` if the request should **not** be rate-limited.

    **Default Value |** :code:`None`

:code:`rate_limit_period()`
    Specifies and returns the number of seconds to enforce between requests with the same :code:`rate_limit_key`.

    **Default Value |** 1

:code:`get_endpoint_attributes()`
    Returns a list of endpoint attributes

    **Example**
    Let’s define an endpoint that updates a single task in a todo list.

    .. code-block:: python

        from django_declarative_apis import machinery

        class TodoUpdateSingleTaskDefinition(TodoResourceMixin, machinery.ResourceEndpointDefinition):
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

    Using :code:`get_endpoint_attributes` to find all the attributes of this endpoint and print it.

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


:code:`get_request_properties`
    Returns a list of request properties

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


:code:`get_required_request_properties`
    Returns a list of required request properties

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


:code:`get_request_fields`
    Returns a list of request fields

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


:code:`get_resource_fields()`
    Returns a list of resource fields

:code:`get_required_request_fields()`
    Returns a list of required request fields

    **Example**

    .. code-block:: python

        endpoint_object = resources.TodoUpdateSingleTaskDefinition
        properties = endpoint_object.get_required_request_fields()

        for property in properties:
            print(property.name)

        # It will print:
        # task
        # priority


:code:`get_tasks()`
    Returns endpoint tasks

:code:`get_url_fields()`
    Returns a list of URL fields

    **Example**

    .. code-block:: python

        endpoint_object = resources.TodoUpdateSingleTaskDefinition
        url_fields = endpoint_object.get_url_fields()

        for field in url_fields:
            print(field.name)

        # It will print:
        # resource_id

:code:`documentation()`
    Returns a dictionary containing the class name and endpoint fields that can be used for documentation purposes.

    **Example**::

        {'class_name': 'TodoUpdateSingleTaskDefinition',
        'fields': [{'name': 'request'},
                   {'name': 'task', 'type': <class 'str'>, 'multivalued': False},
                   {'name': 'priority', 'type': <class 'str'>, 'multivalued': False},
                   {'name': 'completion_status', 'type': <class 'bool'>, 'multivalued': False, 'default_value': False}
                   ],
        'consumer_type': 'unknown'}


:code:`get_adhoc_queries()`
    Returns a list of ad hoc queries.


2. EndpointDefinition
~~~~~~~~~~~~~~~~~~~~~
Inherits from :code:`BaseEndpointDefinition`. This base class can be used for implementing endpoints that are not tied to a model. It also implements a basic consumer-based authentication.

**EndpointDefintion takes the following fields**

:code:`request`
    Initialize request using :code:`RawRequestObjectProperty()`

:code:`_consumer_type`
    Defines the consumer type with the default privileges of read and write.

    .. note::
        If you do not want to define a consumer for your api, set :code:`consumer` and :code:`_consumer_type` to :code:`None`.

:code:`is_read_only`
    Determines whether the consumer has read-only privileges or not.

    **Default Value |** :code:`False`

**Methods**

:code:`is_permitted()`
    Checks whether user has permission to access the resource.

:code:`get_consumer_attributes()`
    Returns a list of consumer attributes

:code:`get_consumer_type()`
    Returns consumer type. If consumer is set to :code:`None` it will return unknown.

:code:`documentation()`
    Returns a dictionary containing class name, fields, and consumer type. Used for documentation purposes.



3. ResourceEndpointDefinition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Inherits from :code:`EndpointDefinition`. It is a specialization of :code:`EndpointDefinition` that performs queries on the URL. It can be used when defining endpoints bound to models.

:code:`ResourceEndpointDefinition` is mainly used for :code:`GET`.

**Fields**

:code:`consumer`
    Initialize consumer using :code:`request_attribute()`. It can also be set to :code:`None`.

:code:`resource_id`
    The ID of the resource being fetched from the URL using :code:`url_field`.

:code:`resource_model`
    The model to attach to the resource endpoint definition. It must extend or implement the Django ORM model interface as required.

**Properties**

:code:`resource()`
    Queries the :code:`resource_model` for the given :code:`resource_id`


4. ResourceUpdateEndpointDefinition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Inherits from :code:`ResourceEndpointDefinition`. It handles the changes to the resource that happened from the request, and saves the resource. It can be used for :code:`POST` and :code:`PUT`.

**Tasks**

:code:`mutate()`
    Modifies values of the resource fields by mapping the values of endpoint attributes to the resource.

:code:`validate_input()`
    Checks whether there are any unexpected resource fields present. If so, raises an error and returns the unexpected fields.


Helper Functions
~~~~~~~~~~~~~~~~

:code:`RawRequestObjectProperty()`
    Creates a request object for an endpoint definition.

    **Parameter**

    :code:`additional_safe_fields`
        **Optional |** Defines any additional fields that need to be treated as safe fields.

        **Default Value |** :code:`()`

        **Example**

        .. code-block:: python

            from django_declarative_apis.machinery import RawRequestObjectProperty

            request = RawRequestObjectProperty()

:code:`consumer_attribute()`
    Creates a requester/authenticator object for an endpoint definition.

    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import consumer_attribute

        requester = consumer_attribute()

:code:`request_attribute()`
    It can be used to initialize a consumer object for an endpoint definition.

    **Example**

    .. code-block:: python

        from django_declarative_apis.machinery import request_attribute

        consumer = request_attribute()

