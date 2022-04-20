#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import abc
import typing


class AuthenticatorHint(typing.NamedTuple):
    """Tuple to provide hints for authentication implementations.

    header_hint: a string used to match the :code:`Authentication:` header.
    """

    header: str


class Authenticator(metaclass=abc.ABCMeta):
    """The base class for constructing an authenticator.

    The Authenticator class has two methods: :code:`is_authenticated` and
    :code:`challenge`. Both of these need to be overridden by the authenticator
    implementation that inherits from :code:`Authenticator` class. Otherwise,
    it will throw a :code:`NotImplementedError`.

    **Example**

    .. code-block::

        from django_declarative_apis.authentication import Authenticator

        class SampleAuthenticator(Authenticator):
            def is_authenticated(request):
                # authentication code

            def challenge(self, error):
                # challenge code
    """

    @abc.abstractmethod
    def is_authenticated(self, request):
        """Takes in the request as an argument and identifies whether the
        requester is valid.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def challenge(self, error):
        """Results in the challenge response sent to the user

        This should result in a django.http.HttpResponse that should include
        information through the WWW-Authenticate header around expectations.
        """
        raise NotImplementedError


class AuthenticationResult:
    """A class definition that takes in and stores the authentication header
    and details of the result.
    """

    def __init__(self, detail=None, auth_header=None):
        self.detail = detail
        self.auth_header = auth_header


class NoAuthentication(AuthenticationResult, Authenticator):
    """
    Authentication handler that always returns True, so no authentication is
    needed, nor initiated.

    .. note::
        **Important:** In this implementation the :code:`challenge` method is
        missing and must be implemented by the user. Otherwise, it will raise
        :code:`NotImplementedError`.
    """

    def is_authenticated(self, request):
        return True


class AuthenticationSuccess(AuthenticationResult):
    """An instance of :code:`AuthenticationResult` that returns :code:`True`.

    It can be used as a return response in an authenticator implementation.
    """

    def __bool__(self):
        return True


class AuthenticationFailure(AuthenticationResult):
    """An instance of :code:`AuthenticationResult` that returns :code:`False`.

    It can be used as a return response in an authenticator implementation.
    """

    def __bool__(self):
        return False


def validate_authentication_config(config):
    """Validate the computed configuration of authentication handlers

    The schema for the config is:

    {
        <AuthenticatorHint>: [<Authenticator>, <Authenticator>...],
        <AuthenticatorHint>: [<Authenticator>, <Authenticator>...],
    }

    AuthenticatorHints allow us to match Authorization headers for quick
    handler lookup. For example, if we want to use OAuth 1.0a, we could use an
    AuthenticatorHint.header value of 'OAuth ' as a key and a value of
    [django_declarative_apis.authentication.oauthilib.oauth1.TwoLeggedOauth1()].
    This will ensure that any time an `Authorization: OAuth ...` header is
    seen, the appropriate authenticator is used.

    If there are more complexities to the authenticator (i.e. OAuth 1.0a allows
    for the transport of credentials through header, request body or query
    parameters, catch-alls are allowed by using a key of `None`:

    {
        None: [<Authenticator>],
    }

    The catch-all authenticators are always executed after matched
    authenticators.

    Note: This may need to get smarter in the future but was kept simple
          intentionally as it's executed on every request.
    """
    assert isinstance(config, typing.Mapping)
    for hint, authenticators in config.items():
        if not isinstance(hint, (AuthenticatorHint, type(None))):
            raise TypeError(
                "Authenticator hint must be an instance of authentication.AuthenticatorHint or None"
            )

        assert isinstance(authenticators, (list, tuple))
        for authenticator in authenticators:
            if not isinstance(authenticator, Authenticator):
                raise TypeError(
                    "Authenticator must be an instance of authentication.Authenticator"
                )
