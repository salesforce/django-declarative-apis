import django.test

from django_declarative_apis.machinery import errors


class ErrorTestCast(django.test.TestCase):

    def test_apierror_tuple(self):
        test_code, test_message = test_tuple = errors.HTTPS_REQUIRED
        err = errors.ApiError(error_tuple=test_tuple)
        self.assertEqual(test_code, err.error_code)
        self.assertEqual(test_message, err.error_message)
        self.assertDictEqual(err.as_dict(), dict(error_code=test_code, error_message=test_message))

    def test_apierror_code_and_message(self):
        test_code, test_message = 600, "test message"
        err = errors.ApiError(code=test_code, message=test_message)
        self.assertEqual(test_code, err.error_code)
        self.assertEqual(test_message, err.error_message)
        self.assertDictEqual(dict(error_code=test_code, error_message=test_message), err.as_dict())

    def test_apierror_bad_args(self):
        try:
            errors.ApiError()
        except errors.ApiError:
            errmsg = "ApiError requires arguments"
            self.fail(errmsg)
        except Exception:  # this is the expected result
            pass
        else:
            self.fail("ApiError without arguments should raise an exception.")

    def test_apierror_extra_args(self):
        test_code, test_message = test_tuple = errors.AUTHORIZATION_FAILURE
        err = errors.ApiError(error_tuple=test_tuple, foo="bar", baz="quux")
        self.assertDictEqual(dict(error_code=test_code, error_message=test_message, foo="bar", baz="quux"),
                             err.as_dict())

    def test_additional_info(self):
        test_classes = [errors.ClientErrorUnprocessableEntity, errors.ClientErrorNotFound, errors.ClientErrorForbidden,
                        errors.ClientErrorUnauthorized, errors.ClientErrorExternalServiceFailure,
                        errors.ClientErrorTimedOut,
                        errors.ServerError]
        test_message = "Test additional info."
        for cls in test_classes:
            with self.subTest(cls):
                err = cls(additional_info=test_message)
                self.assertIn(test_message, err.error_message)