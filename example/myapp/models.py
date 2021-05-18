#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from django.db import models
import django_declarative_apis.models


class User(models.Model):
    consumer = models.ForeignKey(
        django_declarative_apis.models.OauthConsumer, on_delete=models.CASCADE
    )
    name = models.CharField(max_length=50, null=False, blank=False)
