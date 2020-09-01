#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import json
from http import HTTPStatus

from django.test import TestCase, override_settings
from django.core.cache import cache

from . import testutils

from django_declarative_apis import models as auth_models


@override_settings(DECLARATIVE_ENDPOINT_TASKS_FORCE_SYNCHRONOUS=True)
class DeclarativeApisTestCase(TestCase):
    client_class = testutils.DeclarativeApisOAuthClient

    def setUp(self):
        self.consumer = auth_models.OauthConsumer.objects.create()

    def test_simplest_endpoint(self):
        self.client.get(
            "/simple", consumer=self.consumer, expected_status_code=HTTPStatus.OK
        )

    def test_dict_endpoint(self):
        resp = self.client.get(
            "/dict", consumer=self.consumer, expected_status_code=HTTPStatus.OK
        )
        data = resp.json()
        self.assertEqual(
            data,
            {
                "test": {
                    "pk": 1,
                    "int_field": 1,
                    "__expandable__": ["expandable_dict", "expandable_string"],
                },
                "deep_test": {
                    "test": {
                        "pk": 1,
                        "int_field": 1,
                        "__expandable__": ["expandable_dict", "expandable_string"],
                    }
                },
            },
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

    def test_skip_deferred_task(self):
        cache.set("deferred_task_called", False)
        self.client.get(
            "/simple?skip_task=True",
            consumer=self.consumer,
            expected_status_code=HTTPStatus.OK,
        )
        self.assertFalse(cache.get("deferred_task_called"))

    def test_run_deferred_task(self):
        cache.set("deferred_task_called", False)
        self.client.get(
            "/simple", consumer=self.consumer, expected_status_code=HTTPStatus.OK
        )
        self.assertTrue(cache.get("deferred_task_called"))
