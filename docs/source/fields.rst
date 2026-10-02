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

   from django_declarative_apis.machinery import EndpointDefinition, field

   class CompleteTask(EndpointDefinition):
       @field(
           required=False,
           name="completion_status",
           type=bool,
           default=None,
           description='Status for a task in the todo list. The only valid status is "True"',
       )
       def status(self, value):
           if value is None:
               return None
           if value is not True:
               raise ValueError(f"{value} is not a valid status")
           return value

The function receives the value after boolean conversion, so it can check the
value directly. Return :code:`None` for a missing optional value, and reject
:code:`False`. No separate status lookup dictionary is needed.

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


