#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import unittest

from django_declarative_apis.authentication.oauthlib import oauth_errors


class OAuthErrorsTestCase(unittest.TestCase):
    def test_oauth_invalid_version_error(self):
        err = oauth_errors.OAuthInvalidVersionError()
        self.assertEqual(
            err.detail, "OAuth version (oauth_version parameter) should be 1.0"
        )
        self.assertEqual(
            err.auth_header,
            'OAuth realm="API",oauth_problem=version_rejected&oauth_acceptable_versions=1.0-1.0',
        )

    def test_build_error(self):
        self.assertIsInstance(
            oauth_errors.build_error("...Timestamp given is invalid..."),
            oauth_errors.OAuthTimestampError,
        )

        self.assertIsInstance(
            oauth_errors.build_error("...parameter_absent...foo:bar"),
            oauth_errors.OAuthMissingParameterError,
        )

        self.assertIsInstance(
            oauth_errors.build_error("...Invalid signature..."),
            oauth_errors.OAuthInvalidSignatureError,
        )

        self.assertIsInstance(
            oauth_errors.build_error("...Invalid OAuth version..."),
            oauth_errors.OAuthInvalidVersionError,
        )

        # an unknown error happened
        generic_error = oauth_errors.build_error("something bad happened")
        self.assertIsInstance(generic_error, oauth_errors.OAuthError)
        self.assertEqual(generic_error.detail, "something bad happened")
        self.assertEqual(
            generic_error.auth_header,
            'OAuth realm="API",oauth_problem=something bad happened',
        )

        # a known error
        for key, msg in oauth_errors.error_to_human_readable_message.items():
            generic_error = oauth_errors.build_error(key)
            self.assertIsInstance(generic_error, oauth_errors.OAuthError)
            self.assertEqual(generic_error.detail, msg)
            self.assertEqual(
                generic_error.auth_header, f'OAuth realm="API",oauth_problem={key}'
            )
