from django.http import request
import http
import oauthlib

from django.test import TestCase
from django.http import QueryDict, HttpRequest
from oauthlib.oauth1 import SIGNATURE_TYPE_QUERY



class ResponseTestCase(TestCase):
    def test_ping_definition(self):
        resp = self.client.get(
            '/ping',
        )
        self.assertEqual(resp.json(), {'ping': 'pong'})
    

    def test_create_me(self):
        client = oauthlib.oauth1.Client('client_key', signature_type=SIGNATURE_TYPE_QUERY,)

        uri, headers, body = client.sign('http://localhost:8000/me?q=hello')
        parameters = QueryDict(uri)

        resp = self.client.post(
            '/me',
            {
                'oauth_consumer_key': parameters.get('oauth_consumer_key'),
                'oauth_token': parameters.get('oauth_token'),
                'oauth_signature_method': parameters.get('oauth_signature_method'),
                'oauth_timestamp': parameters.get('oauth_timestamp'),
                'oauth_nonce': parameters.get('oauth_nonce'),
                'oauth_signature': parameters.get('oauth_signature'),
            },
            content_type='application/json'
        )
        print("resp: ", resp.json())
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
