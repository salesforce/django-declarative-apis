Quick start
===========

Create django app
-----------------

``` sourceCode
./manage startapp myapp
```

myapp/urls.py
-------------

``` sourceCode
from django_declarative_apis import adapters
import myapp.resources

urlpatterns = [
    url(
        r'^users$',
        adapters.resource_adapter(
            get=myapp.resources.UserListDefinition,
            post=myapp.resources.UserCreateDefinition
        )
    ),
    url(
        r'^ping$',
        adapters.resource_adapter(
            get=myapp.resources.PongDefinition
        )
    ),
]
```

myapp/resources.py
------------------

``` sourceCode
from django_declarative_apis import machinery


class PongDefinition(machinery.EndpointDefinition):
    """ Example of an endpoint not tied to a model
    """
    def is_authorized(self):
        return True

    @property
    def resource(self):
        return {'ping': 'pong'}


class UserListDefinition(machinery.ResourceEndpointDefinition):
    """ Example of a get/list endpoint tied to a model
    """
    resource_model = modes.User

    def is_authorized(self):
        return True


class UserCreateDefinition(machinery.ResourceEndpointDefinition):
    """ Example of a create endpoint tied to a model
    """
    resource_model = models.User

    def is_authorized(self):
        return True
```

myapp/models.py
---------------

``` sourceCode
from django.db import models


class User(models.Model):
    name = models.CharField(max_length=100, null=False)
```
