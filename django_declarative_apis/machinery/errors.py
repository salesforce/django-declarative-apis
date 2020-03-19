#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import http
import uuid
import logging
import warnings

import http.client

# Start Toopher-specific codes at 600 to avoid conflict/confusion with HTTP status codes
import sys

logger = logging.getLogger(__name__)

HTTPS_REQUIRED = (600, "This request must use HTTPS")
FORBIDDEN = (601, "Not allowed")
EXTERNAL_REQUEST_FAILURE = (
    604,
    "Encountered exception while contacting an external service",
)
REQUEST_THROTTLED = (605, "Too many requests.  Please try again later.")
TIMED_OUT = (606, "Request timed out")
AUTHORIZATION_FAILURE = (607, "Authorization failure")

EXTRA_FIELDS = (700, "Extra field(s) in request")
READ_ONLY_FIELDS = (701, "Write attempted to read-only field(s)")
MISSING_FIELDS = (702, "Missing required field(s)")
INVALID_FIELD_VALUES = (703, "Invalid values for field(s)")

LOGGED_SERVER_ERROR = (500, "Server Error: Reference {0}")


DEPRECATED_ERROR_CODES = {}


class ApiError(Exception):
    def __init__(
        self,
        code=None,
        message=None,
        error_tuple=None,
        http_status_code=http.client.BAD_REQUEST,
        **kwargs,
    ):
        if error_tuple:
            self.error_code = error_tuple[0]
            self.error_message = error_tuple[1]
        else:
            if not (code and message):
                raise Exception(
                    "Must specify either clienterror tuple or BOTH code and message"
                )
            self.error_code = code
            self.error_message = message

        self.status_code = http_status_code
        self.extra_fields = kwargs

    def as_dict(self):
        result = {"error_code": self.error_code, "error_message": self.error_message}

        if self.extra_fields:
            result.update(self.extra_fields)

        return result

    @property
    def error_code(self):
        try:
            return self.__dict__["error_code"]
        except KeyError:
            raise AttributeError(
                "'{}' object has no attribute '{}'".format(
                    ApiError.__name__, "error_code"
                )
            )

    @error_code.setter
    def error_code(self, value):
        if value in DEPRECATED_ERROR_CODES:
            warnings.warn("deprecated error code", DeprecationWarning)
            raise ValueError("ApiError cannot use a deprecated error code")
        self.__dict__["error_code"] = value


class ClientError(ApiError):
    def __init__(self, *args, **kwargs):
        self.save_changes = kwargs.pop("save_changes", False)
        super().__init__(*args, **kwargs)


class ClientErrorUnprocessableEntity(ClientError):
    def __init__(self, additional_info=None):
        error_code, error_message = (
            http.HTTPStatus.UNPROCESSABLE_ENTITY,
            http.HTTPStatus.UNPROCESSABLE_ENTITY.phrase,
        )
        if additional_info:
            error_message = f"{error_message} : {additional_info}"

        super().__init__(error_code, error_message, http_status_code=error_code)


class ClientErrorNotFound(ClientError):
    def __init__(self, additional_info=None):
        error_code, error_message = (
            http.client.NOT_FOUND,
            http.client.responses.get(http.client.NOT_FOUND),
        )
        if additional_info:
            error_message += " : " + additional_info
        super().__init__(
            error_code, error_message, http_status_code=http.client.NOT_FOUND
        )


class ClientErrorForbidden(ClientError):
    def __init__(self, additional_info=None, **kwargs):
        error_code, error_message = FORBIDDEN
        if additional_info:
            error_message += ": %s" % additional_info
        super().__init__(
            error_code, error_message, http_status_code=http.client.FORBIDDEN, **kwargs
        )


class ClientErrorUnauthorized(ClientError):
    def __init__(self, additional_info=None, **kwargs):
        error_code, error_message = AUTHORIZATION_FAILURE
        if additional_info:
            error_message = f"{error_message} : {additional_info}"

        super().__init__(
            error_code,
            error_message,
            http_status_code=http.HTTPStatus.UNAUTHORIZED,
            **kwargs,
        )


class ClientErrorExternalServiceFailure(ClientError):
    def __init__(self, additional_info=None):
        error_code, error_message = EXTERNAL_REQUEST_FAILURE
        if additional_info:
            error_message += ": {0}".format(additional_info)
        super().__init__(error_code, error_message)


class ClientErrorRequestThrottled(ClientError):
    def __init__(self):
        error_code, error_message = REQUEST_THROTTLED
        super().__init__(error_code, error_message, http_status_code=429)


class ClientErrorTimedOut(ClientError):
    def __init__(self, additional_info=None):
        error_code, error_message = TIMED_OUT
        if additional_info:
            error_message += ": %s" % additional_info
        super().__init__(
            error_code, error_message, http_status_code=http.client.REQUEST_TIMEOUT
        )


class ClientErrorResponseWrapper(ClientError):
    def __init__(self, response):
        error_code = response.status_code
        error_message = response.content
        status_code = response.status_code
        super().__init__(error_code, error_message, http_status_code=status_code)


class ClientErrorExtraFields(ClientError):
    def __init__(self, extra_fields=None):
        error_code, error_message = EXTRA_FIELDS
        if extra_fields:
            error_message += ": %s" % ", ".join(extra_fields)
        super().__init__(error_code, error_message)


class ClientErrorReadOnlyFields(ClientError):
    def __init__(self, read_only_fields=None):
        error_code, error_message = READ_ONLY_FIELDS
        if read_only_fields:
            error_message += ": %s" % ", ".join(read_only_fields)
        super().__init__(error_code, error_message)


class ClientErrorMissingFields(ClientError):
    def __init__(self, missing_fields=None, extra_message=None):
        error_code, error_message = MISSING_FIELDS
        if missing_fields:
            error_message += ": %s" % ", ".join(missing_fields)
        if extra_message:
            error_message += ": {0}".format(extra_message)
        super().__init__(error_code, error_message)


class ClientErrorInvalidFieldValues(ClientError):
    def __init__(self, invalid_fields=None, extra_message=None):
        error_code, error_message = INVALID_FIELD_VALUES
        if invalid_fields:
            error_message += ": %s" % ", ".join(invalid_fields)
        if extra_message:
            error_message += ": {0}".format(extra_message)
        super().__init__(error_code, error_message)


class ServerError(ApiError):
    def __init__(self):
        error_code, error_message = LOGGED_SERVER_ERROR
        error_message = error_message.format(uuid.uuid4())
        logger.exception(error_message)

        self._cause = None

        super().__init__(
            error_code,
            error_message,
            http_status_code=http.client.INTERNAL_SERVER_ERROR,
        )

    @property
    def __cause__(self):
        return self._cause

    @__cause__.setter
    def __cause__(self, value):
        """Augment __cause__ setter to capture the relevant __traceback__ for the cause (inspired by Python 3)"""
        self._cause = value
        _, cause, traceback = sys.exc_info()
        if value is cause and not hasattr(cause, "__traceback__"):
            value.__traceback__ = traceback
