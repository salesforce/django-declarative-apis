#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import json
from http import HTTPStatus

from django.test import TestCase

from . import testutils

from django_declarative_apis import models as auth_models


class DeclarativeApisTestCase(TestCase):
    client_class = testutils.DeclarativeApisOAuthClient

    def setUp(self):
        self.consumer = auth_models.OauthConsumer.objects.create()

    def test_simplest_endpoint(self):
        self.client.get(
            "/simple", consumer=self.consumer, expected_status_code=HTTPStatus.OK
        )

    def test_typed_parameter(self):
        response = self.client.get(
            "/simple?int_type_field=not_an_int",
            consumer=self.consumer,
            expected_status_code=HTTPStatus.BAD_REQUEST,
        )
        error = json.loads(response.content.decode("utf-8"))
        self.assertEqual(error["error_code"], 703)
        self.assertTrue("Invalid values for field(s): int_type_field")
