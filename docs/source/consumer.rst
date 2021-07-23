Consumer
========

Consumer Authentication
------------------------
At the root of authentication & authorization is the consumer. The existence of a consumer gives us the ability to verify that the user exists, that we can authenticate the request by OAuth 1.0a signature. Then using this information, each endpoint can dictate whether or not a given consumer has access to a requested resource as necessary for each resource.
By default, *OauthConsumer* is used. However, this can be overridden with the :code:`DECLARATIVE_ENDPOINT_CONSUMER_GETTER` Django config setting. This must be implemented as a function that takes a single parameter (key).
Consumer creation is straightforward. If unspecified, key and secrets are auto-generated:

 .. code-block::

    In [1]: from django_declarative_apis import models
    In [2]: consumer = models.OauthConsumer.objects.create(name='test_user')
    In [3]: consumer.__dict__
    Out[3]:{'content_type_id': None,
     'id': 1,
     'key': 'j5wPDAvtYsArfZ5Lo5',
     'name': 'test_user',
     'object_id': None,
     'secret': 'FM3wNWMj34JmzqFFRzPwe3QvOjE9X4Xu',
     'type': 'RW'}


Endpoint Authorization
----------------------
Consumers are authenticated automatically when using any endpoint definition class that derives from :code:`EndpointDefinition`. Rudimentary authorization (read-only vs read-write) is implemented as well. If an endpoint is defined as :code:`is_read_only = False` and a consumer has been created with :code:`consumer.type = OauthConsumer.TYPE_READ_ONLY`, the request will be rejected.
If more complex logic is required (i.e. the resource belongs to the requesting consumer), is_authorized(self) can be overridden.

**Example**

.. code-block:: python

    from django_declarative_apis import machinery

    class MyEndpointDefinition(machinery.EndpointDefinition):
        def is_authorized(self):
            return self.request.consumer.id == self.resource.owner_id



BaseConsumer
------------
.. autoclass:: django_declarative_apis.models.BaseConsumer
   :members:

OAuthConsumer
-------------

.. autoclass:: django_declarative_apis.models.OauthConsumer
   :members:
   :show-inheritance:


Django Config Settings Related to Consumer
--------------------------------------------
DECLARATIVE_ENDPOINT_CONSUMER_GETTER
    Tries to get the consumer using the provided primary key. Should point to :code:`consumer_getter` function defined by the developer.
