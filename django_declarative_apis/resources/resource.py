#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import collections
import http.client
import json
import logging
import sys

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage
from django.http import Http404
from django.http import HttpResponse, HttpResponseNotAllowed
from django.views.debug import ExceptionReporter
from django.views.decorators.vary import vary_on_headers

from django_declarative_apis import authentication
from django_declarative_apis.machinery import errors
from .emitters import Emitter
from .utils import HttpStatusCode, coerce_put_post, instantiate_class, locate_object
from .utils import MimerDataException, rc, translate_mime

CHALLENGE = object()


logger = logging.getLogger(__name__)


def _deserialize_json(req):
    if req.method == "POST":
        req.POST = json.loads(req.body)
    return req


_DESERIALIZERS = collections.defaultdict(
    lambda: lambda r: r, {"application/json": _deserialize_json}
)


class HttpResponseServerError(HttpResponse):
    def __init__(self, *args, **kwargs):
        self.error = kwargs.pop("error", None)
        super().__init__(*args, **kwargs)


class Resource:
    """
    Resource. Create one for your URL mappings, just
    like you would with Django. Takes one argument,
    the handler. The second argument is optional, and
    is an authentication handler. If not specified,
    `NoAuthentication` will be used by default.
    """

    callmap = {"GET": "read", "POST": "create", "PUT": "update", "DELETE": "delete"}

    def __init__(self, handler):
        if not callable(handler):
            raise AttributeError("Handler not callable.")

        self.handler = handler()
        self.csrf_exempt = getattr(self.handler, "csrf_exempt", True)

        try:
            # DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS should be defined as:
            # [
            #   (
            #       (<tuple of header hints),
            #       <implementation>
            #   ),
            # ]
            # for example:
            # DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS = [
            #   (
            #       (None, 'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth1Hint'),
            #       'django_declarative_apis.authentication.oauthlib.oauth1.TwoLeggedOauth'
            #   ),
            # ]
            # The above effectively states 'try using the oauth handler any time we see a header that looks like
            # "Authorization: OAuth ..." as well as a fallback mechanism should no other header matching authenticators
            # pass. This can be useful for more complex authenticators such as OAuth 1.0, where auth information can
            # be passed through headers, query params or even request bodies.
            authentication_class_list = (
                settings.DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS
            )
        except (KeyError, AttributeError):
            raise ImproperlyConfigured(
                "must specify settings.DECLARATIVE_ENDPOINT_AUTHENTICATION_HANDLERS"
            )

        self.authentication = collections.defaultdict(list)
        for (
            authentication_hints,
            authentication_class_name,
        ) in authentication_class_list:
            authenticator_instance = instantiate_class(authentication_class_name)

            for hint_path in authentication_hints:
                if hint_path is not None:
                    hint_instance = locate_object(hint_path)
                else:
                    hint_instance = None

                self.authentication[hint_instance].append(authenticator_instance)

        authentication.validate_authentication_config(self.authentication)

        # Erroring
        self.email_errors = getattr(settings, "DECLARATIVE_EMAIL_ERRORS", True)
        self.display_errors = getattr(settings, "DECLARATIVE_DISPLAY_ERRORS", True)
        self.stream = getattr(settings, "DECLARATIVE_STREAM_OUTPUT", False)

    def determine_emitter(self, request, *args, **kwargs):
        """
        Function for determining which emitter to use
        for output. It lives here so you can easily subclass
        `Resource` in order to change how emission is detected.

        You could also check for the `Accept` HTTP header here,
        since that pretty much makes sense. Refer to `Mimer` for
        that as well.
        """
        em = kwargs.pop("emitter_format", None)

        if not em:
            em = request.GET.get("format", "json")

        return em

    @property
    def anonymous(self):
        """
        Gets the anonymous handler. Also tries to grab a class
        if the `anonymous` value is a string, so that we can define
        anonymous handlers that aren't defined yet (like, when
        you're subclassing your basehandler into an anonymous one.)
        """
        if hasattr(self.handler, "anonymous"):
            anon = self.handler.anonymous

            if callable(anon):
                return anon

        return None

    def authenticate(self, request, rm):  # noqa: C901
        actor, anonymous, error = False, True, ""
        # workaround for django header sillyness
        if "HTTP_AUTHORIZATION" in request.META:
            request.META["AUTHORIZATION"] = request.META["HTTP_AUTHORIZATION"]
        # first we're going to try any authenticators that might match header hints. then, we'll try
        # any catch-all registered under None as a hint
        potential_authenticators = []
        try:
            auth_header = request.META["AUTHORIZATION"]
            for hint, authenticators in self.authentication.items():
                if hint is None:
                    # pass by these for now. we want the catch-alls to execute last
                    continue
                if auth_header.startswith(hint.header):
                    potential_authenticators.extend(authenticators)
                    continue
        except KeyError as ke:
            logger.info(
                "ev=dda loc=resource method=authenticate state=no_auth_header key_error=%s",
                ke,
            )
            pass

        try:
            # now append the catch-all authenticators
            potential_authenticators.extend(self.authentication[None])
        except KeyError:
            pass

        try:
            if len(potential_authenticators) <= 0:
                actor, anonymous = _no_authenticators_found, CHALLENGE
            else:
                for authenticator in potential_authenticators:
                    authentication_result = authenticator.is_authenticated(request)

                    if not authentication_result:
                        error = authentication_result
                        if self.anonymous and rm in self.anonymous.allowed_methods:
                            actor, anonymous = self.anonymous(), True
                        else:
                            actor, anonymous = authenticator.challenge, CHALLENGE
                    else:
                        return self.handler, False, error

            # XXX: this might be a little weird as it'll contain information about the last executed authenticator
            return actor, anonymous, error
        except Exception:
            logger.exception(
                "ev=dda_resource method=authenticate state=authentication_exception"
            )

    # TODO: make this method less complex and remove the `noqa`
    @vary_on_headers("Authorization")  # noqa: C901
    def __call__(self, request, *args, **kwargs):  # noqa: C901
        """
        NB: Sends a `Vary` header so we don't cache requests
        that are different (OAuth stuff in `Authorization` header.)
        """
        rm = request.method.upper()

        # Django's internal mechanism doesn't pick up
        # PUT request, so we trick it a little here.
        if rm == "PUT":
            coerce_put_post(request)

        actor, anonymous, error = self.authenticate(request, rm)

        if anonymous is CHALLENGE:
            return actor(error)
        else:
            handler = actor

        # Translate nested datastructs into `request.data` here.
        if rm in ("POST", "PUT"):
            try:
                translate_mime(request)
            except MimerDataException:
                return rc.BAD_REQUEST
            if not hasattr(request, "data"):
                if rm == "POST":
                    request.data = request.POST
                else:
                    request.data = request.PUT

        if rm not in handler.allowed_methods:
            return HttpResponseNotAllowed(handler.allowed_methods)

        meth = handler.method_handlers.get(rm, None)
        if not meth:
            raise Http404

        # Support emitter through (?P<emitter_format>) and ?format=emitter
        # and lastly Accept: header processing
        em_format = self.determine_emitter(request, *args, **kwargs)
        if not em_format:  # pragma: nocover
            # TODO: This should be fixed. The current implementation of determine_emitter defaults to json.
            # The only way to reach this block is to append ?format= in your URL. If the code reaches this block,
            # it will fail because neither self.strict_accept or self.default_emitter exist. It would be fixed by
            # implementing a child resource class, but that shouldn't be required.
            request_has_accept = "HTTP_ACCEPT" in request.META
            if request_has_accept and self.strict_accept:
                return rc.NOT_ACCEPTABLE
            em_format = self.default_emitter

        kwargs.pop("emitter_format", None)

        # Clean up the request object a bit, since we might
        # very well have `oauth_`-headers in there, and we
        # don't want to pass these along to the handler.
        request = _DESERIALIZERS[request.content_type](self.cleanup_request(request))

        try:
            # forces Django to parse the request data
            _ = request.POST if request.method == "POST" else request.GET
            status_code, result = meth(request, *args, **kwargs)
        except errors.ClientError as client_error:
            status_code = http.client.BAD_REQUEST
            result = self.error_handler(client_error, request, meth, em_format)
        except Exception as e:
            logger.exception(
                "ev=dda_resource method=__call__ state=exception_during_endpoint_processing"
            )
            status_code = http.client.BAD_REQUEST
            result = self.error_handler(e, request, meth, em_format)

        try:
            emitter, ct = Emitter.get(em_format)
        except ValueError:  # pragma: nocover
            logger.error(
                "ev=dda_resource method=__call__ state=bad_emitter emitter_format=%s",
                em_format,
            )
            result = rc.BAD_REQUEST
            result.content = "Invalid output format specified '%s'." % em_format
            return result

        # If we're looking at a response object which contains non-string
        # content, then assume we should use the emitter to format that
        # content
        if self._use_emitter(result):  # pragma: nocover
            status_code = result.status_code
            # Note: We can't use result.content here because that
            # method attempts to convert the content into a string
            # which we don't want.  when
            # _is_string/_base_content_is_iter is False _container is
            # the raw data
            result = result._container

        srl = emitter(result, handler, anonymous)

        try:
            # If the status code is 204, we need to return an empty response. skip the emitter.
            if status_code == http.HTTPStatus.NO_CONTENT:
                return HttpResponse(b"", status=http.HTTPStatus.NO_CONTENT)

            """
            Decide whether or not we want a generator here,
            or we just want to buffer up the entire result
            before sending it to the client. Won't matter for
            smaller datasets, but larger will have an impact.
            """
            if self.stream:
                stream = srl.stream_render(request)
            else:
                stream = srl.render(request)

            if not isinstance(stream, HttpResponse):
                resp = HttpResponse(stream, content_type=ct, status=status_code)
            else:
                resp = stream

            resp.streaming = self.stream

            return resp
        except HttpStatusCode as e:
            return e.response

    @staticmethod
    def _use_emitter(result):
        """
        True if result is a HttpResponse and contains non-string content,
        except for content-type 'image/png' or 'image/jpg'.
        """
        if not isinstance(result, HttpResponse):
            return False
        elif result.status_code in {304, 400, 401, 403, 404, 409, 429}:
            return False  # pragma: nocover
        elif not isinstance(result.content, bytes):
            return False  # pragma: nocover
        elif "image" in result.get("content-type"):
            return False
        elif "application/json" in result.get("content-type"):
            return False
        return True

    @staticmethod
    def cleanup_request(request):
        """
        Removes `oauth_` keys from various dicts on the
        request object, and returns the sanitized version.
        """
        for method_type in ("GET", "PUT", "POST", "DELETE"):
            block = getattr(request, method_type, {})

            if True in [k.startswith("oauth_") for k in block.keys()]:
                sanitized = block.copy()

                for k in list(sanitized.keys()):
                    if k.startswith("oauth_"):
                        sanitized.pop(k)

                setattr(request, method_type, sanitized)

        return request

    # --

    def email_exception(self, reporter):
        subject = "Django Declarative APIs crash report"
        html = reporter.get_traceback_html()

        message = EmailMessage(
            settings.EMAIL_SUBJECT_PREFIX + subject,
            html,
            settings.SERVER_EMAIL,
            [admin[1] for admin in settings.ADMINS],
        )

        message.content_subtype = "html"
        message.send(fail_silently=True)

    def error_handler(self, error, request, meth, em_format):
        if not isinstance(error, errors.ApiError):
            # handler returned a raw exception instead of a client error.  This is bad.
            # convert it to a clienterrors.ServerError so we can capture the stack trace in our logs.
            # The client will receive a unique key that allows us to locate the stack trace if necessary
            error = errors.ServerError()
            exc_type, exc_value, tb = sys.exc_info()
            rep = ExceptionReporter(request, exc_type, exc_value, tb.tb_next)
            self.email_exception(rep)
        elif isinstance(error, errors.ClientError):
            logger.info(
                'ev=dda, error_type=%s, status_code=%s, error="%s"',
                error.__class__.__name__,
                error.status_code,
                error.as_dict(),
            )

        emitter, ct = Emitter.get(em_format)
        content = emitter(error.as_dict(), None)
        return HttpResponseServerError(
            content.render(request),
            content_type=ct,
            status=error.status_code,
            error=error,
        )


def _no_authenticators_found(*args):
    error_code, error_message = errors.AUTHORIZATION_FAILURE

    response = HttpResponse()
    response.content = json.dumps(
        {"error_code": error_code, "error_message": error_message}
    )
    response.status_code = http.HTTPStatus.UNAUTHORIZED
    response["content-type"] = "application/json"

    return response
