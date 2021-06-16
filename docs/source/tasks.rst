Tasks
=====

Task
------------
:code:`task` is used as a decorator on a function. It encapsulate the side-effect operations of an endpoint. For instance, if hitting an endpoint causes an operation to happen in another resource or it causes an operation to be queued and run as a background task.

:code:`task` runs **synchronously**, which means it will be executed before the response is returned to the user. It can also affect the response by making changes to the :code:`EndpointDefinition.resource()`.


**Example**

.. code-block:: python

    from django-declarative-apis import task

    class SampleClass:
        # code

        @task
        def sample_function():
            # your code goes here


**Parameters**

:code:`task_runner`
    **Optional |** It is a callable that dictates how the task is executed.

    **Default Value |** :code:`None`

:code:`depends_on`
    **Optional |** It is a reference to another task that should be run before this one.  Overrides priority.

    **Default Value |** :code:`None`

    .. note::
        **Important:** :code:`deferrable_task` cannot be used as a depends_on argument.

:code:`priority`
    **Optional |** Specifies the priority of the task. Tasks with lower priority are executed first.

    **Default Value |** :code:`0`

**Example**

.. code-block:: python

    from django-declarative-apis import task

    class SampleEndpointDefinition:
       def is_authorized(self):
         return True

       @task
       def set_response_filter(self):
            self.response._api_filter = filters.SampleFilters




Deferrable Task
---------------

:code:`deferrable_task` is used as a decorator on a function. It is similar to :code:`task` in that it encapsulates side-effects, but can be automatically executed in a deferred queue outside of the request-response cycle.

:code:`deferrable_task` runs **asynchronously** and because of that it is used for operations that take time and when we want to avoid delaying the response to the user.

**Deferrable Task Rules**:

* Deferrable task methods must always be a :code:`staticmethod`. Therefore, anything a deferrable task needs to know should be saved in the :code:`EndpointDefinition.resource()`.
* The :code:`staticmethod` decorator should come after :code:`deferrable_task` decorator.

    .. code-block:: python

      from django-declarative-apis import deferrable_task

      class SampleClass:
        # code

        @deferrable_task
        @staticmethod
        def sample_method(arg):
           # your code goes here
* Works only with a Django Model instance as the resource
* String name for how to locate this static method.


**Parameters**

.. note::
    Depending on the parameters used, a deferrable task can be run in different time intervals. In some cases, it can be made to run synchronously.

:code:`task_runner`
    **Optional |** It is a callable that dictates how the task is executed.

    **Default Value |** :code:`None`

:code:`delay`
    **Optional |** Sets the delay in seconds before running the task. Requires :code:`always_defer=True.`

    **Default Value |** :code:`None`

:code:`always_defer`
    **Optional |** Runs task in deferred queue even when :code:`delay=0.`

    **Default Value |** :code:`False`

:code:`task_args_factory`
    **Optional |** Stores task args and kwargs. :code:`task_args_factory` must be a **callable**.

    **Default Value |** :code:`None`

:code:`queue`
    **Optional |** Sets the celery queue that will be used for storing the tasks.

    **Default Value |** :code:`None`

:code:`routing_key`
    **Optional |** It is used to determine which queue the task should be routed to.

    **Default Value |** :code:`None`

:code:`retries`
    **Optional |** Specifies the number of times the current task has been retried.

    **Default Value |** :code:`0`

:code:`retry_exception_filter`
    **Optional |** It is used to store retry exception information that is used in logs.

    **Default Value |** :code:`()` - empty tuple

:code:`execute_unless`
    **Optional |** Execute the task unless a condition is met. It must be a **callable**.

    **Default Value |** None

**Example**

.. code-block:: python

    from django-declarative-apis import deferrable_task

    class SampleClass:
        # code

        @deferrable_task(execute_unless=<condition>)
        @staticmethod
        def sample_method(arg):
            # your code goes here



Django Config Settings Related to Tasks
----------------------------------------

:code:`DDA_DEFERRED_TASK_TIME_LIMIT`
    Sets a time limit on a task using Celery time limits.

    **Default Value |** :code:`999999` — maximum number of seconds to run the task.

:code:`DDA_DEFERRED_TASK_SOFT_TIME_LIMIT`
    Sets a time limit on a task using Celery soft time limits.

    **Default Value |** :code:`999999` — maximum number of seconds to run the task.

:code:`DECLARATIVE_ENDPOINT_TASKS_FORCE_SYNCHRONOUS`
    Determines whether endpoint tasks should be forced to run synchronously.

    **Default Value |** :code:`False`

:code:`DECLARATIVE_ENDPOINT_TASKS_SYNCHRONOUS_FALLBACK`
    Determines whether endpoint task should be falling back to executing task synchronously.

    **Default Value |** :code:`False`
