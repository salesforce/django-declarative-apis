Quick Start
===========
We are going to create a simple todo app that can only add tasks to a todo list.

Project Setup
--------------
Create a new project named dda_project and a new app called todo.

.. code-block::

    # create a new project directory
    mkdir dda_todo_app
    cd dda_todo_app

    # create a virutal environment
    python -m venv env
    source env/bin/activate

    # install django
    pip install django

    # create a new project
    django-admin startproject dda_project
    cd dda_project

    # create a new app
    python manage.py startapp todo
    cd ..

Install django-declarative-apis
--------------------------------
Clone django-declarative-apis repository.

.. code-block::

    git clone https://github.com/salesforce/django-declarative-apis.git


Django Config Settings Setup
------------------------------
Add the todo app and django-declarative-apis to the list of installed apps in :code:`settings.py`.

.. code-block::

    INSTALLED_APPS = ['django_declarative_apis','todo',]

Add the DDA required configuration to :code:`settings.py`.

.. code-block::

    # This will be used later in the process to find the correct EndpointResource.
    # The EndpointResource is responsible for authentication and routing of the requests.
    DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER = (
        "django_declarative_apis.adapters.EndpointResource"
    )

    # The authentication handler is used by endpoint resource to authenticate the requester.
    DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS = [
    (
     (None, 'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth1Hint'),
     'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth'
     ),
    ]

    # This will be the default filters that will applied to all the endpoint definitions' responses
    DECLARATIVE_ENDPOINT_DEFAULT_FILTERS = "todo.filters.TodoResponseFilter"



Models Setup
-------------
Let’s set up a Todo model in :code:`todo/models.py`.

.. code-block::

    from django.db import models

    class Todo(models.Model):
        task                = models.CharField(max_length=255, null=False)
        priority            = models.CharField(max_length=255)
        created_date        = models.DateTimeField(auto_now_add=True)
        completion_status   = models.BooleanField(default=False)

        def __str__(self):
            return f"{self.task}"



Filters Setup
---------------

Let’s set up filters in :code:`todo/filters.py` that will decide the format of the API response.

.. code-block::

    from django_declarative_apis.machinery import filtering
    from .models import Todo

    TodoResponseFilter = {
        Todo: {
            'task': filtering.ALWAYS,
            'priority': filtering.ALWAYS,
            'created_date': filtering.ALWAYS,
            'completion_status': filtering.ALWAYS
        },
    }



URLs
------
Let’s set up the URLs in :code:`todo/urls.py`.

.. code-block::

    from django.conf.urls import url

    urlpatterns = [
           url(
            r"^tasks/$",
            post=resource_adapter(post=resources.TodoUpdateDefinition,)
            ),
    ]

**The important points to note here:**

1. :code:`resource_adapter` is a helper function that will look into Django’s config settings and find the endpoint resource adapter to call. In our case, :code:`DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER` is set to :code:`EndpointResource`, which is the endpoint resource that will be called.


2. :code:`EndpointResource` will perform:
    1. Authentication configuration check.
    2. Endpoint binding, which means routing the request to an endpoint definition based on the **HTTP verb** used and the **required parameters** accepted by the endpoint definition.
    3. The endpoint binder then executes the authentication checks defined in the endpoint definition, which are :code:`is_authorized`, :code:`is_permitted`, and :code:`is_valid`.


3. Once the endpoint binding is successful, the request will be routed to the endpoint definition that can handle it. In our case it will be routed to :code:`resources.TodoUpdateDefinition`.

.. note::
    All of the above-mentioned operations will be handled by the framework and will run in the background.


Resources Setup
----------------
Let’s set up our endpoint definition in a new file named :code:`todo/resources.py`. The endpoint definition is :code:`TodoUpdateDefinition` that will be used to create a new a task in the todo list.

.. code-block::

    from django_declarative_apis import machinery
    from django_declarative_apis.machinery import field, endpoint_resource
    from .models import Todo


    class TodoResourceMixin:
        consumer = None
        _consumer_type = None

        def is_authorized(self):
            return True

    class TodoUpdateDefinition(TodoResourceMixin, machinery.ResourceUpdateEndpointDefinition):
        task = field(required=True, type=str)
        priority = field(required=True, type=str)
        completion_status = field(type=bool, default=False)

        @endpoint_resource(type=Todo)
        def resource(self):
            task, created = Todo.objects.get_or_create(
                task=self.task,
                priority=self.priority,
                completion_status=self.completion_status,
            )
            return task

**The important points to note here:**

1. Once the authentication and binding are successfully completed, the framework will run :code:`TodoUpdateDefinition.resource()`, which will refer to the fields.

2. fields will process the request data.

    .. note::
        If :code:`aggregates` and :code:`tasks` are present, the framework will also be process those in this stage.

3. By default DDA calls :code:`TodoUpdateDefinition.response`, which returns :code:`TodoUpdateDefinition.resource` as the response of the endpoint.

    .. note::
        The default response can be overridden.


4. The format of the response will be determined by filters.


.. note::
    All of the above-mentioned operations will be handled by the framework and will run in the background.
