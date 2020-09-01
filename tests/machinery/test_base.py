#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import http
import json
import unittest

import django.core.exceptions
import django.test
import kombu.exceptions
import mock
from django.core.cache import cache
from django.http import HttpRequest

import tests.models
from django_declarative_apis import machinery, models as dda_models
from django_declarative_apis.machinery import errors, filtering, tasks
from django_declarative_apis.machinery.tasks import future_task_runner
from django_declarative_apis.resources.utils import HttpStatusCode
from tests import testutils

_TEST_RESOURCE = {"foo": "bar"}


class EndpointResourceAttributeTestCase(
    testutils.RequestCreatorMixin, unittest.TestCase
):
    def test_call(self):
        attrib = machinery.EndpointResourceAttribute(str)
        self.assertEqual(attrib(lambda: "foo"), attrib)

    def test_get_instance_value(self):
        attrib = machinery.EndpointResourceAttribute(str)
        self.assertEqual(attrib.get_instance_value(None, None), attrib)

    def test_get_instance_value_dict(self):
        expected_resource = {"foo": "bar"}

        class _TestEndpoint(machinery.EndpointDefinition):
            @machinery.endpoint_resource(type=dict)
            def resource(self):
                return expected_resource

        endpoint = _TestEndpoint()
        self.assertEqual(endpoint.resource, expected_resource)

    def test_get_instance_value_custom_type(self):
        class _TestResource:
            pass

        expected_resource = _TestResource()

        class _TestEndpoint(machinery.EndpointDefinition):
            @machinery.endpoint_resource(type=_TestResource)
            def resource(self):
                return expected_resource

        endpoint = _TestEndpoint()
        res = endpoint.resource
        self.assertIsInstance(res, _TestResource)
        # attribute should be set in get_instance_value
        self.assertEqual(res._api_filter, None)

    def test_get_instance_value_instance_not_found(self):
        class _TestErrorEndpoint(machinery.EndpointDefinition):
            @machinery.endpoint_resource(type=dict)
            def resource(self):
                raise django.core.exceptions.ObjectDoesNotExist

        endpoint = _TestErrorEndpoint()

        try:
            endpoint.resource
            self.fail("This should have failed")
        except errors.ClientErrorNotFound as err:
            self.assertEqual(err.error_code, http.HTTPStatus.NOT_FOUND)
            self.assertEqual(err.error_message, "Not Found : dict instance not found")
            self.assertEqual(err.status_code, http.HTTPStatus.NOT_FOUND)
            self.assertFalse(err.save_changes)
            self.assertEqual(err.extra_fields, {})


class EndpointResponseAttributeTestCase(
    testutils.RequestCreatorMixin, unittest.TestCase
):
    def test_call(self):
        attr = machinery.EndpointResponseAttribute(str)
        self.assertEqual(attr.get_instance_value(None, None), attr)

    def test_instance_value(self):
        expected_response = {"foo": "bar"}

        class _TestEndpoint(machinery.EndpointDefinition):
            @machinery.endpoint_response(type=dict)
            def response(self):
                return expected_response

        endpoint = _TestEndpoint()
        self.assertEqual(endpoint.response, expected_response)

    def test_instance_value_with_filter(self):
        class _TestResource:
            def __init__(self, name, secret):
                self.name = name
                self.secret = secret

        expected_response = _TestResource(name="foo", secret="bar")
        obj_filter = {"name": filtering.ALWAYS, "secret": filtering.NEVER}

        class _TestEndpoint(machinery.EndpointDefinition):
            @machinery.endpoint_response(type=dict, filter=obj_filter)
            def response(self):
                return expected_response

        endpoint = _TestEndpoint()
        resp = endpoint.response

        self.assertIsInstance(resp, _TestResource)
        self.assertEqual(resp._api_filter, obj_filter)


class EndpointBinderTestCase(django.test.TestCase):
    @mock.patch("django_declarative_apis.machinery.logger")
    def test_get_response_with_non_client_error(self, mock_logging):
        class _TestException(Exception):
            pass

        class _TestEndpoint(machinery.EndpointDefinition):
            @property
            def resource(self):
                return {}

        endpoint = _TestEndpoint()
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )
        manager.binding_exc_info = (
            _TestException,
            _TestException("something bad happened"),
            None,
        )
        self.assertRaises(_TestException, manager.get_response)
        mock_logging.error.assert_called_with("('something bad happened',)\nNone")

    def test_get_response_with_dirty_resource(self):
        class _TestResource:
            def is_dirty(self, check_relationship=False):
                return True

            def save(self):
                pass

        class _TestEndpoint(machinery.EndpointDefinition):
            @machinery.endpoint_resource(type=_TestResource)
            def resource(self):
                return _TestResource()

        endpoint = _TestEndpoint()
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )

        class _FakeRequest:
            META = {}

        manager.bound_endpoint.request = _FakeRequest()

        with mock.patch.object(_TestResource, "save", return_value=None) as mock_save:
            manager.get_response()
            # save is called before and after tasks. since we've hardcoded _TestResource.is_dirty to return True,
            # both of them should fire
            self.assertEqual(mock_save.call_count, 2)

    def test_get_response_with_client_error_while_executing_tasks(self):
        class _TestResource:
            def is_dirty(self, check_relationship=False):
                return True

            def save(self):
                pass

        class _TestEndpoint(machinery.EndpointDefinition):
            @machinery.endpoint_resource(type=_TestResource)
            def resource(self):
                return _TestResource()

            @machinery.task
            def raise_an_exception(self):
                raise errors.ClientError(
                    code=http.HTTPStatus.BAD_REQUEST,
                    message="something bad happened",
                    save_changes=error_should_save_changes,
                )

        for error_should_save_changes in (True, False):
            with mock.patch.object(_TestResource, "save") as mock_save:
                endpoint = _TestEndpoint()
                manager = machinery.EndpointBinder.BoundEndpointManager(
                    machinery._EndpointRequestLifecycleManager(endpoint), endpoint
                )
                try:
                    manager.get_response()
                    self.fail("This should have failed")
                except errors.ClientError:
                    # save should be called twice if the exception says the resource should be saved: once before
                    # tasks are executed and once during exception handling.
                    self.assertEqual(
                        mock_save.call_count, 2 if error_should_save_changes else 1
                    )

    def test_get_response_custom_http_response(self):
        expected_data = {"foo": "bar"}
        expected_response = django.http.HttpResponse(content=json.dumps(expected_data))

        class _TestEndpoint(machinery.EndpointDefinition):
            @property
            def resource(self):
                pass

            @property
            def response(self):
                return expected_response

        endpoint = _TestEndpoint()
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )

        status, resp = manager.get_response()
        self.assertEqual(status, http.HTTPStatus.OK)
        self.assertEqual(resp, expected_response)
        self.assertEqual(json.loads(resp.content), expected_data)

    def test_get_response_custom_http_error(self):
        expected_data = {"error": "something bad happened"}

        class _TestEndpoint(machinery.EndpointDefinition):
            @property
            def resource(self):
                pass

            @property
            def response(self):
                return django.http.HttpResponse(
                    content=json.dumps(expected_data),
                    status=http.HTTPStatus.BAD_REQUEST,
                )

            @property
            def http_status(self):
                # TODO: it's kind of strange that http_status has to be defined if the response returns a custom
                # http response
                return http.HTTPStatus.BAD_REQUEST

        endpoint = _TestEndpoint()
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )

        try:
            manager.get_response()
            self.fail("This should have failed")
        except HttpStatusCode as err:
            self.assertEqual(err.response.status_code, http.HTTPStatus.BAD_REQUEST)
            self.assertEqual(json.loads(err.response.content), expected_data)

    def test_get_response_with_filtered_list(self):
        class _TestResource:
            def __init__(self, name, secret):
                self.name = name
                self.secret = secret

        class _QuerySet(list):
            pass

        data = _QuerySet([_TestResource("foo", "bar"), _TestResource("bar", "baz")])

        filter_def = {
            _TestResource: {"name": filtering.ALWAYS, "secret": filtering.NEVER}
        }

        class _TestEndpoint(machinery.EndpointDefinition):
            @machinery.endpoint_resource(type=_TestResource, filter=filter_def)
            def resource(self):
                return data

            @property
            def response(self):
                return {"people": self.resource}

            def __call__(self):
                return self

        endpoint = _TestEndpoint()
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )
        machinery.EndpointBinder(endpoint).create_bound_endpoint(manager, HttpRequest())

        status, resp = manager.get_response()
        self.assertEqual(status, http.HTTPStatus.OK)
        # make sure the list is in the expected order
        resp["people"].sort(key=lambda p: p["name"].lower())
        self.assertEqual(resp, {"people": [{"name": "bar"}, {"name": "foo"}]})


class EndpointFilteringTestCase(testutils.RequestCreatorMixin, django.test.TestCase):
    from django_declarative_apis.machinery.filtering import ALWAYS, NEVER

    class DummyClassOne(object):
        def __init__(self):
            self.foo = "foo" * 100
            self.bar = "bar" * 100

    class DummyMixin:
        pass

    class DummyClassTwo(DummyMixin, DummyClassOne):
        def __init__(self):
            super().__init__()
            self.baz = "baz" * 100
            self.blah = "blah" * 100

    class DummyClassThree(DummyClassTwo):
        def __init__(self):
            super().__init__()
            self.a_number = 5
            self.when = "when"
            self._in = "in"
            self.the = "the"
            self.course = "course"
            self.of = "of"
            self.human = "human"
            self.events = "events"

    class DummyClassFour(DummyClassThree):
        pass

    TEST_FILTERS = {
        str: ALWAYS,
        DummyClassOne: {"foo": ALWAYS, "bar": ALWAYS},
        DummyClassTwo: {
            "baz": lambda inst: inst.baz.upper(),
            "blah": lambda inst: inst.blah.upper(),
        },
        DummyClassThree: {
            "foo": NEVER,
            "a_number": lambda inst: inst.a_number + 5,
            "when": ALWAYS,
            "_in": ALWAYS,
            "the": ALWAYS,
            "course": NEVER,
            "of": ALWAYS,
            "human": ALWAYS,
            "events": ALWAYS,
        },
    }

    def test_filter_inheritance_with_mixin(self):
        data = EndpointFilteringTestCase.DummyClassTwo()
        filtered_data = filtering.apply_filters_to_object(
            data, EndpointFilteringTestCase.TEST_FILTERS
        )
        self.assertTrue("foo" in filtered_data)
        self.assertTrue("bar" in filtered_data)

    def test_filter_large_collection(self):
        data = [EndpointFilteringTestCase.DummyClassFour() for _ in range(1000)]
        filtered_data = filtering.apply_filters_to_object(
            data, EndpointFilteringTestCase.TEST_FILTERS
        )
        self.assertEqual(1000, len(filtered_data))
        self.assertFalse("course" in filtered_data[0])
        self.assertTrue("when" in filtered_data[0])
        self.assertEqual(10, filtered_data[0]["a_number"])
        self.assertEqual("BLAH" * 100, filtered_data[0]["blah"])

    def test_init_without_consumer_attributes(self):
        class _TestEndpoint(machinery.BaseEndpointDefinition):
            @property
            def resource(self):
                return {}

        endpoint = _TestEndpoint()
        endpoint_binder = machinery.EndpointBinder(endpoint)
        self.assertEqual(endpoint_binder.consumer_attributes, [])

    def test_create_bound_endpoint_with_url_and_adhoc_query_fields(self):
        req = django.test.RequestFactory().get("/")
        req.consumer = self.consumer
        testutils.OAuthClientHandler._build_request(req)
        params = req.GET.copy()
        params["adhoc_field__lt"] = "bar"
        req.GET = params

        class _TestEndpoint(machinery.EndpointDefinition):
            url_field = machinery.url_field()
            adhoc_field = machinery.adhoc_queryset()

            def is_authorized(self):
                return True

            @property
            def resource(self):
                return {"adhoc_field": self.adhoc_field, "url_field": self.url_field}

        bound_endpoint = _bind_endpoint(_TestEndpoint, req, url_field="baz")

        status, data = bound_endpoint.get_response()
        self.assertEqual(status, http.HTTPStatus.OK)
        self.assertEqual(data["adhoc_field"], {"adhoc_field__lt": "bar"})
        self.assertEqual(data["url_field"], "baz")

    @mock.patch("django_declarative_apis.machinery.EndpointBinder._validate_endpoint")
    def test_create_bound_endpoint_exception_raised(self, mock_validate_endpoint):
        mock_validate_endpoint.side_effect = Exception("something bad happened")
        req = django.test.RequestFactory().get("/")
        req.consumer = self.consumer
        testutils.OAuthClientHandler._build_request(req)

        class _TestEndpoint(machinery.EndpointDefinition):
            @property
            def resource(self):
                return {}

        bound_endpoint = _bind_endpoint(_TestEndpoint, req)

        try:
            status, data = bound_endpoint.get_response()
            self.fail("Should have failed")
        except Exception as err:
            _, err_inst, _ = bound_endpoint.validation_exc_info
            self.assertEqual(err_inst, err)

    def test_validate_endpoint_unauthorized(self):
        req = django.test.RequestFactory().get("/")
        req.consumer = self.consumer
        testutils.OAuthClientHandler._build_request(req)

        class _TestEndpoint(machinery.EndpointDefinition):
            required_field = machinery.url_field(required=True)

            @property
            def resource(self):
                return {}

        bound_endpoint = _bind_endpoint(_TestEndpoint, req)

        try:
            bound_endpoint.get_response()
            self.fail("this should have failed")
        except errors.ClientErrorForbidden as err:
            expected_code, expected_msg = errors.FORBIDDEN
            self.assertEqual(err.save_changes, False)
            self.assertEqual(err.error_code, expected_code)
            self.assertEqual(err.error_message, expected_msg)
            self.assertEqual(err.status_code, http.HTTPStatus.FORBIDDEN)

    def test_validate_endpoint_missing_consumer_error(self):
        req = self.create_request()

        class _TestEndpoint(machinery.EndpointDefinition):
            consumer = machinery.consumer_attribute()

            @property
            def resource(self):
                return {}

        bound_endpoint = _bind_endpoint(_TestEndpoint, req)

        try:
            bound_endpoint.get_response()
            self.fail("this should have failed")
        except errors.ClientErrorForbidden as err:
            expected_code, expected_msg = errors.FORBIDDEN
            self.assertEqual(err.save_changes, False)
            self.assertEqual(err.error_code, expected_code)
            self.assertEqual(err.error_message, expected_msg)
            self.assertEqual(err.status_code, http.HTTPStatus.FORBIDDEN)

    def test_get_response_missing_required_attributes_error(self):
        req = self.create_request()

        class _TestEndpoint(machinery.EndpointDefinition):
            required_a = machinery.field(required=True)
            required_b = machinery.field(required=True)

            @property
            def resource(self):
                return {}

        bound_endpoint = _bind_endpoint(_TestEndpoint, req)
        try:
            bound_endpoint.get_response()
        except errors.ClientErrorMissingFields as err:
            expected_code, expected_msg = errors.MISSING_FIELDS
            self.assertFalse(err.save_changes)
            self.assertTrue(err.error_message.startswith(expected_msg))
            self.assertTrue(
                all(name in err.error_message for name in ("required_a", "required_b"))
            )
            self.assertEqual(err.error_code, expected_code)
            self.assertEqual(err.status_code, http.HTTPStatus.BAD_REQUEST)

    def test_get_response_invalid_field_type_error(self):
        req = self.create_request(
            method="POST", body={"int_field_a": "foo", "int_field_b": "bar"}
        )

        class _TestEndpoint(machinery.EndpointDefinition):
            int_field_a = machinery.field(type=int, required=True)
            int_field_b = machinery.field(type=int, required=True)

            def is_authorized(self):
                return True

            @property
            def resource(self):
                return {}

        bound_endpoint = _bind_endpoint(_TestEndpoint, req)

        try:
            bound_endpoint.get_response()
            self.fail("should have failed here")
        except errors.ClientErrorInvalidFieldValues as err:
            expected_code, expected_msg = errors.INVALID_FIELD_VALUES
            self.assertFalse(err.save_changes)
            self.assertTrue(err.error_message.startswith(expected_msg))
            self.assertTrue("int_field_a" in err.error_message)
            self.assertTrue("int_field_b" in err.error_message)
            self.assertEqual(err.error_code, expected_code)
            self.assertEqual(err.status_code, http.HTTPStatus.BAD_REQUEST)

    def test_get_response_not_found_error(self):
        req = self.create_request()

        class _TestEndpoint(machinery.EndpointDefinition):
            def is_authorized(self):
                raise django.core.exceptions.ObjectDoesNotExist

            @property
            def resource(self):
                return {}

        bound_endpoint = _bind_endpoint(_TestEndpoint, req)

        try:
            bound_endpoint.get_response()
            self.fail("should have failed")
        except errors.ClientErrorNotFound as err:
            self.assertFalse(err.save_changes)
            self.assertEqual(err.error_message, http.HTTPStatus.NOT_FOUND.phrase)
            self.assertEqual(err.error_code, http.HTTPStatus.NOT_FOUND)
            self.assertEqual(err.status_code, http.HTTPStatus.NOT_FOUND)

    def test_get_response_throttled_error(self):
        req = self.create_request()

        class _TestEndpoint(machinery.EndpointDefinition):
            def is_authorized(self):
                return True

            def rate_limit_key(self):
                return "foo"

            @property
            def resource(self):
                return {}

        with mock.patch(
            "django_declarative_apis.machinery.rate_limit_exceeded"
        ) as patch_throttle:
            patch_throttle.return_value = True
            bound_endpoint = _bind_endpoint(_TestEndpoint, req)

        try:
            bound_endpoint.get_response()
        except errors.ClientErrorRequestThrottled as err:
            expected_code, expected_message = errors.REQUEST_THROTTLED
            self.assertFalse(err.save_changes)
            self.assertEqual(err.error_code, expected_code)
            self.assertEqual(err.error_message, expected_message)
            self.assertEqual(err.status_code, http.HTTPStatus.TOO_MANY_REQUESTS)


class EndpointRequestLifecycleManagerTestCase(
    testutils.RequestCreatorMixin, unittest.TestCase
):
    def test_process_request_and_get_response_success(self):
        req = self.create_request()
        expected_data = {"foo": "bar"}

        class _TestEndpoint(machinery.EndpointDefinition):
            def is_authorized(self):
                return True

            @property
            def resource(self):
                return expected_data

        manager = machinery._EndpointRequestLifecycleManager(_TestEndpoint)
        status, data = manager.process_request_and_get_response(req)
        self.assertEqual(status, http.HTTPStatus.OK)
        self.assertEqual(data, expected_data)


class EndpointDefinitionTestCase(testutils.RequestCreatorMixin, unittest.TestCase):
    def test_is_permitted(self):
        self.consumer.type = dda_models.BaseConsumer.TYPE_READ_ONLY
        self.consumer.save()

        class _TestEndpoint(machinery.EndpointDefinition):
            def is_authorized(self):
                return True

            @property
            def resource(self):
                return {}

        # client should be able to access read endpoints
        req = self.create_request()
        bound_endpoint = _bind_endpoint(_TestEndpoint, req)
        status, _ = bound_endpoint.get_response()
        self.assertEqual(status, http.HTTPStatus.OK)

        # but not write
        req = self.create_request(method="POST")
        bound_endpoint = _bind_endpoint(_TestEndpoint, req)
        self.assertRaises(errors.ClientErrorForbidden, bound_endpoint.get_response)

    def test_is_permitted_readonly(self):
        self.consumer.type = dda_models.BaseConsumer.TYPE_READ_ONLY
        self.consumer.save()

        class _TestReadOnlyEndpoint(machinery.EndpointDefinition):
            is_read_only = True

            def is_authorized(self):
                return True

            @property
            def resource(self):
                return {}

        req = self.create_request(method="POST")
        bound_endpoint = _bind_endpoint(_TestReadOnlyEndpoint, req)
        status, _ = bound_endpoint.get_response()
        self.assertEqual(status, http.HTTPStatus.OK)

    def test_misconfigured_consumer_cant_access_resource(self):
        self.consumer.type = "invalid"
        self.consumer.save()

        class _TestEndpoint(machinery.EndpointDefinition):
            def is_authorized(self):
                return True

            @property
            def resource(self):
                return {}

        req = self.create_request()
        bound_endpoint = _bind_endpoint(_TestEndpoint, req)
        self.assertRaises(errors.ClientErrorForbidden, bound_endpoint.get_response)

        req = self.create_request(method="POST")
        bound_endpoint = _bind_endpoint(_TestEndpoint, req)
        self.assertRaises(errors.ClientErrorForbidden, bound_endpoint.get_response)


class ResourceUpdateEndpointDefinitionTestCase(
    testutils.RequestCreatorMixin, django.test.TestCase
):
    def test_mutate_resource(self):
        obj = tests.models.TestModel(int_field=24)
        obj.save()

        class _TestEndpoint(machinery.ResourceUpdateEndpointDefinition):
            resource_model = tests.models.TestModel
            int_field = machinery.resource_field(type=int)

            def __init__(self, *args, **kwargs):
                self.resource_id = obj.id
                super().__init__(*args, **kwargs)

            def is_authorized(self):
                return True

            @machinery.endpoint_resource(
                type=tests.models.TestModel,
                filter={tests.models.TestModel: {"int_field": filtering.ALWAYS}},
            )
            def resource(self):
                return super().resource

            @property
            def response(self):
                self.resource.save()
                return self.resource

        req = self.create_request(
            method="POST", body={"int_field": 42}, use_auth_header_signature=True
        )
        bound_endpoint = _bind_endpoint(_TestEndpoint, req)
        status, resp = bound_endpoint.get_response()
        self.assertEqual(status, http.HTTPStatus.OK)
        self.assertEqual(resp, {"int_field": 42})


class ResourceCreationMixinTestCase(unittest.TestCase):
    def test_status(self):
        class Test(machinery.ResourceCreationMixin):
            pass

        self.assertEqual(Test().http_status, http.HTTPStatus.CREATED)


class MySpecialException(Exception):
    pass


class _TestEndpoint(machinery.EndpointDefinition):
    def __init__(self, expected_response, *args, **kwargs):
        super(_TestEndpoint, self).__init__(*args, **kwargs)
        self.expected_response = expected_response

    def __call__(self):
        return self

    @machinery.endpoint_resource(
        type=tests.models.TestModel, filter={str: filtering.ALWAYS}
    )
    def resource(self):
        return tests.models.TestModel(int_field=0)

    @property
    def response(self):
        return self.expected_response

    @machinery.deferrable_task(always_defer=True)
    @staticmethod
    def deferred_task(inst):
        assert inst is not None
        _TestEndpoint.semaphore["status"] = "deferred task executed"

    @machinery.deferrable_task(always_defer=True, retries=2)
    @staticmethod
    def deferred_task_with_retry(inst):
        assert inst is not None
        retry_key = "retry_count"
        _TestEndpoint.semaphore[retry_key] += 1
        if _TestEndpoint.semaphore[retry_key] < 3:
            raise Exception("failing so task will retry")

    @machinery.deferrable_task(
        always_defer=True, retries=2, retry_exception_filter=(MySpecialException,)
    )
    @staticmethod
    def deferred_task_with_retry_and_filtered_exceptions(inst):
        assert inst is not None
        retry_key = "filtered_retry_count_1"
        _TestEndpoint.semaphore[retry_key] += 1
        if _TestEndpoint.semaphore[retry_key] < 3:
            raise MySpecialException("failing so task will retry")

    @machinery.deferrable_task(
        always_defer=True, retries=2, retry_exception_filter=(MySpecialException,)
    )
    @staticmethod
    def deferred_task_with_retry_and_filtered_exceptions_fail(inst):
        # this task specifies an exception filter list, but throws the wrong exception, so should not retry
        assert inst is not None
        retry_key = "filtered_retry_count_2"
        _TestEndpoint.semaphore[retry_key] += 1
        if _TestEndpoint.semaphore[retry_key] < 3:
            raise Exception("failing so task will retry")


class DeferrableTaskTestCase(django.test.TestCase):
    def setUp(self):
        _TestEndpoint.semaphore = {
            "status": None,
            "retry_count": 0,
            "filtered_retry_count_1": 0,
            "filtered_retry_count_2": 0,
        }

    def test_get_response_kombu_error_retried(self):
        expected_response = {"foo": "bar"}
        endpoint = _TestEndpoint(expected_response)
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )
        machinery.EndpointBinder(endpoint).create_bound_endpoint(manager, HttpRequest())

        conf = tasks.future_task_runner.app.conf
        old_val = conf["task_always_eager"]
        conf["task_always_eager"] = True

        cache.set(tasks.JOB_COUNT_CACHE_KEY, 0)

        with mock.patch(
            "django_declarative_apis.machinery.tasks.future_task_runner.apply_async"
        ) as mock_apply:
            exceptions = iter(
                [kombu.exceptions.OperationalError, kombu.exceptions.OperationalError]
            )

            def _side_effect(*args, **kwargs):
                try:
                    raise next(exceptions)
                except StopIteration:
                    return future_task_runner.apply(*args, **kwargs)

            mock_apply.side_effect = _side_effect

            try:
                resp = manager.get_response()
            finally:
                conf["task_always_eager"] = old_val

        self.assertEqual(resp, (http.HTTPStatus.OK, expected_response))
        self.assertTrue(cache.get(tasks.JOB_COUNT_CACHE_KEY) != 0)

        self.assertEqual("deferred task executed", _TestEndpoint.semaphore["status"])

    def test_async_task_falls_back_to_synchronous_when_configured(self):
        expected_response = {"foo": "bar"}

        endpoint = _TestEndpoint(expected_response)
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )
        machinery.EndpointBinder(endpoint).create_bound_endpoint(manager, HttpRequest())

        conf = tasks.future_task_runner.app.conf
        old_val = conf["task_always_eager"]
        conf["task_always_eager"] = True

        with mock.patch(
            "django_declarative_apis.machinery.tasks.future_task_runner.apply_async"
        ) as mock_apply_async:
            mock_apply_async.side_effect = kombu.exceptions.OperationalError

            cache.set(tasks.JOB_COUNT_CACHE_KEY, 0)

            with self.settings(DECLARATIVE_ENDPOINT_TASKS_SYNCHRONOUS_FALLBACK=True):
                try:
                    manager.get_response()
                except kombu.exceptions.OperationalError:
                    self.fail("OperationalError should not have been triggered")
                finally:
                    conf["task_always_eager"] = old_val

        self.assertEqual("deferred task executed", _TestEndpoint.semaphore["status"])

    def test_force_synchronous_tasks(self):
        expected_response = {"foo": "bar"}
        endpoint = _TestEndpoint(expected_response)
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )
        machinery.EndpointBinder(endpoint).create_bound_endpoint(manager, HttpRequest())

        conf = tasks.future_task_runner.app.conf
        old_val = conf["task_always_eager"]
        conf["task_always_eager"] = True

        cache.set(tasks.JOB_COUNT_CACHE_KEY, 0)

        with mock.patch(
            "django_declarative_apis.machinery.tasks.future_task_runner.apply_async"
        ) as mock_apply:
            mock_apply.side_effect = kombu.exceptions.OperationalError

            with self.settings(DECLARATIVE_ENDPOINT_TASKS_FORCE_SYNCHRONOUS=True):
                try:
                    manager.get_response()
                except kombu.exceptions.OperationalError:
                    self.fail("OperationalError should not have been triggered")
                finally:
                    conf["task_always_eager"] = old_val

        self.assertEqual(0, mock_apply.call_count)
        self.assertEqual("deferred task executed", _TestEndpoint.semaphore["status"])

    def test_get_response_kombu_error_attempts_exceeded(self):
        expected_response = {"foo": "bar"}
        endpoint = _TestEndpoint(expected_response)
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )
        machinery.EndpointBinder(endpoint).create_bound_endpoint(manager, HttpRequest())

        conf = tasks.future_task_runner.app.conf
        old_val = conf["task_always_eager"]
        conf["task_always_eager"] = True

        cache.set(tasks.JOB_COUNT_CACHE_KEY, 0)

        with mock.patch(
            "django_declarative_apis.machinery.tasks.future_task_runner.apply_async"
        ) as mock_apply:
            exceptions = iter(
                [
                    kombu.exceptions.OperationalError,
                    kombu.exceptions.OperationalError,
                    kombu.exceptions.OperationalError,
                ]
            )

            def _side_effect(*args, **kwargs):
                try:
                    raise next(exceptions)
                except StopIteration:
                    return future_task_runner.apply(*args, **kwargs)

            mock_apply.side_effect = _side_effect

            try:
                manager.get_response()
                self.fail("should have triggered a kombu.exceptions.OperationalError")
            except kombu.exceptions.OperationalError:
                pass
            finally:
                conf["task_always_eager"] = old_val

        self.assertIsNone(_TestEndpoint.semaphore["status"])

    def test_get_response_success(self):
        expected_response = {"foo": "bar"}

        endpoint = _TestEndpoint(expected_response)
        manager = machinery.EndpointBinder.BoundEndpointManager(
            machinery._EndpointRequestLifecycleManager(endpoint), endpoint
        )
        machinery.EndpointBinder(endpoint).create_bound_endpoint(manager, HttpRequest())

        # can't use mock.patch.dict here because it doesn't implement the api that the unpatcher expects
        conf = tasks.future_task_runner.app.conf
        old_val = conf["task_always_eager"]
        conf["task_always_eager"] = True

        cache.set(tasks.JOB_COUNT_CACHE_KEY, 0)

        try:
            resp = manager.get_response()
        finally:
            conf["task_always_eager"] = old_val

        self.assertEqual(resp, (http.HTTPStatus.OK, expected_response))
        self.assertTrue(cache.get(tasks.JOB_COUNT_CACHE_KEY) != 0)

        self.assertEqual("deferred task executed", _TestEndpoint.semaphore["status"])
        self.assertEqual(3, _TestEndpoint.semaphore["retry_count"])
        self.assertEqual(3, _TestEndpoint.semaphore["filtered_retry_count_1"])
        self.assertEqual(1, _TestEndpoint.semaphore["filtered_retry_count_2"])

        _TestEndpoint.semaphore = {
            "status": None,
            "retry_count": 0,
            "filtered_retry_count_1": 0,
            "filtered_retry_count_2": 0,
        }

    def test_deferrable_methods_must_be_static(self):
        try:
            machinery.deferrable_task()(
                DeferrableTaskTestCase.test_deferrable_methods_must_be_static
            )
            self.fail("Should have raised assertionerror")
        except AssertionError as err:
            self.assertTrue("Deferrable task methods MUST be staticmethods" in str(err))
        except Exception:
            self.fail("should have raised assertionerror")


class ResourceAsyncJobTestCase(django.test.TestCase):
    def test_resource_async_job(self):
        resource = tests.models.TestModel()
        resource.int_field = 1
        resource.save()

        conf = tasks.future_task_runner.app.conf
        old_val = conf["task_always_eager"]
        conf["task_always_eager"] = True

        tasks.schedule_resource_task_runner(resource.mutate_action)

        conf["task_always_eager"] = old_val

        resource.refresh_from_db()
        self.assertEqual(2, resource.int_field)


def _bind_endpoint(endpoint_cls, request, url_field=None):
    endpoint = endpoint_cls()
    binder = machinery.EndpointBinder(endpoint_cls)
    return binder.create_bound_endpoint(
        machinery._EndpointRequestLifecycleManager(endpoint),
        request,
        url_field=url_field,
    )
