Resources
=========

Resources are abstract representations of underlying objects that are exposed by an API. They may or
may not be tied to a model. Using django-declarative-apis, an implementation of an
:class:`~django_declarative_apis.machinery.EndpointDefinition` is what's tied
to a specific URL in a Django app's ``urls.py``.


.. autoclass:: django_declarative_apis.machinery.EndpointDefinition
   :members:


.. autoclass:: django_declarative_apis.machinery.ResourceEndpointDefinition
   :members:

.. autoclass:: django_declarative_apis.machinery.BaseEndpointDefinition
   :members:
