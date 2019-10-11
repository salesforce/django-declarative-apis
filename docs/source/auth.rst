Authentication & authorization
==============================

The current authentication implementation is `OAuth 1.0a`_. It's important to note that at the time of writing, only
the `1-legged OAuth`_ is supported. This works well for cases where keys and secrets can be treated as secret, such
as in server-to-server communication. If other methods of authentication are required, custom methods must be
implemented and specified when defining URLs and their corresponding endpoints.


Consumer authentication
-----------------------

At the root of authentication & authorization is the consumer. The existence of a consumer gives us the ability to
verify that the user exists, that we can authenticate the request by OAuth 1.0a signature. Then using this information,
each endpoint can dictate whether or not a given consumer has access to a requested resource as necessary for each
resource.

By default, :class:`~django_declarative_apis.models.OauthConsumer` is used. However, this can be overridden with the
``DECLARATIVE_ENDPOINT_CONSUMER_GETTER`` Django config setting. This must be implemented as a function that takes a
single parameter (key).

.. autoclass:: django_declarative_apis.models.OauthConsumer
   :members:

Consumer creation is straightforward. If unspecified, key and secrets are auto-generated:

.. code-block:: shell

   In [1]: from django_declarative_apis import models
   In [2]: consumer = models.OauthConsumer.objects.create(name='test_user')
   In [3]: consumer.__dict__
   Out[3]:
   {
    'content_type_id': None,
    'id': 1,
    'key': 'j5wPDAvtYsArfZ5Lo5',
    'name': 'test_user',
    'object_id': None,
    'secret': 'FM3wNWMj34JmzqFFRzPwe3QvOjE9X4Xu',
    'type': 'RW'
    }


.. _`OAuth 1.0a`: https://tools.ietf.org/html/rfc5849
.. _`1-legged OAuth`: http://oauthbible.com/#oauth-10a-one-legged



Endpoint authorization
----------------------

Consumers are authenticated automatically when using any endpoint definition class that derives from 
:class:`~django_declarative_apis.machinery.EndpointDefinition`. Rudimentary authorization (read-only vs read-write)
is implemented as well. If an endpoint is defined as ``is_read_only = False`` and a consumer has been created
with ``consumer.type = OauthConsumer.TYPE_READ_ONLY``, the request will be rejected.

If more complex logic is required (i.e. the resource belongs to the requesting consumer), ``is_authorized(self)`` can
be overridden:

.. code-block:: python

   from django_declarative_apis import machinery


   class MyEndpointDefinition(machinery.EndpointDefinition):
      def is_authorized(self):
         return self.request.consumer.id == self.resource.owner_id
