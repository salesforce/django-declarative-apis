#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import http
import json
import unittest

import django.test
import django.http
import mock

from django_declarative_apis import models
from django_declarative_apis import authentication
from django_declarative_apis.authentication.oauthlib import oauth1, oauth_errors
from tests import testutils


class TwoLeggedOauth1TestCase(unittest.TestCase):
    def setUp(self):
        self.request_factory = django.test.RequestFactory()
        self.consumer = models.OauthConsumer.objects.create(name="test")

    def test_validate_missing_parameters(self):
        request = self.request_factory.get("/")
        authenticator = oauth1.TwoLeggedOauth1()
        authenticator.validate_missing_parameters(request)

        self.assertEqual(
            request.auth_header,
            'OAuth realm="API",oauth_problem=parameter_absent&oauth_parameters_absent=oauth_consumer_key,oauth_nonce,'
            "oauth_signature,oauth_signature_method,oauth_timestamp",
        )

    def test_is_authenticated_django_header_sillyness_and_auth_failure(self):
        request = self.request_factory.get("/")
        request.META["HTTP_AUTHORIZATION"] = "OAuth foo=bar"
        testutils.OAuthClientHandler._build_request(request)

        authenticator = oauth1.TwoLeggedOauth1()
        result = authenticator.is_authenticated(request)
        self.assertIsInstance(result, oauth_errors.OAuthMissingParameterError)
        self.assertEqual(
            result.detail,
            "Parameters missing: oauth_consumer_key,oauth_nonce,oauth_signature,oauth_signature_method,oauth_timestamp",
        )

    def test_is_authenticated_invalid_signature_error(self):
        request = self.request_factory.get("/")
        request.META["consumer"] = self.consumer
        testutils.OAuthClientHandler._build_request(request)

        params = request.GET.copy()
        params["oauth_signature"] = "bad"
        request.GET = params

        authenticator = oauth1.TwoLeggedOauth1()
        result = authenticator.is_authenticated(request)
        self.assertIsInstance(result, oauth_errors.OAuthInvalidSignatureError)
        self.assertTrue(result.detail.startswith("Invalid signature."))

    @mock.patch("django_declarative_apis.authentication.oauthlib.oauth1.logger.error")
    def test_is_authenticated_validation_error_handled(self, mocked_log):
        class ExceptionWithMessage(Exception):
            def __init__(self, msg):
                self.message = msg

        request = self.request_factory.get("/")
        request.META["consumer"] = self.consumer
        testutils.OAuthClientHandler._build_request(request)

        authenticator = oauth1.TwoLeggedOauth1()

        with mock.patch(
            "django_declarative_apis.authentication.oauthlib.oauth1.TweakedSignatureOnlyEndpoint"
        ) as mocked_obj:
            mocked_obj.side_effect = ExceptionWithMessage(msg="something bad happened")
            result = authenticator.is_authenticated(request)
        self.assertIsInstance(result, authentication.AuthenticationFailure)
        mocked_log.assert_called_with(
            "Invalid oauthlib request: something bad happened"
        )

    def test_authenticate_header(self):
        request = self.request_factory.get("/")

        authenticator = oauth1.TwoLeggedOauth1()

        result = authenticator.authenticate_header(request)
        self.assertEqual(result, "Unknown OAuth Error")

        request.auth_header = "foo"
        result = authenticator.authenticate_header(request)
        self.assertEqual(result, "foo")

    def test_challenge_with_no_error(self):
        authenticator = oauth1.TwoLeggedOauth1()
        response = authenticator.challenge()

        self.assertIsInstance(response, django.http.HttpResponse)
        self.assertEqual(response.status_code, http.HTTPStatus.UNAUTHORIZED)
        self.assertEqual(response["www-authenticate"], "None")

    def test_challenge_with_error(self):
        authenticator = oauth1.TwoLeggedOauth1()
        response = authenticator.challenge(oauth_errors.OAuthTimestampError())

        self.assertEqual(response.status_code, http.HTTPStatus.UNAUTHORIZED)
        self.assertTrue("timestamp_refused" in response["www-authenticate"])

        data = json.loads(response.getvalue().decode("utf8"))
        self.assertEqual(data["error_code"], http.HTTPStatus.UNAUTHORIZED)
        self.assertTrue(
            data["error_message"], "There was a problem with your timestamp."
        )
