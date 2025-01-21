[![Documentation Status](https://readthedocs.org/projects/django-declarative-apis/badge/?version=stable)](https://django-declarative-apis.readthedocs.io/en/stable/?badge=stable)


Overview
========

django-declarative-apis is a framework built on top of Django aimed at teams implementing RESTful APis. It provides a simple interface to define endpoints declaratively. Some benefits to using django-declarative-apis:

-   Define endpoints declaratively
-   Define model-bound and unbound resource endpoints with a consistent interface
-   OAuth 1.0a authentication out of the box
-   Define resource and endpoint-bound tasks, promoting modularity
-   Define synchronous and asynchronous tasks (asynchronous tasks implemented with Celery)
-   Separation of concerns between request body processing and business logic


Quick start
===========

This guide is intended to demonstrate the bare minimum in order to get a django-declarative-apis project up and running. The example directory contains further examples using endpoint to model relationships, authentication and response attribute filtering.

Create django app
-----------------

``` sourceCode
./manage startapp myapp
```

Add app to INSTALLED\_APPS
--------------------------

``` python
INSTALLED_APPS = [
   'django_declarative_apis',
   'myapp',
]
```

Add required config
-------------------

``` python
DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER = 'django_declarative_apis.adapters.EndpointResource'
DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS = 'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth1'
```

myapp/urls.py
-------------

``` python
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
```

myproject/myproject/urls.py
---------------------------

``` python
from django.conf.urls import url, include
import myapp.urls

urlpatterns = [
   url(r'^', include(myapp.urls)),
]
```

myapp/resources.py
------------------

``` python
from django_declarative_apis import machinery


class PingDefinition(machinery.BaseEndpointDefinition):
    def is_authorized(self):
        return True

    @property
    def resource(self):
        return {'ping': 'pong'}
```

Optional: Implement Custom Event Hooks for Event Emission
-----
```bash
# settings.py 
DDA_EVENT_HOOK = "my_app.hooks.custom_event_handler"
```