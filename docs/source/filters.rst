Filters
=======

Filters are used to define the output of your responses. The only fields returned in the response are the ones specified in the filters. If not specified, the field will not be part of the response.

.. note::
    **Important:** If filters are not defined, the response will be an empty dictionary.


Filtering Options
~~~~~~~~~~~~~~~~~
ALWAYS
    The response field will always be returned.
NEVER
    The response field will never be returned.
IF_TRUTHY
    Only return if the response field value is a python truthy value.


**Structure for defining a filter**

.. code-block:: python

    FilterName = {
        Model: {
            'response_field': filtering_option
        }
    }


**Example:**
Creating a new :code:`filters.py` file and defining a filter for a Todo app’s response.

.. code-block:: python

    TodoResponseFilter = {
        Todo: {
            'task': filtering.ALWAYS,
            'priority': filtering.ALWAYS,
            'created_date': filtering.NEVER,
            'completion_status': filtering.IF_TRUTHY
        },
    }

* :code:`task` and :code:`priority` fields are set to **ALWAYS** . Therefore, they will always be returned in the response.
* :code:`create_date` is set to **NEVER** , thus, it will not appear in the response object.
* :code:`completion_status` will only be included in the response if it is a python truthy value.


Define Filters
~~~~~~~~~~~~~~
Filters can be defined in four places:


.. note::
    **Important:** Items lower in the list take precedence over items at the top of the list. For instance, :code:`response_filter` overrides the default filter defined in :code:`settings.py`.


1. settings.py
    **Required |** Set default filters for the entire application in settings.py by setting :code:`DECLARATIVE_ENDPOINT_DEFAULT_FITLERS` to your :code:`filters.py` file.

    **Example:**
    Set the Todo filter as the default filter in :code:`settings.py`.

    .. code-block:: python

        DECLARATIVE_ENDPOINT_DEFAULT_FILTERS = "todo.filters.TodoResponseFilter"

2. ``response_filter``

    **Optional |** Defines filters for a class and can be used interchangeably with :code:`@endpoint_resource()`. To implement, set :code:`response_filter` as a class-level field on your :code:`EndpointDefinition`.

    **Default Value |** :code:`None`

    **Example:**

    .. code-block:: python

        class TodoCreationEndpoint:
            response_filter = filters.TodoResponseFilter

3. ``@endpoint_resource``

    **Optional |** Defines filters for a class and can be used interchangeably with response filter. To implement, set :code:`filter=<filter>` in an argument to the :code:`@endpoint_resource` decorator.

    **Default Value |** :code:`None`

    **Example**

    .. code-block:: python

        from django-declarative-apis.machinery import endpoint_resource

        class TodoDefinition(TodoResourceMixin, machinery.ResourceEndpointDefinition):
            resource_model = Todo

            @endpoint_resource(type=Todo, filter=filters.TodoResponseFilter)
            def resource(self):
                return Todo.objects.all()


4. ``_api_filter``
    **Optional |** Defines filters for a return object. To implement, set :code:`_api_filter` on the object returned from :code:`@endpoint_resource`.

    **Default Value |** :code:`None`

    **Example**

    .. code-block:: python

        class TodoDefinition(TodoResourceMixin, machinery.ResourceUpdateEndpointDefinition):
            task = field(required=True, type=str)
            priority = field(required=True, type=str)
            completion_status = field(type=bool, default=False)

            @endpoint_resource(type=Todo)
            def resource(self):
                task, created = Todo.objects.get_or_create(
                    task=self.task,
                    priority=self.priority,
                    completion_status=self.completion_status,
                )

                task._api_filter = filters.TodoResponseFilter

                return task





