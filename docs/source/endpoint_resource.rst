Endpoint Resource
==================
An endpoint resource maps to a single URL endpoint in a Django app’s urls.py. Each endpoint resource can have one or more :code:`EndpointDefinition` that implements the handler code. HTTP verbs such as :code:`POST`, :code:`GET`, along with parameters present in the request determine which :code:`EndpointDefinition` is used.


Set Up Resource Adapter
-----------------------
The default resource adapter for Django Declarative APIs is :code:`django_declarative_apis.adapters.EndpointResource`
defined in :code:`settings.py`. To use a custom resource adapter,  set :code:`DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER` to your own definition of resource adapter.

.. code-block::

    DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER = (
        "django_declarative_apis.adapters.EndpointResource")



Helper Function
----------------

.. autofunction:: django_declarative_apis.adapters.resource_adapter


EndpointResource
----------------

.. autoclass:: django_declarative_apis.adapters.EndpointResource

Authentication
~~~~~~~~~~~~~~
Authentication is tied to the resource adapter. It is the first step that a request needs to pass through. Requests will not be processed if authentication fails at this stage.

**Authentication can be set up in two places**

settings.py
    **Required |** Sets the default authenticator for the entire application. In other words, all endpoint definitions will use the authenticator defined here.

    Set :code:`DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS` to point to the authentication handler.

resource_adapter()
    **Optional |** Defines authentication handler for a specific endpoint definition. To implement, set
    :code:`authentication=<{<AuthenticatorHint>: [Authenticator]}>` in an argument to the :code:`resource_adapter()`.

    Once specified, it will override the default authentication setup in :code:`settings.py`.

    **Default Value |** :code:`None`

    *Example*

    .. code-block::

        # Define a custom NoAuth class.

        TodoEndpoint = resource_adapter(
            post=resources.TodoUpdateDefinition,
            authentication={None: (NoAuth(),)},
        )


The :code:`resource_adapter` expects the authentication handler to conform to the following configuration schema.

.. code-block::

    {
        <AuthenticatorHint>: [<Authenticator>, <Authenticator>...],
        <AuthenticatorHint>: [<Authenticator>, <Authenticator>...],
    }

* <AuthenticatorHint>
    **Required |** It is used to match Authorization headers for quick handler lookup.

    **Properties**

    * Should be defined as a :code:`<(tuple of header hints)>`
    * Must be an instance of :code:`authentication.AuthenticatorHint` or :code:`None`

    **Example**

    .. code-block::

        from django_declarative_apis.authentication import AuthenticatorHint

        SampleAuthenticatorHint = AuthenticatorHint("OAuth ")


    If there are more complexities to the authenticator, catch-alls are allowed by using a key of :code:`None`. The catch-all authenticators are always executed after matched authenticators.

    .. code-block::

        {
            None: [<Authenticator>]
        }



* <Authenticator>
    **Required |** Responsible for looking at the request and determining whether it can validate the requester.

    **Properties**

    * Should point to the implementation of the authenticator → :code:`<implementation>`
    * Must be an instance of :code:`authentication.Authenticator`

    **Example**

    .. code-block::

        from django_declarative_apis.authentication import Authenticator

        class SampleAuthenticator(Authenticator):
            # your code goes here

**Example**

For instance, if we want to use :code:`OAuth1.0a`, we could use an :code:`AuthenticatorHint.header` value of "OAuth" as a key, and :code:`[django_declarative_apis.authentication.oauthilib.oauth1.TwoLeggedOauth1()]` as value.
This will ensure that any time an ‘Authorization: OAuth ...’  header is seen, the appropriate authenticator is used. In this case, the DDA built-in :code:`TwoLeggedOauth1()` will be used.

.. code-block::

    DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS = [
    (
     (None, 'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth1Hint'),
     'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth'
     ),
    ]



Features of DDA Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: django_declarative_apis.authentication.Authenticator
   :members:


.. autoclass:: django_declarative_apis.authentication.AuthenticatorHint
   :members:

.. autoclass:: django_declarative_apis.authentication.AuthenticationResult
   :members:

.. autoclass:: django_declarative_apis.authentication.AuthenticationSuccess
   :members:

.. autoclass:: django_declarative_apis.authentication.AuthenticationFailure
   :members:

.. autoclass:: django_declarative_apis.authentication.NoAuthentication
   :members:

**Example**

.. code-block::

    SampleHint = authentication.AuthenticatorHint("SampleHint")


    class SampleAuthenticator(authentication.Authenticator):
        def is_authenticated(self, request):
            try:
                # code for authentication of the requester
                return authentication.AuthenticationSuccess()
            except Exception as error:
                # more code
                return authentication.AuthenticationFailure()



Custom Authenticator Class
--------------------------
Any authenticator class **must** be an instance of :code:`authentication.Authenticator`.

The built-in Authenticator class requires the user to override the built in :code:`is_authenticated` and :code:`challenge` methods, and write their own authentication methods. If not implemented, it will raise a :code:`NotImplementedError`.

**Example**

The NoAuth authentication handler is the minimal implementation of that interface.

.. code-block::

    class NoAuth(authentication.Authenticator):
        @staticmethod
        def is_authenticated(request):
            return True

        def challenge(self, error):
            super().challenge(error)



Built-in DDA Authenticator Based on OAuth1.0a
----------------------------------------------
The current authentication implementation is `OAuth 1.0a <https://tools.ietf.org/html/rfc5849>`_. This works well for cases where keys and secrets can be treated as secret, such as in server-to-server communication. If other methods of authentication are required, custom methods must be implemented and specified when defining URLs and their corresponding endpoints.

TwoLeggedOauth1
~~~~~~~~~~~~~~~~

.. autoclass:: django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth1
   :members:


Behavioral Routing
------------------
In DDA a single HTTP request can take multiple endpoint definitions. DDA will determine which EndpointDefinition to use depending on parameters present in the request and parameters accepted by the different endpoint definitions.

Determining whether an :code:`EndpointDefinition` can handle the request happens through an :code:`EndpointBinder`.

EndpointBinder
~~~~~~~~~~~~~~
.. autoclass:: django_declarative_apis.machinery.EndpointBinder
   :members:

The :code:`EndpointBinder` performs three important roles.

1. It checks whether all the required fields for an :code:`EndpointDefinition` are present. **If everything binds successfully and all the required fields are present, the EndpointDefinition is going to handle the request.** If there are errors and other endpoint definitions are present, then the endpoint binder will try the next endpoint definition. If all the endpoint definitions present give error then the endpoint binder will raise an error.

2. It runs the three standard validators required by the endpoint definition that checks whether the requester should have access to :code:`<endpoint>.resource()`.

    1. :code:`is_authorized()`
    2. :code:`is_permitted()`
    3. :code:`is_valid()`

3. It checks the rate limits defined in the endpoint definition, which are:

    1. :code:`rate_limit_key()`
    2. :code:`rate_limit_period()`

**Example**

.. code-block::

    post=(
            FooCreationEndpoint,
            BarCreationEndpoint,
            FooBarCreationEndpoint,
        )



Helper Functions
-----------------

.. autoclass:: django_declarative_apis.machinery.EndpointResourceAttribute
    :members:

.. autoclass:: django_declarative_apis.machinery.EndpointResponseAttribute


