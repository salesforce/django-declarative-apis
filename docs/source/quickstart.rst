Quick start
===========

This guide is intended to demonstrate the bare minimum in order to get a django-declarative-apis project up and
running. The example directory contains further examples using endpoint to model relationships, authentication and
response attribute filtering.


Create django app
-----------------

.. code-block:: shell

   ./manage startapp myapp


Add app to INSTALLED_APPS
-------------------------

.. code-block:: python

   INSTALLED_APPS = [
      'django_declarative_apis',
      'myapp',
   ]


Add required config
-------------------

.. code-block:: python

   DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER = 'django_declarative_apis.adapters.EndpointResource'
   DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS = 'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth1'



myapp/urls.py
-------------

.. code-block:: python

   from django_declarative_apis import adapters
   import myapp.resources

   class NoAuth:
      @staticmethod
      def is_authenticated(request):
         return True


   urlpatterns = [
       url(
           r'^ping$',
           adapters.resource_adapter(
               get=myapp.resources.PingDefinition,
               authentication=NoAuth
           )
       ),
   ]


myproject/myproject/urls.py
---------------------------

.. code-block:: python

   from django.conf.urls import url, include
   import myapp.urls

   urlpatterns = [
      url(r'^', include(myapp.urls)),
   ]


myapp/resources.py
------------------

.. code-block:: python

   from django_declarative_apis import machinery


   class PingDefinition(machinery.BaseEndpointDefinition):
       def is_authorized(self):
           return True

       @property
       def resource(self):
           return {'ping': 'pong'}
