Fields
======

Field
------

.. autoclass:: django_declarative_apis.machinery.attributes.RequestField
   :members:


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

.. autoclass:: django_declarative_apis.machinery.attributes.RequestUrlField
   :members:


Operations on Fields
--------------------

.. autoclass:: django_declarative_apis.machinery.attributes.RequireOneAttribute
   :members:

.. autoclass:: django_declarative_apis.machinery.attributes.RequireAllAttribute
   :members:

.. autoclass:: django_declarative_apis.machinery.attributes.RequireAllIfAnyAttribute
   :members:


