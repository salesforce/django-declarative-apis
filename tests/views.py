#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from django_declarative_apis.machinery import EndpointDefinition, field


class SimpleEndpointDefinition(EndpointDefinition):
    def is_authorized(self):
        return True

    int_type_field = field(type=int)

    @property
    def resource(self):
        return {}
