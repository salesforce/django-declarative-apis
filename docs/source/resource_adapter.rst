Endpoint Resource
==================
A endpoint resource maps to a single URL endpoint in a Django app’s urls.py. Each endpont resource can have one or more :code:`EndpointDefinition` that implements the handler code. HTTP verbs such as :code:`POST`, :code:`GET`, along with parameters present in the request determine which :code:`EndpointDefinition` is used.


Set Up Resource Adapter
-----------------------
The default resource adapter for Django Declarative APIs is :code:`django_declarative_apis.adapters.EndpointResource`
defined in :code:`settings.py`. To use a custom resource adapter,  set :code:`DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER` to your own definition of resource adapter.

.. code-block::

    DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER = (
        "django_declarative_apis.adapters.EndpointResource")



Helper Function
----------------
:code:`resource_adapter()` is a helper function that finds the endpoint resource adapter from settings.py and calls that resource adapter.

**resource_adapter takes two arguments:**

Handler/Resource
    **Required |** The :code:`EndpointDefinition` implementation along with an HTTP verb.

Authentication Handler
    **Optional |** If not specified, :code:`OAuth1.0a` will be used by default.

    **Example:**
    Handler defined in a separate file named handlers.py

    .. code-block::

        TodoEndpoint = resource_adapter(
            post=resources.TodoUpdateDefinition,
            get=resources.TodoDefinition,
            authentication={None: (NoAuth(),)},
        )

    Django app’s urls.py

    .. code-block::

        url(
            r"^tasks/$",
            handlers.TodoEndpoint,
        )



EndpointResource
----------------
:code:`EndpointResource` is the DDA default resource adapter. It validates the configuration of the authentication handler, and in combination with Django’s native urls.py routes requests (through behavioral routing) to the same URL but to different handlers based on request attributes.


Authentication
~~~~~~~~~~~~~~
Authentication is tied to the resource adapter. It is the first step that a request needs to pass through. Requests will not be processed if authentication fails at this stage.

**Authentication can be set up in two places**

:code:`settings.py`
    **Required |** Sets the default authenticator for the entire application. In other words, all endpoint definitions will use the authenticator defined here.

    Set :code:`DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS` to point to the authentication handler.

:code:`resource_adapter()`
    **Optional |** Defines authentication handler for a specific EndpointDefinition. To implement, set
    :code:`authentication=<{<AuthenticatorHint>: [Authenticator]}>` in an argument to the :code:`resource_adapter()`.

    Once specified, it will override the default authentication set up in settings.py

    **Default Value |** :code:`None`

    *Example*

    .. code-block::

        # Define a custom NoAuth class.

        TodoEndpoint = resource_adapter(
            post=resources.TodoUpdateDefinition,
            authentication={None: (NoAuth(),)},
        )


The resource_adapter expects the authentication handler to conform to the following configuration schema.

.. code-block::

    {
        <AuthenticatorHint>: [<Authenticator>, <Authenticator>...],
        <AuthenticatorHint>: [<Authenticator>, <Authenticator>...],
    }

* :code:`<AuthenticatorHint>`
    **Required |** It is used to match Authorization headers for quick handler lookup.

    **Properties**

    * Should be defined as a :code:`<(tuple of header hints)>`
    * Must be an instance of :code:`authentication.AuthenticatorHint` or :code:`None`

    **Example**

    .. code-block::

        from django_declarative_apis.authentication import AuthenticatorHint

        SampleAuthenticatorHint = AuthenticatorHint("OAuth ")


    If there are more complexities to the authenticator, catch-alls are allowed by using a key of None. The catch-all authenticators are always executed after matched authenticators.

    .. code-block::

        {
            None: [<Authenticator>]
        }



* :code:`<Authenticator>`
    **Required |** Responsible for looking at the request and determining whether it can validate the requester.

    **Properties**

    * Should point to the implementation of the authenticator → :code:`<implementation>`
    * Must be an instance of :code:`authentication.Authenticator`

    **Example**

    .. code-block::

        from django_declarative_apis.authentication import Authenticator

        class SampleAuthenticator(*Authenticator*):
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

:code:`Authenticator`
    The base class for constructing an authenticator.

    The Authenticator class has two methods: :code:`is_authenticated` and :code:`challenge`. Both of these need to be overridden by the authenticator implementation that inherits from :code:`Authenticator` class. Otherwise, it will throw a :code:`NotImplementedError`.

    **Methods**

    :code:`is_authenticated(request)`
        Takes in the request as an argument and identifies whether the requester is valid.

    :code:`challenge(error)`
        Results in the challenge response sent to the user. This should result in a django.http.HttpResponse that should include information through the :code:`WWW-Authenticate` header around expectations.

    **Example**

    .. code-block::

        from django_declarative_apis.authentication import Authenticator

        class SampleAuthenticator(Authenticator):
            def is_authenticated(request):
                # authentication code

            def challenge(self, error):
                # challenge code


:code:`AuthenticatorHint`
    Takes a tuple to provide hints for authentication implementations

    **Import**

    .. code-block::

        from django_declarative_apis.authentication import AuthenticatorHint


:code:`AuthenticationResult`
    A class definition that take in and stores the authentication header and detail of the result.

    **Arguments**

    :code:`detail`
        **Defualt Value |** :code:`None`

    :code:`auth_header`
        **Default Value |** :code:`None`

    **Import**

    .. code-block::

        from django_declarative_apis.authentication import AuthenticationResult



:code:`AuthenticationSuccess`
    It is an instance of :code:`AuthenticationResult` and returns :code:`True`. It can be used as a return response in an authenticator implementation.

    **Import**

    .. code-block::

        from django_declarative_apis.authentication import AuthenticationSuccess



:code:`AuthenticationFailure`
    It is an instance of :code:`AuthenticationResult` returns :code:`False`. It can be used as a return response in an authenticator implementation.

    **Import**

    .. code-block::

        from django_declarative_apis.authentication import AuthenticationFailure



:code:`NoAuthentication`
    It is an authentication handler that always returns :code:`True`, so no authentication is needed.

    .. note::
        **Important:** In this implementation the challenge method is missing and must be implemented by the user. Otherwise, it will raise NotImplementedError.

    **Import**

    .. code-block::

        from django_declarative_apis.authentication import NoAuthentication

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

The built-in Authenticator class requires the user to override the built in :code:`is_authenticated` and :code:`challenge methods`, and write their own authentication methods. If not implemented, it will raise a :code:`NotImplementedError`.

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
**Methods**

:code:`validate_missing_parameters`
    Ensures that the request contains all required parameters. Otherwise, raises a Parameters absent error.

    **Required Parameters**
    :code:`oauth_consumer_key`
    :code:`oauth_nonce`
    :code:`oauth_signature`
    :code:`oauth_signature_method`
    :code:`oauth_timestamp`

:code:`is_authenticated`
    Authenticates the requester using OAuth1.0a

:code:`authenticate_header`
    Returns the authentication header. If it does not exist, returns "Unknown OAuth Error"

:code:`challenge`
    Returns a 401 response with a some information on what OAuth is, and where to learn more about it.



Behavioral Routing
------------------
In DDA a single HTTP request can take multiple endpoint definitions. DDA will determine which EndpointDefinition to use depending on parameters present in the request and parameters accepted by the different endpoint definitions.

Determining whether an :code:`EndpointDefinition` can handle the request happens through an :code:`EndpointBinder`.

EndpointBinder
~~~~~~~~~~~~~~
The :code:`EndpointBinder` checks whether all the required fields for an :code:`EndpointDefinition` are present. **If everything binds successfully and all the required fields are present, the EndpointDefinition is going to handle the request.** If there are errors and other endpoint definitions are present, then the endpoint binder will try the next endpoint definition.

If there is one endpoint definition, or all endpoint definitions present give error then the endpoint binder will raise an error.

**Example**

.. code-block::

    post=(
            FooCreationEndpoint,
            BarCreationEndpoint,
            FooBarCreationEndpoint,
        )



Helper Functions
-----------------

:code:`endpoint_resource` decorator
    It is used as a decorator on a resource function. It specifies the attributes of that resource.

    **Parameters**

    :code:`type=<type>`
        **Required |** Specifies the model type. It is used only for documentation generation purposes.

    :code:`filter=<filter>`
        **Optional |** Defines the class filters. Overrides the default filters.

        **Default Value |** :code:`None`

    :code:`returns_list=<returns_list>`
        **Optional |** It is used for documentation generation purposes.

        **Default Value |** :code:`False`

    **Example**

    .. code-block::

        class TodoSingleTaskDefinition(TodoResourceMixin, machinery.ResourceEndpointDefinition):
            resource_id = url_field(name='id')  # grabs the id from url

            @endpoint_resource(type=Todo)
            def resource(self):
                return Todo.objects.get(id=self.resource_id)


:code:`endpoint_response` decorator
    It is used as a decorator on a response function. It specifies the attributes of the response.

    **Parameters**

    :code:`type=<type>`
        **Required |** Specifies the response type, which can be dictionary, list, or model type. It is used only for documentation generation purposes.

    :code:`filter=<filter>`
        **Optional |** Defines the class filters. Overrides the default filters.
        **Default Value |** :code:`None`

    **Example**

    .. code-block::

        @endpoint_response(type=dict)
        def response(self):
            return http.status.OK

