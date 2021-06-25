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

.. autoclass:: django_declarative_apis.machinery.BaseEndpointDefinition
   :members:



2. EndpointDefinition
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: django_declarative_apis.machinery.EndpointDefinition
   :members:
   :private-members:
   :show-inheritance:


3. ResourceEndpointDefinition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: django_declarative_apis.machinery.ResourceEndpointDefinition
   :members:
   :show-inheritance:

4. ResourceUpdateEndpointDefinition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: django_declarative_apis.machinery.ResourceUpdateEndpointDefinition
   :members:
   :show-inheritance:


Helper Functions
~~~~~~~~~~~~~~~~

.. autoclass:: django_declarative_apis.machinery.attributes.RawRequestObjectProperty
   :members:


.. autoclass:: django_declarative_apis.machinery.attributes.ConsumerAttribute
   :members:


.. autoclass:: django_declarative_apis.machinery.attributes.RequestAttribute
   :members:
