import django.test

from django_declarative_apis.machinery import errors

class ApiErrorTestCase(django.test.TestCase):

    def test_tuple(self):
        test_code, test_message = test_tuple = errors.HTTPS_REQUIRED
        err = errors.ApiError(error_tuple=test_tuple)
        self.assertEqual(err.error_code, test_code)
        self.assertEqual(err.error_message, test_message)
        self.assertDictEqual(err.as_dict(), dict(error_code=test_code, error_message=test_message))

    def test_code_and_message(self):
        test_code, test_message = 600, "test message"
        err = errors.ApiError(code=test_code, message=test_message)
        self.assertEqual(err.error_code, test_code)
        self.assertEqual(err.error_message, test_message)
        self.assertDictEqual(err.as_dict(), dict(error_code=test_code, error_message=test_message))

    def test_bad_args(self):
        try:
            errors.ApiError()
        except errors.ApiError:
            errmsg = "ApiError requires arguments"
            self.fail(errmsg)
        except Exception:  # this is the expected result
            pass
        else:
            self.fail("ApiError without arguments should raise an exception.")

    def test_extra_args(self):
        test_code, test_message = test_tuple = errors.AUTHORIZATION_FAILURE
        err = errors.ApiError(error_tuple=test_tuple, foo="bar", baz="quux")
        self.assertDictEqual(err.as_dict(),
                             dict(error_code=test_code, error_message=test_message, foo="bar", baz="quux"))