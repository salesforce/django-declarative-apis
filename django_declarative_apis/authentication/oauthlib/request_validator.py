#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import logging

from django.conf import settings
from django.core.cache import cache
from oauthlib.oauth1 import RequestValidator

from django_declarative_apis import models as oauth_models


logger = logging.getLogger(__name__)


class DjangoRequestValidator(RequestValidator):
    TIMESTAMP_THRESHOLD = 300

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.consumer = None
        self.validation_error_message = ""

    @property
    def enforce_ssl(self):
        return getattr(settings, "REQUIRE_HTTPS_FOR_OAUTH", True)

    def check_client_key(self, client_key):
        return bool(client_key)

    def check_nonce(self, nonce):
        return bool(
            nonce
        )  # we didn't enforce any minimum length on nonces previously...

    def validate_timestamp_and_nonce(
        self,
        client_key,
        timestamp,
        nonce,
        request,
        request_token=None,
        access_token=None,
    ):
        request_token = request_token or ""
        access_token = access_token or ""
        cache_key = "{0}:{1}:{2}:{3}".format(
            client_key, request_token, access_token, nonce
        )
        cache_created = cache.add(cache_key, True, self.TIMESTAMP_THRESHOLD * 2)
        if not cache_created:
            self.validation_error_message = "nonce_used"
        return cache_created

    def validate_client_key(self, client_key, request):
        self.consumer = oauth_models.get_consumer(client_key)
        if self.consumer is None:
            self.validation_error_message = "consumer_key_unknown"
            logger.error(
                'ev=oauth1, error=%s, client_key="%s"',
                self.validation_error_message,
                client_key,
            )
            return False
        return True

    def get_client_secret(self, client_key, request):
        try:
            if self.consumer.rsa_public_key_pem:
                return None

            return self.consumer.secret
        except Exception:  # noqa
            logger.error('ev=dda_client_secret, status=error, key="%s"', client_key)
            return ""

    def get_rsa_key(self, client_key, request):
        try:
            return self.consumer.rsa_public_key_pem
        except Exception:  # noqa
            logger.error('ev=dda_rsa_key, status=error, key="%s"', client_key)
            return ""

    @property
    def dummy_client(self):
        class DummyClient:
            def __init__(self, *args, **kwargs):
                self.secret = ""
                self.key = ""
                self.rsa_public_key_base64 = ""

        return DummyClient()
