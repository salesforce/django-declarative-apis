from django.test import TestCase
import http


class ResponseTestCase(TestCase):
    def test_ping_definition(self):
        resp = self.client.get(
            '/ping',
        )
        self.assertEqual(resp.json(), {'ping': 'pong'})
    
    def test_create_me(self):
        resp = self.client.post(
            '/me',
            {   
                'name':'smith',
                'secret': 'this is a secret',
            },
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, http.HTTPStatus.OK)
