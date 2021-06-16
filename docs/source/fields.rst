Fields
======

Field
------
Endpoint properties are called fields. Fields can be simple types such as int , or they can be used as a decorator on a function.

**Valid field types:** :code:`int`, :code:`bool`, :code:`float`, :code:`str`, :code:`dict`, :code:`complex`

**Example**

.. code-block:: python

    from django-declarative-apis.machinery import field

    task = field(required=True, type=str)

**Parameters**

:code:`required`
    **Optional |** Determines whether the field is required for the EndpointDefinition.

    **Default Value |**  :code:`True`

:code:`name`
    **Optional |** Allows the name of the field in HTTP API to be different from its name defined on the EndpointDefinition

    **Default Value |** :code:`None`

:code:`type`
    **Optional |** Determines the type of the field. Type needs to be on of the *valid field types* listed above.
    **Default Value |** :code:`String`

:code:`default`
    **Optional |** Sets the default value for the field.
    **Default Value |** :code:`None`

:code:`description`
    **Optional |** Describes the purpose of the field.
    **Default Value |** :code:`None`

:code:`multivalued`
    **Optional |** Allows a field to to be specified multiple times in the request. With multivalued set to True , the EndpointHandler will receive a list of values instead of a single value.

    **Default Value |** :code:`False`

    **Example**

    Request:

    .. code-block::

        GET https://example.com?foo=bar1&foo=bar2

    EndpointDefinition:

    .. code-block:: python

        from django-declarative-apis.machinery import field

        class FooDefinition(EndpointDefinition):
            foo = field(multivalued=True)


    In the :code:`EndpointDefintion`, :code:`self.foo` would be equal to ['bar1', 'bar2']


Field as decorators on a function
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Define fields as a decorator on a function when you want to perform operations on the data before returning it and using it in your :code:`EndpointDefinition`.

The function will have :code:`@field` decorator at the top. Once the :code:`type=<type>` argument of :code:`@field` decorator is set, that is going to be the type of the input to the field function.

**Example:**
Let’s say the only acceptable status for a task in todo list is True

.. code-block:: python

   @field(
        required=False,
        name='completion_status',
        type=bool,
        default=None,
        description='Status for a task in the todo list. The only valid status is "True"')
    def status(self, raw_value):
       if status.get(raw_value, None) != True:
            raise ValueError(f"{raw_value} is not a valid status")
       return True






URL Field
---------
It is a specialized form of field that takes any parameter that directly appears in the URL path.

**Parameters**

:code:`name`
    **Optional |** Allows the name of the field in HTTP API to be different from its name defined on the EndpointDefinition

    **Default Value |** :code:`None`

**Example:**
URL defined in :code:`urls.py`

.. code-block:: python

    url_patterns = [
        url(
            r"^tasks/(?P<id>{0})/$".format(r"[0-9]{1}"),
            handlers.TodoDetailEndpoint,
            )
    ]

:code:`url_field` is used to extract the id of a single task from the above URL for deleting that task.

.. code-block:: python

    from django-declarative-apis.machinery import url_field

    class TodoDeleteSingleTaskDefinition(TodoResourceMixin, machinery.ResourceEndpointDefinition):
        resource_id = url_field(name='id')

        @endpoint_resource(type=Todo)
        def resource(self):
            task = Todo.objects.delete(id=self.resource_id)
            return django.http.HttpResponse(status=http.HTTPStatus.OK)




Operations on Fields
--------------------

:code:`require_one`
    Exactly one of the given fields must be present.

    **Example**

    .. code-block:: python

        from django-declarative-apis.machinery import require_one

        sample_field_1 = field()
        sample_field_2 = field()

        sample_require_one = require_one(
                sample_field_1,
                sample_field_2,
            )


:code:`require_all`
    All fields must be populated.


:code:`require_all_if_any`
    Either all fields must be present or all fields must be missing.

