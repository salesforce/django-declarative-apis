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
                    "expandable_generic": {"id": "1234"},
                    "__expandable__": [
                        "expandable_dict",
                        "expandable_string",
                        "expandable_generic",
                    ],
                },
                "deep_test": {
                    "test": {
                        "pk": 1,
                        "int_field": 1,
                        "expandable_generic": {"id": "1234"},
                        "__expandable__": [
                            "expandable_dict",
                            "expandable_string",
                            "expandable_generic",
                        ],
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

    def test_dict_field_endpoint(self):
        good_dict = {
            "length": 11,
            "description": "This is a description",
            "timestamp": "2022-10-24T00:00:00",
            "words": ["foo", "bar", "baz", "quux"],
        }
        test_data = [
            (good_dict, HTTPStatus.OK, "good dict"),
            ({}, HTTPStatus.OK, "empty_dict"),
            (list(good_dict), HTTPStatus.BAD_REQUEST, "list"),
            ("a string", HTTPStatus.BAD_REQUEST, "string"),
            (1337, HTTPStatus.BAD_REQUEST, "int"),
        ]

        for dct, expected_status, message in test_data:
            data = {"dict_type_field": dct}
            with self.subTest(message):
                response = self.client.post(
                    "/dictfield",
                    consumer=self.consumer,
                    data=data,
                    expected_status_code=expected_status,
                    content_type="application/json",
                )
                if expected_status == HTTPStatus.OK:
                    self.assertDictEqual(json.loads(response.content), data)

    def test_pydantic_field_endpoint(self):
        good_dict = {
            "length": 11,
            "description": "This is a description",
            "timestamp": "2022-10-24T00:00:00",
            "words": ["foo", "bar", "baz", "quux"],
        }
        test_data = [
            (good_dict, HTTPStatus.OK, "no errors"),
            ({**good_dict, "length": "eleven"}, HTTPStatus.BAD_REQUEST, "bad length"),
            (
                {**good_dict, "description": ["one", "two"]},
                HTTPStatus.BAD_REQUEST,
                "bad description",
            ),
            (
                {**good_dict, "timestamp": "2022-10-24T99:99:99"},
                HTTPStatus.BAD_REQUEST,
                "bad timestamp",
            ),
            (
                {**good_dict, "words": "foo bar baz quux"},
                HTTPStatus.BAD_REQUEST,
                "bad words",
            ),
        ]

        for dct, expected_status, message in test_data:
            data = {"pydantic_type_field": dct}
            with self.subTest(message):
                response = self.client.post(
                    "/pydanticfield",
                    consumer=self.consumer,
                    data=data,
                    expected_status_code=expected_status,
                    content_type="application/json",
                )
                if expected_status == HTTPStatus.OK:
                    self.assertDictEqual(json.loads(response.content), data)

    def test_nested_pydantic_field_endpoint(self):
        good_dict = {"b": "hello", "c": {"a": "world"}}
        test_data = [
            (good_dict, HTTPStatus.OK, "no errors"),
            ({**good_dict, "b": list("abc")}, HTTPStatus.BAD_REQUEST, "bad b"),
            ({**good_dict, "c": 11}, HTTPStatus.BAD_REQUEST, "bad c"),
            ({**good_dict, "c": {"a": list("abc")}}, HTTPStatus.BAD_REQUEST, "bad a"),
            ({**good_dict, "c": {}}, HTTPStatus.BAD_REQUEST, "missing a"),
            (
                {k: v for (k, v) in good_dict.items() if k != "b"},
                HTTPStatus.BAD_REQUEST,
                "missing b",
            ),
            (
                {k: v for (k, v) in good_dict.items() if k != "c"},
                HTTPStatus.BAD_REQUEST,
                "missing c",
            ),
        ]

        for dct, expected_status, message in test_data:
            data = {"nested_pydantic_type_field": dct}
            with self.subTest(message):
                response = self.client.post(
                    "/nestedpydanticfield",
                    consumer=self.consumer,
                    data=data,
                    expected_status_code=expected_status,
                    content_type="application/json",
                )
                if expected_status == HTTPStatus.OK:
                    self.assertDictEqual(json.loads(response.content), data)
