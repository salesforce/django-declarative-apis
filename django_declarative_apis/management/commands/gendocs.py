#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

# pragma: nocover
import pprint

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.urlresolvers import RegexURLResolver, RegexURLPattern

from django_declarative_apis.resources.resource import Resource


class Command(BaseCommand):
    help = "Generate documentation for declarative endpoints"

    def handle(self, *args, **options):
        pprint.pprint(self.traverse())

    def traverse(self, url_patterns=None, prefix=None):
        if url_patterns is None:
            url_patterns = __import__(settings.ROOT_URLCONF).urls.urlpatterns
        if prefix is None:
            prefix = ""

        result = []
        for url_pattern in url_patterns:
            endpoint_location = prefix + url_pattern.regex.pattern
            if isinstance(url_pattern, RegexURLResolver):
                result += self.traverse(url_pattern.url_patterns, endpoint_location)
            elif isinstance(url_pattern, RegexURLPattern):
                callback = url_pattern.callback
                if isinstance(callback, Resource):
                    handler = callback.handler
                    result.append(
                        {
                            "location": endpoint_location,
                            "endpoint": handler.documentation,
                        }
                    )
        return result
