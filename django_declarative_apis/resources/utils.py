#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import warnings
from pydoc import locate

import django
from decorator import decorator
from django import get_version as django_version
from django.http import HttpResponse


def format_error(error):
    return "Django Declarative APIs (Django %s) crash report:\n\n%s" % (
        django_version(),
        error,
    )


class rc_factory(object):
    """
    Status codes.
    """

    CODES = dict(
        ALL_OK=("OK", 200),
        CREATED=("Created", 201),
        ACCEPTED=("Accepted", 202),
        DELETED=("", 204),  # 204 says "Don't send a body!"
        BAD_REQUEST=("Bad Request", 400),
        UNAUTHORIZED=("Unauthorized", 401),
        FORBIDDEN=("Forbidden", 403),
        NOT_FOUND=("Not Found", 404),
        NOT_ACCEPTABLE=("Not Acceptable", 406),
        DUPLICATE_ENTRY=("Conflict/Duplicate", 409),
        NOT_HERE=("Gone", 410),
        INTERNAL_ERROR=("Internal Error", 500),
        NOT_IMPLEMENTED=("Not Implemented", 501),
        THROTTLED=("Throttled", 503),
    )

    def __getattr__(self, attr):
        """
        Returns a fresh `HttpResponse` when getting
        an "attribute". This is backwards compatible
        with 0.2, which is important.
        """
        try:
            (r, c) = self.CODES.get(attr)
        except TypeError:
            raise AttributeError(attr)

        if (r, c) == ("Forbidden", 401):  # pragma: nocover
            warnings.warn(
                "In future versions rc.FORBIDDEN will return 403 and rc.UNAUTHORIZED 401.",
                PendingDeprecationWarning,
            )
            warnings.warn(
                "Please change all your rc.FORBIDDEN for rc.UNAUTHORIZED",
                DeprecationWarning,
            )

        class HttpResponseWrapper(HttpResponse):
            """
            Wrap HttpResponse and make sure that the internal _is_string
            flag is updated when the _set_content method (via the content
            property) is called
            """

            def _set_content(self, content):
                """
                Set the _container and _is_string /
                _base_content_is_iter properties based on the type of
                the value parameter. This logic is in the construtor
                for HttpResponse, but doesn't get repeated when
                setting HttpResponse.content although this bug report
                (feature request) suggests that it should:
                http://code.djangoproject.com/ticket/9403
                """
                is_string = False
                if not isinstance(content, str) and hasattr(content, "__iter__"):
                    self._container = content
                else:
                    self._container = [content]
                    is_string = True
                if django.VERSION >= (1, 4):
                    self._base_content_is_iter = not is_string
                else:  # pragma: nocover
                    self._is_string = is_string

            try:
                content = property(HttpResponse._get_content, _set_content)
            except Exception:

                @HttpResponse.content.setter
                def content(self, content):
                    self._set_content(content)

        return HttpResponseWrapper(r, content_type="text/plain", status=c)


rc = rc_factory()


class FormValidationError(Exception):
    def __init__(self, form):
        self.form = form


class HttpStatusCode(Exception):
    def __init__(self, response):
        self.response = response


def coerce_put_post(request):
    """
    Django doesn't particularly understand REST.
    In case we send data over PUT, Django won't
    actually look at the data and load it. We need
    to twist its arm here.

    The try/except abominiation here is due to a bug
    in mod_python. This should fix it.
    """
    if request.method == "PUT":
        # Bug fix: if _load_post_and_files has already been called, for
        # example by middleware accessing request.POST, the below code to
        # pretend the request is a POST instead of a PUT will be too late
        # to make a difference. Also calling _load_post_and_files will result
        # in the following exception:
        #   AttributeError: You cannot set the upload handlers after the upload has been processed.
        # The fix is to check for the presence of the _post field which is set
        # the first time _load_post_and_files is called (both by wsgi.py and
        # modpython.py). If it's set, the request has to be 'reset' to redo
        # the query value parsing in POST mode.
        if hasattr(request, "_post"):
            del request._post
            del request._files

        try:
            request.method = "POST"
            request._load_post_and_files()
            request.method = "PUT"
        except AttributeError:  # pragma: nocover
            # TODO: Not quite sure how this block is supposed to be hit. Maybe something internal in
            # django.http.request.HttpRequest._load_post_and_files()? If request.method didn't exist then we'd
            # be running into issues with the above check
            request.META["REQUEST_METHOD"] = "POST"
            request._load_post_and_files()
            request.META["REQUEST_METHOD"] = "PUT"

        request.PUT = request.POST


class MimerDataException(Exception):
    """
    Raised if the content_type and data don't match
    """

    pass


class Mimer(object):
    TYPES = dict()

    def __init__(self, request):
        self.request = request

    def is_multipart(self):
        content_type = self.content_type()

        if content_type is not None:
            return content_type.lstrip().startswith("multipart")

        return False

    def loader_for_type(self, ctype):
        """
        Gets a function ref to deserialize content
        for a certain mimetype.
        """
        for loadee, mimes in Mimer.TYPES.items():
            for mime in mimes:
                if ctype.startswith(mime):
                    return loadee

    def content_type(self):
        """
        Returns the content type of the request in all cases where it is
        different than a submitted form - application/x-www-form-urlencoded
        """
        type_formencoded = "application/x-www-form-urlencoded"

        # Content-Type format:
        # http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.17
        ctype = self.request.META.get("CONTENT_TYPE", type_formencoded).split(";")[0]

        if type_formencoded in ctype:
            return None

        return ctype

    def translate(self):
        """
        Will look at the `Content-type` sent by the client, and maybe
        deserialize the contents into the format they sent. This will
        work for JSON, YAML, XML and Pickle. Since the data is not just
        key-value (and maybe just a list), the data will be placed on
        `request.data` instead, and the handler will have to read from
        there.

        It will also set `request.content_type` so the handler has an easy
        way to tell what's going on. `request.content_type` will always be
        None for form-encoded and/or multipart form data (what your browser sends.)
        """
        ctype = self.content_type()
        self.request.content_type = ctype

        if not self.is_multipart() and ctype:
            loadee = self.loader_for_type(ctype)

            if loadee:
                try:
                    data = self.request.body
                    # PY3: Loaders usually don't work with bytes:
                    data = data.decode("utf-8")
                    self.request.data = loadee(data)

                    # Reset both POST and PUT from request, as its
                    # misleading having their presence around.
                    self.request.POST = self.request.PUT = dict()
                except (TypeError, ValueError):
                    # This also catches if loadee is None.
                    raise MimerDataException
            else:
                self.request.data = None

        return self.request

    @classmethod
    def register(cls, loadee, types):
        cls.TYPES[loadee] = types

    @classmethod
    def unregister(cls, loadee):
        return cls.TYPES.pop(loadee)


def translate_mime(request):
    request = Mimer(request).translate()


def require_mime(*mimes):
    """
    Decorator requiring a certain mimetype. There's a nifty
    helper called `require_extended` below which requires everything
    we support except for post-data via form.
    """

    @decorator
    def wrap(f, self, request, *args, **kwargs):
        m = Mimer(request)
        realmimes = set()

        rewrite = {
            "json": "application/json",
            "yaml": "application/x-yaml",
            "xml": "text/xml",
            "pickle": "application/python-pickle",
        }

        for idx, mime in enumerate(mimes):
            realmimes.add(rewrite.get(mime, mime))

        if not m.content_type() in realmimes:
            return rc.BAD_REQUEST

        return f(self, request, *args, **kwargs)

    return wrap


require_extended = require_mime("json", "yaml", "xml", "pickle")


def locate_object(namespaced_name):
    name_components = namespaced_name.split(".")
    module_name = ".".join(name_components[:-1])
    module = locate(module_name)
    class_name = name_components[-1]
    return getattr(module, class_name)


def instantiate_class(namespaced_class_name, *args, **kwargs):
    cls = locate_object(namespaced_class_name)
    return cls(*args, **kwargs)


def preprocess_rsa_key(key_str):
    """Make Android and iOS RSA keys compatible with cryptography library.

    Android and iOS have slightly wonky, non-standard key formats. This updates
    the key to be standardized and compatible with pyca/cryptography.
    """
    if key_str.startswith("-----BEGIN CERTIFICATE"):
        key_str = key_str.replace("CERTIFICATE", "PUBLIC KEY")
    elif key_str.startswith("-----BEGIN RSA"):
        key_str = key_str.replace("BEGIN RSA", "BEGIN").replace("END RSA", "END")
    return key_str
