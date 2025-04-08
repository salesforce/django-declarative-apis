import unittest
from django.test import RequestFactory
from django.http import QueryDict
from django_declarative_apis import machinery
from django_declarative_apis.machinery import errors


class TestRequestField(unittest.TestCase):
    def setUp(self):
        self.request_factory = RequestFactory()

    def test_get_without_default_none_request(self):
        field = machinery.field(type=str)
        actual = field.get_without_default(None, None)
        self.assertIsNone(actual)

    def test_get_without_default_empty_query_dict(self):
        request = self.request_factory.get("/")
        request.GET = QueryDict()
        field = machinery.field(type=str)
        actual = field.get_without_default(None, request)
        self.assertIsNone(actual)

    def test_get_without_default_get_request(self):
        field = machinery.field(type=str, name="test_field")
        expected = "test_value"
        request = self.request_factory.get(f"/?test_field={expected}")
        actual = field.get_without_default(None, request)
        self.assertEqual(actual, expected)

    def test_get_without_default_post_request(self):
        spaghetti_code_field = machinery.field(type=str, name="spaghetti_code_field")
        spaghetti_code_value = "italiano"
        request = self.request_factory.post(
            "/",
            {"test_field": "test_value", "spaghetti_code_field": spaghetti_code_value},
        )
        actual = spaghetti_code_field.get_without_default(None, request)
        self.assertEqual(actual, spaghetti_code_value)

    def test_get_without_default_multivalued(self):
        name = "vibe"
        field = machinery.field(type=str, multivalued=True, name=name)
        v1 = "cool"
        v2 = "good"
        request = self.request_factory.get(f"/?{name}={v1}&{name}={v2}")
        actual = field.get_without_default(None, request)
        self.assertEqual(actual, [v1, v2])

    def test_get_without_default_different_types(self):
        int_field = machinery.field(type=int, name="age")
        expected = 5
        request = self.request_factory.get(f"/?age={expected}")
        actual = int_field.get_without_default(None, request)
        self.assertEqual(actual, expected)

        # boolean type
        bool_field = machinery.field(type=bool, name="is_cool")
        request = self.request_factory.get("/?is_cool=true")
        actual = bool_field.get_without_default(None, request)
        self.assertTrue(actual)

        # float type
        float_field = machinery.field(type=float, name="pi")
        short_pi = 3.14
        request = self.request_factory.get(f"/?pi={short_pi}")
        actual = float_field.get_without_default(None, request)
        self.assertEqual(actual, short_pi)

    def test_get_without_default_invalid_type(self):
        name = "chad"
        antagonistical_value = "chad_is_not_an_int"
        int_field = machinery.field(type=int, name=name)
        request = self.request_factory.get(f"/?{name}={antagonistical_value}")

        with self.assertRaises(errors.ClientErrorInvalidFieldValues) as cm:
            int_field.get_without_default(None, request)

        self.assertIn(
            f"Could not parse {antagonistical_value} as type int", str(cm.exception)
        )

    def test_get_without_default_with_post_processor(self):
        def post_processor(owner_instance, value):
            return f"spicy_{value}"

        field = machinery.field(type=str, name="bird")
        field_value = "duck"
        expected = post_processor(None, field_value)
        field.post_processor = post_processor

        request = self.request_factory.get(f"/?bird={field_value}")
        actual = field.get_without_default(None, request)
        self.assertEqual(actual, expected)

    def test_get_without_default_field_not_present(self):
        field = machinery.field(type=str, name="nemo")
        request = self.request_factory.get("/?dory=keeps_on_swimming")
        actual = field.get_without_default(None, request)
        self.assertIsNone(actual)
