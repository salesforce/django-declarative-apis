#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import json
import time
import urllib.parse
import logging

import oauth2

from oauthlib import oauth1 as oauthlib_oauth1
from oauthlib import common as oauthlib_common

from django.http import QueryDict

import django.test
from django.test import Client
from django.test.client import ClientHandler
from django.test.runner import DiscoverRunner

from django_declarative_apis import models

DEFAULT_CONTENT_TYPE = "application/x-www-form-urlencoded"
_ENCODERS = {
    DEFAULT_CONTENT_TYPE: lambda data: urllib.parse.urlencode(data),
    "application/json": lambda data: json.dumps(data),
    "application/json; charset=utf-16": lambda data: json.dumps(data),
}


class NoLoggingTestRunner(DiscoverRunner):

    """Don't log during tests."""

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        logging.disable(logging.CRITICAL)
        return super().run_tests(test_labels, extra_tests, **kwargs)


class RequestCreatorMixin:
    def setUp(self):
        self.consumer = models.OauthConsumer.objects.create(name="test")
        self.consumer.save()

    def create_request(
        self,
        method="GET",
        path="/",
        url_fields=None,
        body=None,
        content_type=DEFAULT_CONTENT_TYPE,
        use_auth_header_signature=False,
    ):
        meth = getattr(django.test.RequestFactory(), method.lower())
        req = meth(
            path,
            _ENCODERS[content_type](body) if body else None,
            content_type=content_type,
        )
        req.consumer = self.consumer
        req.META["consumer"] = self.consumer

        if url_fields is not None:
            params = req.GET.copy()
            params.update(url_fields)
            req.GET = params

        # TODO: this should be better documented or on by default. If this is omitted or False, then requests will
        # fail in resource input validation (ResourceUpdateEndpointDefinition.validate_input)
        req.META["use_auth_header_signature"] = use_auth_header_signature
        OAuthClientHandler._build_request(req)

        return req


class OAuthClientHandler(ClientHandler):
    one_time_client_timestamp_override = None

    @classmethod
    def get_oauth_client_timestamp(cls):
        if cls.one_time_client_timestamp_override:
            result = cls.one_time_client_timestamp_override
            cls.one_time_client_timestamp_override = None
        else:
            result = int(time.time())
        return result

    @classmethod
    def _build_request(cls, request):
        consumer = request.META.get("consumer")

        # Make request params mutable so we can add authorization parameters.
        # We make the params immutable again before processing the request
        request.POST = request.POST.copy()
        request.GET = request.GET.copy()

        if consumer:
            if request.method == "POST":
                data = request.POST
            else:
                data = request.GET

            # This provides a way for us to override default values for testing.
            oauth_version = request.META.get("oauth_version", "1.0")
            oauth_nonce = request.META.get("oauth_nonce", oauth2.generate_nonce())
            oauth_client_timestamp = request.META.get(
                "oauth_timestamp", cls.get_oauth_client_timestamp()
            )

            rsa_key = request.META.get("rsa_key", None)
            oauth_signature_method = (
                oauthlib_oauth1.SIGNATURE_RSA
                if rsa_key
                else oauthlib_oauth1.SIGNATURE_HMAC
            )

            oauth_signature_data = {
                "oauth_version": oauth_version,
                "oauth_nonce": oauth_nonce,
                "oauth_timestamp": str(oauth_client_timestamp),
                "oauth_consumer_key": consumer.key,
                "oauth_signature_method": oauth_signature_method,
            }

            # collect ALL request parameters (original + OAuth) for signing
            all_request_parameters = data.copy()
            all_request_parameters.update(oauth_signature_data)

            if oauth_signature_method == oauthlib_oauth1.SIGNATURE_RSA:
                # use RSA-SHA1 signature method
                oauth1_client = oauthlib_oauth1.Client(
                    consumer.key,
                    signature_method=oauth_signature_method,
                    rsa_key=rsa_key,
                )

                oauth_request = oauthlib_common.Request(
                    request.build_absolute_uri(request.path),
                    http_method=request.method,
                    body=all_request_parameters,
                )

                oauth_signature_data[
                    "oauth_signature"
                ] = oauth1_client.get_oauth_signature(oauth_request)
            else:
                # use HMAC-SHA1 signature method
                oauth_signature_data.update({"oauth_signature_method": "HMAC-SHA1"})

                # Create oauth request object to compute signature
                oauth_request = oauth2.Request.from_consumer_and_token(
                    consumer,
                    None,
                    request.method,
                    request.build_absolute_uri(request.path),
                    all_request_parameters,
                    is_form_encoded=True,
                )

                # Add signature to django request
                signature_method = oauth2.SignatureMethod_HMAC_SHA1()
                oauth_request.sign_request(signature_method, consumer, None)
                oauth_signature_data["oauth_signature"] = oauth_request.get_parameter(
                    "oauth_signature"
                ).decode("utf-8")

            use_auth_header_signature = request.META.pop(
                "use_auth_header_signature", False
            )
            if use_auth_header_signature:
                auth_header_string = "OAuth " + ",".join(
                    [
                        '{0}="{1}"'.format(key, value)
                        for key, value in oauth_signature_data.items()
                    ]
                )
                request.META["HTTP_AUTHORIZATION"] = auth_header_string
            else:
                data.update(oauth_signature_data)

        # Recreate the GET and POST QueryDicts to make them immutable, as in production
        request.POST = QueryDict(request.POST.urlencode().encode("utf-8"))
        request.GET = QueryDict(request.GET.urlencode().encode("utf-8"))

    def get_response(self, request):
        self._build_request(request)
        return ClientHandler.get_response(self, request)


class DeclarativeApisOAuthClient(Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.handler = OAuthClientHandler()

    def request(self, expected_status_code=None, **kwargs):
        response = super().request(**kwargs)
        if expected_status_code is not None:
            if response.status_code != expected_status_code:
                print(response.content.decode("utf-8"))
                raise AssertionError(
                    "Status code, {}, did not match expected status code, {}".format(
                        response.status_code, expected_status_code
                    )
                )
        return response

    def put(self, path, data=None, expected_status_code=None, **kwargs):
        if "content_type" not in kwargs:
            data = data or {}
            kwargs["content_type"] = "application/x-www-form-urlencoded"
            data_qd = QueryDict(mutable=True)
            data_qd.update(data)
            data = data_qd.urlencode()

        return super().put(
            path, data, expected_status_code=expected_status_code, **kwargs
        )
