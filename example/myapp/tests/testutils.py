import oauthlib
import oauthlib.common
import oauthlib.oauth1
import time

from django.test.client import ClientHandler
from django.http import QueryDict
from django import test
from django_declarative_apis.models import OauthConsumer


class OAuthClientHandler(ClientHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_response(self, request):
        consumer = OauthConsumer.objects.get(name="smith")

        # Make request params mutable so we can add authorization parameters.
        # We make the params immutable again before processing the request
        request.POST = request.POST.copy()
        request.GET = request.GET.copy()

        if consumer:
            if request.method == "POST":
                data = request.POST
            else:
                data = request.GET

            # This provides a way for us to override default values for testing.
            oauth_version = request.META.get("oauth_version", "1.0")
            oauth_nonce = request.META.get(
                "oauth_nonce", oauthlib.common.generate_nonce()
            )
            oauth_client_timestamp = request.META.get(
                "oauth_timestamp", int(time.time())
            )

            oauth_signature_method = oauthlib.oauth1.SIGNATURE_HMAC

            oauth_signature_data = {
                "oauth_version": oauth_version,
                "oauth_nonce": oauth_nonce,
                "oauth_timestamp": str(oauth_client_timestamp),
                "oauth_consumer_key": consumer.key,
                "oauth_signature_method": oauth_signature_method,
            }

            # collect ALL request parameters (original + OAuth) for signing
            all_request_parameters = data.copy()
            all_request_parameters.update(oauth_signature_data)

            # use HMAC-SHA1 signature method
            oauth_signature_data.update({"oauth_signature_method": "HMAC-SHA1"})

            oauth1_client = oauthlib.oauth1.Client(
                consumer.key,
                client_secret=consumer.secret,
                signature_method=oauthlib.oauth1.SIGNATURE_HMAC,
            )

            oauth_request = oauthlib.common.Request(
                request.build_absolute_uri(request.path),
                http_method=request.method,
                body=all_request_parameters,
            )

            oauth_signature_data["oauth_signature"] = oauth1_client.get_oauth_signature(
                oauth_request
            )

            use_auth_header_signature = request.META.pop(
                "use_auth_header_signature", False
            )
            if use_auth_header_signature:
                auth_header_string = "OAuth " + ",".join(
                    [
                        '{0}="{1}"'.format(key, value)
                        for key, value in oauth_signature_data.items()
                    ]
                )
                request.META["HTTP_AUTHORIZATION"] = auth_header_string
            else:
                data.update(oauth_signature_data)

        # Recreate the GET and POST QueryDicts to make them immutable, as in production
        request.POST = QueryDict(request.POST.urlencode().encode("utf-8"))
        request.GET = QueryDict(request.GET.urlencode().encode("utf-8"))

        return ClientHandler.get_response(self, request)


class OAuthClient(test.Client):
    def __init__(self, *args, **kwargs):
        test.Client.__init__(self, *args, **kwargs)
        self.handler = OAuthClientHandler()

    def request(self, **kwargs):
        response = super().request(**kwargs)

        return response

    def post(self, path, data=None, **kwargs):
        if "content_type" not in kwargs:
            data = data or {}
            kwargs["content_type"] = "application/x-www-form-urlencoded"
            data_qd = QueryDict(mutable=True)
            data_qd.update(data)
            data = data_qd.urlencode()

        return super().post(path, data, **kwargs)
