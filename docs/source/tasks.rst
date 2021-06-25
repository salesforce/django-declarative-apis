Tasks
=====

.. autoclass:: django_declarative_apis.machinery.attributes.EndpointTask
   :members:


Deferrable Task
---------------

.. autoclass:: django_declarative_apis.machinery.attributes.DeferrableEndpointTask
    :members:



Django Config Settings Related to Tasks
----------------------------------------

DDA_DEFERRED_TASK_TIME_LIMIT
    Sets a time limit on a task using Celery time limits.

    **Default Value |** :code:`999999` — maximum number of seconds to run the task.

DDA_DEFERRED_TASK_SOFT_TIME_LIMIT
    Sets a time limit on a task using Celery soft time limits.

    **Default Value |** :code:`999999` — maximum number of seconds to run the task.

DECLARATIVE_ENDPOINT_TASKS_FORCE_SYNCHRONOUS
    Determines whether endpoint tasks should be forced to run synchronously.

    **Default Value |** :code:`False`

DECLARATIVE_ENDPOINT_TASKS_SYNCHRONOUS_FALLBACK
    Determines whether endpoint task should be falling back to executing task synchronously.

    **Default Value |** :code:`False`
