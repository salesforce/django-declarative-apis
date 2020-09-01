#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from django_declarative_apis.machinery import (
    EndpointDefinition,
    field,
    deferrable_task,
    endpoint_resource,
)
from django.core.cache import cache

from tests.models import TestModel


class SimpleEndpointDefinition(EndpointDefinition):
    def is_authorized(self):
        return True

    int_type_field = field(type=int)
    skip_task = field(type=bool, default=False)

    @endpoint_resource(type=TestModel)
    def resource(self):
        return TestModel.objects.create(int_field=1)

    def execution_decider(self):
        return self.skip_task

    @deferrable_task(execute_unless=execution_decider)
    @staticmethod
    def deferred_task(inst):
        cache.set("deferred_task_called", True)


class DictEndpointDefinition(EndpointDefinition):
    def is_authorized(self):
        return True

    @endpoint_resource(type=TestModel)
    def resource(self):
        inst = TestModel.objects.create(int_field=1)
        return {"test": inst, "deep_test": {"test": inst}}
