#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from django.urls import re_path

from . import views

from django_declarative_apis.adapters import resource_adapter

UUID4_REGEX = r"[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}"

urlpatterns = [
    re_path(r"^simple", resource_adapter(get=views.SimpleEndpointDefinition)),
    re_path(r"^dict", resource_adapter(get=views.DictEndpointDefinition)),
]
