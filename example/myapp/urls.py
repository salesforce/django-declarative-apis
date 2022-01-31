#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from django.urls import re_path

from django_declarative_apis import authentication
from django_declarative_apis.adapters import resource_adapter

from myapp import resources


class NoAuth(authentication.Authenticator):
    """A custom NoAuth class to treat all requests as authenticated

    By default, django-declarative-apis requires authentication. This allows us to get around that.
    """

    @staticmethod
    def is_authenticated(request):
        return True

    def challenge(self, error):
        super().challenge(error)


urlpatterns = [
    re_path(
        r"^me$",
        resource_adapter(get=resources.MeDefinition, post=resources.MeUpdateDefinition),
    ),
    re_path(
        r"^ping$",
        resource_adapter(
            get=resources.PingDefinition, authentication={None: (NoAuth(),)}
        ),
    ),
]
