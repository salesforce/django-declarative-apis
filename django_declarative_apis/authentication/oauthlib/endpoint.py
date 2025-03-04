#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import logging

from oauthlib.oauth1 import SignatureOnlyEndpoint
from oauthlib.oauth1.rfc5849 import SIGNATURE_RSA
from oauthlib.oauth1.rfc5849 import errors, signature

from django_declarative_apis.resources.utils import preprocess_rsa_key

log = logging.getLogger(__name__)


class TweakedSignatureOnlyEndpoint(SignatureOnlyEndpoint):
    """An endpoint only responsible for verifying an oauthlib signature.
    This class modified oauthlib.oauth1.SignatureOnlyEndpoint so that
    the validate_request() method will support returning an error
    message to support our API OAuth error messages

    Altered lines are marked with # TOOPHER
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validation_error_message = ""

    def validate_request(self, uri, http_method="GET", body=None, headers=None):
        """Validate a signed OAuth request.

        :param uri: The full URI of the token request.
        :param http_method: A valid HTTP verb, i.e. GET, POST, PUT, HEAD, etc.
        :param body: The request body as a string.
        :param headers: The request headers as a dict.
        :returns: A tuple of 2 elements.
                  1. True if valid, False otherwise.
                  2. An oauthlib.common.Request object.
        """
        try:
            request = self._create_request(uri, http_method, body, headers)
        except errors.OAuth1Error as e:  # noqa
            return False, None

        try:
            self._check_transport_security(request)
            self._check_mandatory_parameters(request)
        except errors.OAuth1Error as e:
            self.validation_error_message = e.description  # TOOPHER
            return False, request

        if not self.request_validator.validate_timestamp_and_nonce(
            request.client_key, request.timestamp, request.nonce, request
        ):
            return False, request

        # The server SHOULD return a 401 (Unauthorized) status code when
        # receiving a request with invalid client credentials.
        # Note: This is postponed in order to avoid timing attacks, instead
        # a dummy client is assigned and used to maintain near constant
        # time request verification.
        #
        # Note that early exit would enable client enumeration
        valid_client = self.request_validator.validate_client_key(
            request.client_key, request
        )
        if not valid_client:
            request.client_key = self.request_validator.dummy_client

        valid_signature = self._check_signature(request)

        # We delay checking validity until the very end, using dummy values for
        # calculations and fetching secrets/keys to ensure the flow of every
        # request remains almost identical regardless of whether valid values
        # have been supplied. This ensures near constant time execution and
        # prevents malicious users from guessing sensitive information
        v = all((valid_client, valid_signature))
        if not v:
            log.info(
                'ev=oauth1, valid_client=%s, valid_signature=%s, msg="authentication failed"',
                valid_client,
                valid_signature,
            )

        if valid_client and not valid_signature:  # TOOPHER
            norm_params = signature.normalize_parameters(request.params)  # TOOPHER
            uri = signature.base_string_uri(request.uri)  # TOOPHER
            base_signing_string = signature.signature_base_string(
                request.http_method, uri, norm_params
            )  # TOOPHER
            self.validation_error_message = (
                "Invalid signature. Expected signature base string: {0}".format(
                    base_signing_string
                )
            )  # TOOPHER
        return v, request

    def _check_signature(self, request):
        if request.signature_method == SIGNATURE_RSA:  # pragma: nocover
            key_str = self.request_validator.get_rsa_key(request.client_key, request)
            key_str = preprocess_rsa_key(key_str)
            return signature.verify_rsa_sha1(request, key_str)

        return super()._check_signature(request)
