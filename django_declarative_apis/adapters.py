#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from importlib import import_module

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .machinery import BehavioralEndpointDefinitionRouter

import django_declarative_apis.authentication

# don't require resources unless this adapter is in use
try:
    from django_declarative_apis.resources.resource import Resource
except ImportError as e:  # noqa
    import traceback

    traceback.print_exc()
    Resource = object


class BaseHandler(object):
    defined_methods = {"get", "put", "patch", "post", "delete"}


class EndpointHandler(object):
    """
    Glue for combining the new-style endpoint definitions into the old-style piston handler

    """

    def __init__(self, **kwargs):
        super(EndpointHandler, self).__init__()

        self.method_handlers = {}
        for method, handler in kwargs.items():
            if method not in BaseHandler.defined_methods:
                raise TypeError(
                    "Unexpected keyword argument {0}: valid arguments are {1}".format(
                        method, BaseHandler.defined_methods
                    )
                )

            if isinstance(handler, (list, tuple)):
                self.method_handlers[
                    method.upper()
                ] = BehavioralEndpointDefinitionRouter(*handler)
            else:
                self.method_handlers[
                    method.upper()
                ] = BehavioralEndpointDefinitionRouter(handler)

        self.allowed_methods = self.method_handlers.keys()

    def __call__(self, *args, **kwargs):
        return self

    def handle_request(self, method, *args, **kwargs):
        return self.method_handlers[method](*args, **kwargs)

    @property
    def documentation(self):
        return {
            method: handler.documentation
            for method, handler in self.method_handlers.items()
        }


class EndpointResource(Resource):
    def __init__(self, authentication=None, **kwargs):
        super(EndpointResource, self).__init__(EndpointHandler(**kwargs))

        if authentication is not None:
            django_declarative_apis.authentication.validate_authentication_config(
                authentication
            )
            self.authentication = authentication


def resource_adapter(*args, **kwargs):
    setting_name = "DECLARATIVE_ENDPOINT_RESOURCE_ADAPTER"
    adapter_name = getattr(settings, setting_name, None)
    if not adapter_name:
        raise ImproperlyConfigured(setting_name)

    name_components = adapter_name.split(".")
    module_name = ".".join(name_components[:-1])
    module = import_module(module_name)
    class_name = name_components[-1]
    adapter_class = getattr(module, class_name)
    return adapter_class(*args, **kwargs)
