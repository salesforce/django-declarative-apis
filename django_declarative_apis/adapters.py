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


class BaseHandler:
    defined_methods = {"get", "put", "patch", "post", "delete"}


class EndpointHandler:
    """
    Glue for combining the new-style endpoint definitions into the old-style piston handler

    """

    def __init__(self, **kwargs):
        super().__init__()

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
    """:code:`EndpointResource` is the DDA default resource adapter. It validates the
    configuration of the authentication handler, and in combination with Django’s native
    urls.py routes requests (through behavioral routing) to the same URL but to
    different handlers based on request attributes."""

    def __init__(self, authentication=None, **kwargs):
        super().__init__(EndpointHandler(**kwargs))

        if authentication is not None:
            django_declarative_apis.authentication.validate_authentication_config(
                authentication
            )
            self.authentication = authentication


def resource_adapter(*args, **kwargs):
    """:code:`resource_adapter()` is a helper function that finds the endpoint resource
    adapter from settings.py and calls that resource adapter.

    **resource_adapter takes two arguments:**

    Handler/Resource
        **Required |** The :code:`EndpointDefinition` implementation along with an HTTP
        verb.

    Authentication Handler
        **Optional |** If not specified, :code:`OAuth1.0a` will be used by default.

    **Example:**
    Handler defined in a separate file named :code:`handlers.py`.

    .. code-block::

        TodoEndpoint = resource_adapter(
            post=resources.TodoUpdateDefinition,
            get=resources.TodoDefinition,
            authentication={None: (NoAuth(),)},
        )

    Django app’s :code:`urls.py`.

    .. code-block::

        url(
            r"^tasks/$",
            handlers.TodoEndpoint,
        )
    """
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
