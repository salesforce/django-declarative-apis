#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import time

from django_declarative_apis.authentication import AuthenticationFailure


class OAuthError(AuthenticationFailure):
    detail = None
    auth_header = None


class OAuthTimestampError(OAuthError):
    def __init__(self):
        self.detail = (
            "There was a problem with your timestamp. Please check your current system time."
            "Server time is {0}.".format(time.time())
        )
        start_time = int(time.time()) - 300
        end_time = int(time.time())
        self.auth_header = (
            'OAuth realm="API",oauth_problem=timestamp_refused'
            f"&oauth_acceptable_timestamps={start_time}-{end_time}"
        )


class OAuthMissingParameterError(OAuthError):
    def __init__(self, detail):
        self.detail = "Parameters missing: {0}".format(detail.split(":")[1])
        self.auth_header = 'OAuth realm="API",oauth_problem=parameter_absent&oauth_parameters_absent={0}'.format(
            detail.split(":")[1]
        )


class OAuthInvalidSignatureError(OAuthError):
    def __init__(self, detail):
        self.detail = "{0}.".format(detail)
        self.auth_header = 'OAuth realm="API",oauth_problem=signature_invalid'


class OAuthInvalidVersionError(OAuthError):
    def __init__(self):
        self.detail = "OAuth version (oauth_version parameter) should be 1.0"
        self.auth_header = 'OAuth realm="API",oauth_problem=version_rejected&oauth_acceptable_versions=1.0-1.0'


"""
Map internal OAuth errors to those specified in the OAuth Problem Reporting proposal
http://wiki.oauth.net/w/page/12238543/ProblemReporting
"""

error_to_human_readable_message = {
    "nonce_used": "Nonce was already used",
    "signature_method_rejected": 'Signature method must be "HMAC-SHA1" or "RSA-SHA1',
    "consumer_key_unknown": "Invalid consumer key or secret",
}


def build_error(error_message):
    if ("Timestamp given is invalid" in error_message) or (
        "Invalid timestamp" in error_message
    ):
        return OAuthTimestampError()
    if "parameter_absent" in error_message:
        return OAuthMissingParameterError(error_message)
    if "Invalid signature" in error_message:
        return OAuthInvalidSignatureError(error_message)
    if "Invalid OAuth version" in error_message:
        return OAuthInvalidVersionError()

    detail = error_to_human_readable_message.get(error_message, error_message)
    auth_header = 'OAuth realm="API",oauth_problem={0}'.format(error_message)

    return OAuthError(detail=detail, auth_header=auth_header)
