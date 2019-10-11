import logging
from pydoc import locate
from celery.task import task as celery_task
import celery
import time
from typing import NamedTuple

from django.conf import settings
from django.core.cache import cache
import django.db.models

try:
    from newrelic import agent as newrelic_agent
except ImportError:
    newrelic_agent = None

JOB_COUNT_CACHE_KEY = 'future_task_runner:job_id'
QUEUE_LENGTH_CACHE_KEY = 'future_task_runner:current_queue_length'

process_task_count = 0


def get_current_queue_length():
    return cache.get(QUEUE_LENGTH_CACHE_KEY, 0)


def _get_task_job_count():
    try:
        return cache.incr(JOB_COUNT_CACHE_KEY)
    except ValueError:
        cache.set(JOB_COUNT_CACHE_KEY, 0)
        return 0


def _log_task_stats(method_name, resource_instance_id, scheduled_execution_delay, task_creation_time,
                    task_job_count):
    global process_task_count
    process_task_count += 1
    if task_creation_time:
        now = time.time()
        scheduled_execution_time = task_creation_time + scheduled_execution_delay
        current_job_count = cache.get(JOB_COUNT_CACHE_KEY, 0)
        wait_time = now - task_creation_time
        queue_delay = now - scheduled_execution_time
        queue_length = current_job_count - task_job_count
        delivery_info = celery.current_task.request.delivery_info
        queue = delivery_info.get('exchange') or 'default'
        routing_key = delivery_info.get('routing_key') or 'default'

        cache.set(QUEUE_LENGTH_CACHE_KEY, queue_length)

        if newrelic_agent:
            newrelic_agent.record_custom_event('task_runner:queue_length',
                                               {'queue_length': queue_length,
                                                'queue': queue,
                                                'routing_key': routing_key,
                                                'wait_time_seconds': wait_time,
                                                'queue_delay_seconds': queue_delay,
                                                'process_task_count': process_task_count})

        logging.info(
            'method=%s, resource_id=%s, queue_length=%s, queue=%s, routing_key=%s, task_wait_time=%s, '
            'task_queue_delay=%s, process_task_count=%s',
            method_name, resource_instance_id,
            queue_length,
            queue,
            routing_key,
            wait_time,
            queue_delay,
            process_task_count
        )
    else:
        logging.info('method=%s, resource_id=%s', method_name, resource_instance_id)


def _log_retry_stats(method_name, resource_instance_id):
    if newrelic_agent:
        newrelic_agent.record_custom_event('task_runner:retry',
                                           {'method_name': method_name,
                                            'resource_instance_id': resource_instance_id})
        logging.warn('will retry task: method=%s, resource_id=%s', method_name, resource_instance_id)


class RetryParams(NamedTuple):
    retries_remaining: int
    retry_exception_filter: tuple
    queue: str
    routing_key: str
    countdown: int


@celery_task(ignore_results=True,
             time_limit=getattr(settings, 'DDA_DEFERRED_TASK_TIME_LIMIT', 999999),
             soft_time_limit=getattr(settings, 'DDA_DEFERRED_TASK_SOFT_TIME_LIMIT', 999999))
def future_task_runner(endpoint_class_name, endpoint_method_name, resource_class_name, resource_instance_id,
                       task_job_count=0, task_creation_time=None, scheduled_execution_delay=0, task_args=None,
                       retry_params=None):
    endpoint_class = locate(endpoint_class_name)
    resource_class = locate(resource_class_name)
    resource_instance = resource_class.objects.get(pk=resource_instance_id)
    endpoint_task = getattr(endpoint_class, endpoint_method_name)

    logged_stats = 'method={0}, resource_id={1}'.format(
        endpoint_method_name,
        resource_instance_id,
    )

    _log_task_stats(endpoint_method_name, resource_instance_id, scheduled_execution_delay, task_creation_time,
                    task_job_count)

    logging.info('future_task_runner: ' + logged_stats)

    if task_args:
        args, kwargs = task_args
    else:
        args, kwargs = [], {}

    try:
        endpoint_task.task_runner(resource_instance, *args, **kwargs)
    except Exception as e:
        if retry_params is None:
            raise

        if retry_params.retry_exception_filter\
                and not any([isinstance(e, ex_type) for ex_type in retry_params.retry_exception_filter]):
            # this exception is not retryable
            raise

        if retry_params.retries_remaining == 0:
            # out of chances
            raise

        _log_retry_stats(endpoint_method_name, resource_instance_id)
        task_runner_args = (endpoint_class_name, endpoint_method_name, resource_class_name, resource_instance_id)
        task_runner_kwargs = {
            'task_creation_time': time.time(),
            'scheduled_execution_delay': scheduled_execution_delay,
            'task_args': (args, kwargs),
        }
        schedule_future_task_runner(
            task_runner_args,
            task_runner_kwargs,
            retries=retry_params.retries_remaining-1,
            countdown=retry_params.countdown * 2 or 1,
            queue=retry_params.queue,
            routing_key=retry_params.routing_key,
        )


def schedule_future_task_runner(task_runner_args, task_runner_kwargs,
                                retries=0,
                                retry_exception_filter=(),
                                queue=None,
                                routing_key=None,
                                countdown=0,
                                delay=0):
    task_runner_kwargs['task_job_count'] = _get_task_job_count()
    task_runner_kwargs['retry_params'] = RetryParams(retries_remaining=retries,
                                                     retry_exception_filter=retry_exception_filter,
                                                     queue=queue,
                                                     routing_key=routing_key,
                                                     countdown=countdown)
    future_task_runner.apply_async(task_runner_args, task_runner_kwargs, queue=queue, routing_key=routing_key, countdown=countdown+delay)


@celery_task(ignore_results=True,
             time_limit=getattr(settings, 'DDA_DEFERRED_TASK_TIME_LIMIT', 999999),
             soft_time_limit=getattr(settings, 'DDA_DEFERRED_TASK_SOFT_TIME_LIMIT', 999999))
def resource_task_runner(resource_class_name, resource_method_name, resource_instance_id,
                         task_job_count=0, task_creation_time=None, scheduled_execution_delay=0, task_args=None):
    resource_class = locate(resource_class_name)
    resource_instance = resource_class.objects.get(pk=resource_instance_id)
    resource_method = getattr(resource_instance, resource_method_name)

    _log_task_stats("{0}.{1}".format(resource_class_name, resource_method_name),
                    resource_instance_id,
                    scheduled_execution_delay,
                    task_creation_time,
                    task_job_count)
    if task_args:
        args, kwargs = task_args
    else:
        args, kwargs = [], {}

    resource_method(*args, **kwargs)


def schedule_resource_task_runner(resource_bound_method,
                                  task_args=None,
                                  task_kwargs=None,
                                  queue=None,
                                  routing_key=None,
                                  delay=0):
    resource = resource_bound_method.__self__
    assert isinstance(resource, django.db.models.Model), \
        "resource must be an instance of django.db.models.Model to run as deferred task"

    resource_class_name = '{0}.{1}'.format(resource.__module__, resource.__class__.__name__)
    resource_id = resource.pk

    task_runner_args = (resource_class_name, resource_bound_method.__name__, str(resource_id))
    task_runner_kwargs = {
        'task_creation_time': time.time(),
        'scheduled_execution_delay': delay,
        'task_args': (task_args or (), task_kwargs or {}),
        'task_job_count': _get_task_job_count(),
    }

    resource_task_runner.apply_async(task_runner_args,
                                     task_runner_kwargs,
                                     queue=queue,
                                     routing_key=routing_key)
