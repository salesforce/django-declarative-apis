#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import django.test
from django_declarative_apis import models


def test_consumer_getter(key):
    return key


uncallable = "foo"


class ModelsTestCase(django.test.TestCase):
    def test_get_consumer(self):
        with self.settings(
            DECLARATIVE_ENDPOINT_CONSUMER_GETTER="tests.test_models.test_consumer_getter"
        ):
            self.assertEqual(models.get_consumer("foo"), "foo")

    def test_get_consumer_non_callable(self):
        with self.settings(
            DECLARATIVE_ENDPOINT_CONSUMER_GETTER="tests.test_models.uncallable"
        ):
            self.assertRaises(TypeError, models.get_consumer, "foo")
