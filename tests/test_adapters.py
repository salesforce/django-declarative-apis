#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import http
import unittest

import django.test

from django_declarative_apis import adapters, authentication, machinery


class BaseHandlerTestCase(unittest.TestCase):
    def test_supported_methods(self):
        self.assertEqual(
            adapters.BaseHandler.defined_methods,
            {"get", "put", "patch", "post", "delete"},
        )


class _HandlerA(machinery.EndpointDefinition):
    RESPONSE = {"foo": "bar"}
    this_is_really_a_field = machinery.field(type=str)

    def is_authorized(self):
        return True

    @property
    def resource(self):
        return self.RESPONSE


class _HandlerB(machinery.EndpointDefinition):
    def is_authorized(self):
        return True

    @property
    def resource(self):
        return {}


class EndpointHandlerTestCase(unittest.TestCase):
    def test_invalid_method_error(self):
        self.assertRaises(TypeError, adapters.EndpointHandler, invalid=lambda: None)

    def test_multiple_handlers(self):
        endpoints = (_HandlerA, _HandlerB)
        handler = adapters.EndpointHandler(get=endpoints)
        self.assertEqual(handler.method_handlers["GET"].endpoint_definitions, endpoints)
        self.assertEqual(handler.allowed_methods, {"GET"})

    def test_single_handler(self):
        handler = adapters.EndpointHandler(get=_HandlerA)
        self.assertEqual(
            handler.method_handlers["GET"].endpoint_definitions, (_HandlerA,)
        )
        self.assertEqual(handler.allowed_methods, {"GET"})

    def test_documentation(self):
        handler = adapters.EndpointHandler(get=_HandlerA)
        docs = handler.documentation
        self.assertIn("GET", docs)
        self.assertIn("class_name", docs["GET"][0])
        self.assertEqual(docs["GET"][0]["class_name"], "_HandlerA")
        self.assertIn("fields", docs["GET"][0])

        expected_field = {
            "name": "this_is_really_a_field",
            "type": str,
            "multivalued": False,
        }
        self.assertIn(expected_field, docs["GET"][0]["fields"])

    def test_handle_request(self):
        req = django.test.RequestFactory().get("/simple")
        req.consumer = None
        resp = adapters.EndpointHandler(get=_HandlerA).handle_request("GET", req)
        self.assertEqual(resp, (http.HTTPStatus.OK, _HandlerA.RESPONSE))

    def test_custom_request_field(self):
        class _HandlerWithoutCustomField(machinery.EndpointDefinition):
            def is_authorized(self):
                try:
                    return self.request.custom_request_field == 42
                except AttributeError:
                    return False

            @property
            def resource(self):
                return {}

        class _HandlerWithCustomField(_HandlerWithoutCustomField):
            request = machinery.RawRequestObjectProperty(
                additional_safe_fields=("custom_request_field",)
            )

        class _Authenticator(authentication.Authenticator):
            def is_authenticated(self, request):
                request.custom_request_field = 42
                return True

            def challenge(self, error):
                pass

        authenticator = _Authenticator()
        req = django.test.RequestFactory().get("/simple")
        req.consumer = None
        resource = adapters.EndpointResource(
            get=_HandlerWithoutCustomField, authentication={None: [authenticator]}
        )
        resp = resource(req)
        self.assertEqual(resp.status_code, http.HTTPStatus.FORBIDDEN)

        resource = adapters.EndpointResource(
            get=_HandlerWithCustomField, authentication={None: [authenticator]}
        )
        resp = resource(req)
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)


class EndpointResourceTestCase(unittest.TestCase):
    def test_custom_authentication(self):
        class _Authenticator(authentication.Authenticator):
            def is_authenticated(self, request):
                return True

            def challenge(self):
                pass

        authenticator = _Authenticator()
        resource = adapters.EndpointResource(authentication={None: [authenticator]})
        self.assertEqual(resource.authentication, {None: [authenticator]})
