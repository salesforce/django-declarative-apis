#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import json
import logging

from django.http import HttpResponse
from oauthlib.oauth1.rfc5849 import signature

from django_declarative_apis.authentication import (
    Authenticator,
    AuthenticatorHint,
    AuthenticationSuccess,
    AuthenticationFailure,
)
from django_declarative_apis.authentication.oauthlib.endpoint import (
    TweakedSignatureOnlyEndpoint,
)
from django_declarative_apis.authentication.oauthlib.oauth_errors import OAuthError
from django_declarative_apis.authentication.oauthlib.request_validator import (
    DjangoRequestValidator,
)

from . import oauth_errors

TwoLeggedOauth1Hint = AuthenticatorHint("OAuth ")


logger = logging.getLogger(__name__)


class TwoLeggedOauth1(Authenticator):
    def validate_missing_parameters(self, request, parameters=None):
        parameters = parameters or []

        """ Ensures that the request contains all required parameters. """
        params = [
            "oauth_consumer_key",
            "oauth_nonce",
            "oauth_signature",
            "oauth_signature_method",
            "oauth_timestamp",
        ]

        params.extend(parameters)

        collected_request_parameters = dict(
            signature.collect_parameters(
                uri_query=request.GET.urlencode(),
                body=request.POST.dict(),
                headers=request.META,
                exclude_oauth_signature=False,
            )
        )
        try:
            missing = list(
                param for param in params if param not in collected_request_parameters
            )
        except Exception:  # pragma: nocover
            missing = params

        if missing:
            error_message = "parameter_absent:{}".format(",".join(missing))
            logger.error(error_message)
            missing_param_info = oauth_errors.build_error(error_message)
            request.auth_header = getattr(missing_param_info, "auth_header", None)
            return missing_param_info
        else:
            return True

    def is_authenticated(self, request):
        param_check = self.validate_missing_parameters(request)
        if isinstance(param_check, AuthenticationFailure):
            return param_check

        uri = request.build_absolute_uri(request.path)
        url_querystring = request.GET.urlencode()
        if url_querystring:
            uri += "?" + url_querystring

        body_form_data = request.POST.urlencode()

        headers = {k: v for (k, v) in request.META.items() if isinstance(v, str)}

        if body_form_data and "Content-Type" not in headers:  # pragma: nocover
            # TODO: is this only necessary because our test client sucks?
            # TODO (DB): is this still needed?
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        # Verify request
        try:
            validator = DjangoRequestValidator(request)
            endpoint = TweakedSignatureOnlyEndpoint(validator)
            result, _ = endpoint.validate_request(
                uri, http_method=request.method, body=body_form_data, headers=headers
            )

            if result:
                request.consumer = validator.consumer

            error_message = (
                endpoint.validation_error_message or validator.validation_error_message
            )

            if result:
                return AuthenticationSuccess()
            else:
                return oauth_errors.build_error(error_message)
        except Exception as e:
            if hasattr(e, "message"):
                logger.error("Invalid oauthlib request: " + e.message)
            return AuthenticationFailure()

    def authenticate_header(self, request):
        return getattr(request, "auth_header", "Unknown OAuth Error")

    def challenge(self, oauth_error=None):
        """
        Returns a 401 response with a small bit on
        what OAuth is, and where to learn more about it.

        When this was written, browsers did not understand
        OAuth authentication on the browser side, and hence
        the helpful template we render. Maybe some day in the
        future, browsers will take care of this stuff for us
        and understand the 401 with the realm we give it.
        """

        if oauth_error is None:
            oauth_error = OAuthError()

        response = HttpResponse()
        response.status_code = 401

        response["WWW-Authenticate"] = oauth_error.auth_header

        content = {"error_code": 401, "error_message": oauth_error.detail}
        response.content = json.dumps(content)
        response["content-type"] = "application/json"

        return response
