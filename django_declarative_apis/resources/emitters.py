#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import json
import pickle
from io import StringIO

try:
    # yaml isn't standard with python.  It shouldn't be required if it
    # isn't used.
    import yaml
except ImportError:  # pragma: nocover
    yaml = None

from django.utils.encoding import smart_str
from django.utils.xmlutils import SimplerXMLGenerator

try:
    from django.core.serializers.json import (
        DateTimeAwareJSONEncoder as DjangoJSONEncoder,
    )
except ImportError:
    from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.core import serializers

from .utils import HttpStatusCode, Mimer


class Emitter:
    """
    Super emitter. All other emitters should subclass
    this one. It has the `construct` method which
    conveniently returns a serialized `dict`. This is
    usually the only method you want to use in your
    emitter. See below for examples.

    `RESERVED_FIELDS` was introduced when better resource
    method detection came, and we accidentially caught these
    as the methods on the handler. Issue58 says that's no good.
    """

    EMITTERS = {}
    RESERVED_FIELDS = {
        "read",
        "update",
        "create",
        "delete",
        "model",
        "anonymous",
        "allowed_methods",
        "fields",
        "exclude",
    }

    def __init__(self, payload, handler, anonymous=True):
        self.data = payload
        self.handler = handler
        self.anonymous = anonymous

        if isinstance(self.data, Exception):
            raise Exception from self.data

    def method_fields(self, handler, fields):
        if not handler:
            return {}

        ret = dict()

        for field in fields - Emitter.RESERVED_FIELDS:
            t = getattr(handler, str(field), None)

            if t and callable(t):
                ret[field] = t

        return ret

    def construct(self):
        if isinstance(self.data, HttpResponse):
            raise HttpStatusCode(self.data)
        else:
            return self.data

    def render(self, request):
        """
        This super emitter does not implement `render`,
        this is a job for the specific emitter below.
        """
        raise NotImplementedError("Please implement render.")

    def stream_render(self, request, stream=True):
        """
        Tells our patched middleware not to look
        at the contents, and returns a generator
        rather than the buffered string. Should be
        more memory friendly for large datasets.
        """
        yield self.render(request)

    @classmethod
    def get(cls, format):
        """
        Gets an emitter, returns the class and a content-type.
        """
        if format in cls.EMITTERS:
            return cls.EMITTERS.get(format)

        raise ValueError("No emitters found for type %s" % format)

    @classmethod
    def register(cls, name, klass, content_type="text/plain"):
        """
        Register an emitter.

        Parameters::
         - `name`: The name of the emitter ('json', 'xml', 'yaml', ...)
         - `klass`: The emitter class.
         - `content_type`: The content type to serve response as.
        """
        cls.EMITTERS[name] = (klass, content_type)

    @classmethod
    def unregister(cls, name):
        """
        Remove an emitter from the registry. Useful if you don't
        want to provide output in one of the built-in emitters.
        """
        return cls.EMITTERS.pop(name, None)


class XMLEmitter(Emitter):
    def _to_xml(self, xml, data):
        if isinstance(data, (list, tuple)):
            for item in data:
                xml.startElement("resource", {})
                self._to_xml(xml, item)
                xml.endElement("resource")
        elif isinstance(data, dict):
            for key, value in data.items():
                xml.startElement(key, {})
                self._to_xml(xml, value)
                xml.endElement(key)
        else:
            xml.characters(smart_str(data))

    def render(self, request):
        stream = StringIO()

        xml = SimplerXMLGenerator(stream, "utf-8")
        xml.startDocument()
        xml.startElement("response", {})

        self._to_xml(xml, self.construct())

        xml.endElement("response")
        xml.endDocument()

        return stream.getvalue()


Emitter.register("xml", XMLEmitter, "text/xml; charset=utf-8")
Mimer.register(lambda *a: None, ("text/xml",))


class JSONEmitter(Emitter):
    """
    JSON emitter, understands timestamps.
    """

    def decode(self, data):
        if isinstance(data, list):
            for num, val in enumerate(data):
                try:
                    data[num] = val.decode("utf8")
                except AttributeError:
                    pass
        return data

    def render(self, request):
        cb = request.GET.get("callback", None)
        assert cb is None, "JSONP Callbacks not supported"
        seria = self.decode(self.construct())
        if isinstance(seria, list):
            if len(seria) == 0 or (len(seria) == 1 and len(seria[0]) == 0):
                # the body is empty, no need to run json.dumps
                return ""

        # Callback
        # TODO: do we care about JSONP?
        # if cb and is_valid_jsonp_callback_value(cb):
        #     return '%s(%s)' % (cb, seria)

        return json.dumps(
            seria,
            cls=DjangoJSONEncoder,
            ensure_ascii=False,
            indent=4,
        )


Emitter.register("json", JSONEmitter, "application/json; charset=utf-8")
Mimer.register(json.loads, ("application/json",))


class YAMLEmitter(Emitter):
    """
    YAML emitter, uses `safe_dump` to omit the
    specific types when outputting to non-Python.
    """

    def render(self, request):
        return yaml.safe_dump(self.construct())


if yaml:  # Only register yaml if it was import successfully.
    Emitter.register("yaml", YAMLEmitter, "application/x-yaml; charset=utf-8")
    Mimer.register(lambda s: dict(yaml.safe_load(s)), ("application/x-yaml",))


class PickleEmitter(Emitter):
    """
    Emitter that returns Python pickled.
    """

    def render(self, request):
        return pickle.dumps(self.construct())


Emitter.register("pickle", PickleEmitter, "application/python-pickle")

"""
WARNING: Accepting arbitrary pickled data is a huge security concern.
The unpickler has been disabled by default now, and if you want to use
it, please be aware of what implications it will have.

Read more: https://web.archive.org/web/20130423223601/http://nadiana.com/python-pickle-insecure

Uncomment the line below to enable it. You're doing so at your own risk.
"""


# Mimer.register(pickle.loads, ('application/python-pickle',))


class DjangoEmitter(Emitter):
    """
    Emitter for the Django serialized format.
    """

    def render(self, request, format="xml"):
        if isinstance(self.data, HttpResponse):
            return self.data
        elif isinstance(self.data, (int, str)):
            response = self.data
        else:
            response = serializers.serialize(format, self.data, indent=True)

        return response


Emitter.register("django", DjangoEmitter, "text/xml; charset=utf-8")
