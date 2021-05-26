from django.http import request
import http
import oauthlib

from django.test import TestCase
from .testutils import  OAuthClient
from django_declarative_apis.models import OauthConsumer

class ResponseTestCase(TestCase):
    def test_ping_definition(self):
        resp = self.client.get(
            '/ping',
        )
        self.assertEqual(resp.json(), {'ping': 'pong'})
    

    def test_create_me(self):
        self.client = OAuthClient()
        consumer = OauthConsumer.objects.create(name='smith')

        resp = self.client.post(
            '/me',
            {},
            consumer=consumer,
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
