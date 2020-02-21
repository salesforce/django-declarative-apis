#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import http
import json

import django.conf
import django.core.exceptions
import django.test
import mock

from django_declarative_apis.authentication.oauthlib import oauth_errors
from django_declarative_apis.resources import resource
from tests import testutils


class ResourceTestCase(testutils.RequestCreatorMixin, django.test.TestCase):
    def test_call_post(self):
        def handle_post(request, *args, **kwargs):
            return http.HTTPStatus.OK, {"foo": "bar"}

        class Handler:
            allowed_methods = ("POST",)
            method_handlers = {"POST": handle_post}

        body = {"foo": "bar"}
        req = self.create_request(method="POST", body=body)

        res = resource.Resource(lambda: Handler())
        resp = res(req)
        self.assertEqual(json.loads(resp.content), body)

    def test_call_invalid_mime_type(self):
        class Handler:
            allowed_methods = ("POST",)
            method_handlers = {
                "POST": lambda req, *args, **kwargs: (http.HTTPStatus.OK, "")
            }

        body = {"foo": "bar"}
        req = self.create_request(method="POST", body=body)

        res = resource.Resource(lambda: Handler())
        with mock.patch(
            "django_declarative_apis.resources.resource.translate_mime"
        ) as mock_translate:
            mock_translate.side_effect = resource.MimerDataException

            res(req)

    def test_call_put(self):
        class Handler:
            allowed_methods = ("PUT",)
            method_handlers = {
                "PUT": lambda req, *args, **kwargs: (http.HTTPStatus.OK, "")
            }

        body = {"foo": "bar"}
        req = self.create_request(method="PUT", body=body)
        res = resource.Resource(lambda: Handler())
        res(req)

        # make sure request coercion did its thing to allow django to support it
        self.assertEqual(req.PUT, req.POST)

    def test_anonymous(self):
        class HandlerA:
            def anonymous(self):
                return True

        handler = HandlerA()
        res = resource.Resource(lambda: handler)
        self.assertEqual(res.anonymous, handler.anonymous)

        class HandlerB:
            pass

        handler = HandlerB()
        res = resource.Resource(lambda: handler)
        self.assertIsNone(res.anonymous)

    def test_authenticate(self):
        class Handler:
            pass

        handler = Handler()
        res = resource.Resource(lambda: handler)
        _, anonymous, err = res.authenticate(
            django.test.RequestFactory().get("/"), "GET"
        )
        self.assertEqual(anonymous, resource.CHALLENGE)
        self.assertIsInstance(err, oauth_errors.OAuthMissingParameterError)

    def test_deserializers(self):
        data = {"foo": "bar"}
        req = self.create_request(
            method="POST", body=data, content_type="application/json"
        )
        resource._deserialize_json(req)
        self.assertEqual(req.POST, data)

    def test_init_unset_authentication_handlers(self):
        current_handlers = (
            django.conf.settings.DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS
        )
        try:
            del resource.settings.DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS
            self.assertRaises(
                django.core.exceptions.ImproperlyConfigured,
                resource.Resource,
                lambda: lambda: None,
            )
        finally:
            resource.settings.DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS = (
                current_handlers
            )

    def test_init_uncallable_handler(self):
        try:
            resource.Resource("not callable")
            self.fail("should have faileid")
        except AttributeError as err:
            self.assertEqual(str(err), "Handler not callable.")

    def test_error_handler(self):
        class Handler:
            pass

        res = resource.Resource(lambda: Handler())
        req = django.test.RequestFactory().get("/")
        try:
            raise Exception("something bad happened")
        except Exception as err:
            with mock.patch(
                "django_declarative_apis.resources.resource.Resource.email_exception"
            ) as mock_email:
                res.error_handler(err, req, "GET", "json")

        (reporter,), kwargs = mock_email.call_args_list[0]
        self.assertEqual(mock_email.call_count, 1)
        self.assertEqual(reporter.request, req)
        self.assertEqual(reporter.exc_type, Exception)

    def test_use_emitter(self):
        resp = django.http.HttpResponse(content_type="image")
        self.assertFalse(resource.Resource._use_emitter(resp))

        resp = django.http.HttpResponse(content_type="application/json")
        self.assertFalse(resource.Resource._use_emitter(resp))

        resp = django.http.HttpResponse(content_type="unhandled")
        self.assertTrue(resource.Resource._use_emitter(resp))

    def test_email_exception(self):
        with mock.patch(
            "django_declarative_apis.resources.resource.EmailMessage"
        ) as mock_email:
            traceback = "something bad happened"
            reporter = type("Reporter", (), {"get_traceback_html": lambda: traceback})

            res = resource.Resource(lambda: lambda: None)
            res.email_exception(reporter)
            (subj, body, _, __), ___ = mock_email.call_args_list[0]
            self.assertEqual(subj, "[Django] Django Declarative APIs crash report")
            self.assertEqual(body, traceback)
