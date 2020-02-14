#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import django.test
from django.core.cache import cache

from django_declarative_apis import models
from django_declarative_apis.authentication.oauthlib import endpoint, request_validator
from tests import testutils


# TODO: create tests for android and ios rsa signing


def _oauth_qs(request):
    return "&".join(["=".join((k, v)) for k, v in request.GET.items()])


class TweakedSignatureOnlyEndpointTestCase(django.test.TestCase):
    def _request(self, url, method="GET", rsa_key=None):
        request = getattr(self.request, method.lower())(url)
        request.META["consumer"] = self.consumer
        if rsa_key is not None:
            request.META["rsa_key"] = rsa_key
        testutils.OAuthClientHandler._build_request(request)

        validator = request_validator.DjangoRequestValidator(request)
        endpoint_instance = endpoint.TweakedSignatureOnlyEndpoint(validator)

        return request, validator, endpoint_instance

    def setUp(self):
        self.request = django.test.RequestFactory()
        self.consumer = models.OauthConsumer.objects.create(name="test")
        self.consumer.save()

    def test_validate_request_missing_parameters_error(self):
        request, validator, endpoint_instance = self._request("/test")
        result = endpoint_instance.validate_request("/test")

        self.assertEqual(result, (False, None))

    def test_validate_request_invalid_transport_security_error(self):
        with self.settings(REQUIRE_HTTPS_FOR_OAUTH=True):
            request, validator, endpoint_instance = self._request("/test")
            result, _ = endpoint_instance.validate_request(
                f"http://test?{_oauth_qs(request)}"
            )

        self.assertEqual(
            endpoint_instance.validation_error_message,
            "Only HTTPS connections are permitted.",
        )
        self.assertFalse(result)

    def test_validate_request_invalid_parameters_error(self):
        request, validator, endpoint_instance = self._request("/test")

        params = request.GET.copy()
        del params["oauth_signature_method"]
        request.GET = params

        result, _ = endpoint_instance.validate_request(
            f"http://test?{_oauth_qs(request)}"
        )

        self.assertEqual(
            endpoint_instance.validation_error_message,
            "Missing mandatory OAuth parameters.",
        )
        self.assertFalse(result)

    def test_validate_request_invalid_nonce_error(self):
        request, validator, endpoint_instance = self._request("/test")

        # nonce has already been used
        cache.set(
            f"{request.META['consumer'].key}:::{request.GET['oauth_nonce']}", True
        )
        result, _ = endpoint_instance.validate_request(
            f"http://test?{_oauth_qs(request)}"
        )

        self.assertEqual(validator.validation_error_message, "nonce_used")
        self.assertFalse(result)

    def test_validate_request_invalid_client_error(self):
        request, validator, endpoint_instance = self._request("/test")

        params = request.GET.copy()
        params["oauth_consumer_key"] = "bad"
        request.GET = params

        result, _ = endpoint_instance.validate_request(
            f"http://test?{_oauth_qs(request)}"
        )
        self.assertFalse(result)

    def test_validate_request_invalid_signature_error(self):
        request, validator, endpoint_instance = self._request("/test")

        params = request.GET.copy()
        params["oauth_signature"] = "bad"
        request.GET = params

        result, _ = endpoint_instance.validate_request(
            f"http://test?{_oauth_qs(request)}"
        )
        self.assertTrue(
            endpoint_instance.validation_error_message.startswith(
                "Invalid signature. Expected signature base string:"
            )
        )
        self.assertFalse(result)
