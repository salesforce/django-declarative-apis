import django.test
from django import http

from django_declarative_apis.machinery import errors


class ErrorTestCase(django.test.TestCase):
    def test_apierror_tuple(self):
        test_code, test_message = test_tuple = errors.HTTPS_REQUIRED
        err = errors.ApiError(error_tuple=test_tuple)
        self.assertEqual(test_code, err.error_code)
        self.assertEqual(test_message, err.error_message)
        self.assertDictEqual(
            err.as_dict(), dict(error_code=test_code, error_message=test_message)
        )

    def test_apierror_code_and_message(self):
        test_code, test_message = 600, "test message"
        err = errors.ApiError(code=test_code, message=test_message)
        self.assertEqual(test_code, err.error_code)
        self.assertEqual(test_message, err.error_message)
        self.assertDictEqual(
            dict(error_code=test_code, error_message=test_message), err.as_dict()
        )

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
        self.assertDictEqual(
            dict(
                error_code=test_code, error_message=test_message, foo="bar", baz="quux"
            ),
            err.as_dict(),
        )

    def test_apierror_deprecated_error_code(self):
        test_err = (999, "This is a fake error code.")
        try:
            errors.DEPRECATED_ERROR_CODES[test_err[0]] = test_err[1]
            with self.assertRaises(ValueError):
                with self.assertWarns(DeprecationWarning):
                    errors.ApiError(error_tuple=test_err)
        finally:
            del errors.DEPRECATED_ERROR_CODES[test_err[0]]

    def test_apierror_error_code_attributeerror(self):
        test_error_tuple = (999, "This is a fake error code.")
        err = errors.ApiError(error_tuple=test_error_tuple)
        del err.__dict__["error_code"]
        with self.assertRaises(AttributeError):
            err.error_code

    def test_additional_info_in_error(self):
        test_classes = [
            errors.ClientErrorUnprocessableEntity,
            errors.ClientErrorNotFound,
            errors.ClientErrorForbidden,
            errors.ClientErrorUnauthorized,
            errors.ClientErrorExternalServiceFailure,
            errors.ClientErrorTimedOut,
        ]
        test_message = "Test additional info."
        for cls in test_classes:
            with self.subTest(cls):
                err = cls(additional_info=test_message)
                self.assertIn(test_message, err.error_message)

    def test_servererror(self):
        test_additional_info = "Test additional info."
        with self.assertLogs(logger="django_declarative_apis.machinery.errors") as logs:
            err = errors.ServerError(additional_info=test_additional_info)
        self.assertIn("Server Error", err.error_message)
        self.assertNotIn(test_additional_info, err.error_message)
        self.assertIn("Server Error", logs.output[0])
        self.assertIn(test_additional_info, logs.output[0])

    def test_clienterrorresponsewrapper(self):
        message = "It's gone!"
        response = http.HttpResponseGone(message)
        err = errors.ClientErrorResponseWrapper(response)
        self.assertEqual(response.status_code, err.error_code)
        self.assertEqual(message, err.error_message)

    def test_clienterrorextrafields(self):
        err = errors.ClientErrorExtraFields(extra_fields=["foo", "bar", "baz"])
        self.assertIn("foo", err.error_message)
        self.assertIn("bar", err.error_message)
        self.assertIn("baz", err.error_message)

    def test_clienterrorreadonlyfields(self):
        err = errors.ClientErrorReadOnlyFields(read_only_fields=["foo", "bar", "baz"])
        self.assertIn("foo", err.error_message)
        self.assertIn("bar", err.error_message)
        self.assertIn("baz", err.error_message)

    def test_clienterrormissingfields(self):
        extra_message = "Test extra message."
        err = errors.ClientErrorMissingFields(
            missing_fields=["foo", "bar", "baz"], extra_message=extra_message
        )
        self.assertIn("foo", err.error_message)
        self.assertIn("bar", err.error_message)
        self.assertIn("baz", err.error_message)
        self.assertIn(extra_message, err.error_message)
