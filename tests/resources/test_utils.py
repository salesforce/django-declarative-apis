#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import http
import json
import unittest

import django.test
import mock
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from django_declarative_apis.resources import utils


class UtilsTestCase(unittest.TestCase):
    def test_format_error(self):
        val = utils.format_error(Exception("something bad happened"))
        self.assertIn("something bad happened", val)

    def test_rc_factory_invalid_code(self):
        try:
            utils.rc.INVALID
            self.fail("should have failed")
        except AttributeError:
            pass

    def test_rc_factory_iterable_content(self):
        data = [b"foo", b"bar"]
        resp = utils.rc.NOT_FOUND
        resp.content = data
        self.assertEqual(resp.content, b"".join(data))

    def test_form_validation_error(self):
        err = utils.FormValidationError("not a form")
        self.assertEqual(err.form, "not a form")

    def test_require_mime(self):
        @utils.require_mime("application/json")
        def test_json(self, req):
            return {}

        self.assertEqual(
            test_json(
                self,
                django.test.RequestFactory().post(
                    "/", {"foo": "bar"}, content_type="application/json"
                ),
            ),
            {},
        )

        self.assertEqual(
            test_json(
                self,
                django.test.RequestFactory().post("/", "", content_type="text/plain"),
            ).status_code,
            http.HTTPStatus.BAD_REQUEST,
        )


class MimerTestCase(unittest.TestCase):
    def test_is_multipart(self):
        req = django.test.RequestFactory().get("/", content_type="text/plain")
        self.assertFalse(utils.Mimer(req).is_multipart())

        req = django.test.RequestFactory().post("/", content_type="multipart/form-data")
        self.assertTrue(utils.Mimer(req).is_multipart())

    def test_loader_for_type(self):
        req = django.test.RequestFactory().post(
            "/", json.dumps({"foo": "bar"}), content_type="application/json"
        )
        mimer = utils.Mimer(req)
        self.assertEqual(mimer.loader_for_type("application/json"), json.loads)

    def test_translate(self):
        data = {"foo": "bar"}
        req = django.test.RequestFactory().post(
            "/", json.dumps(data), content_type="application/json"
        )
        mimer = utils.Mimer(req)
        req = mimer.translate()
        self.assertEqual(req.POST, {})
        self.assertEqual(req.PUT, {})
        self.assertEqual(req.data, data)

    def test_translate_none_deserializer(self):
        with mock.patch.dict(
            "django_declarative_apis.resources.utils.Mimer.TYPES",
            {None: "application_json"},
            clear=True,
        ):
            req = django.test.RequestFactory().post(
                "/", {"foo": "bar"}, content_type="application/json"
            )
            mimer = utils.Mimer(req)
            self.assertIsNone(mimer.translate().data)

    def test_translate_invalid_data(self):
        req = django.test.RequestFactory().post(
            "/", "notjson", content_type="application/json"
        )
        mimer = utils.Mimer(req)
        self.assertRaises(utils.MimerDataException, mimer.translate)

    def test_register_unregister(self):
        deserializer, content_type = lambda _: None, "foo"
        utils.Mimer.register(deserializer, content_type)

        req = django.test.RequestFactory().post("/", "", content_type=content_type)
        mimer = utils.Mimer(req)
        self.assertEqual(mimer.loader_for_type(content_type), deserializer)

        utils.Mimer.unregister(deserializer)
        self.assertIsNone(mimer.loader_for_type(content_type))


class KeyProcessingTestCase(unittest.TestCase):

    # We can't compute these keys from the cryptography library because they're
    # nonstandard. These were both taken from their respective devices.

    KEYS = {
        "ANDROID_PUBLIC": (
            "-----BEGIN RSA PUBLIC KEY-----\n"
            "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC0YjCwIfYoprq/FQO6lb3asXrx\n"
            "LlJFuCvtinTF5p0GxvQGu5O3gYytUvtC2JlYzypSRjVxwxrsuRcP3e641SdASwfr\n"
            "mzyvIgP08N4S0IFzEURkV1wp/IpH7kH41EtbmUmrXSwfNZsnQRE5SYSOhh+LcK2w\n"
            "yQkdgcMv11l4KoBkcwIDAQAB\n"
            "-----END RSA PUBLIC KEY-----"
        ),
        "IOS_PUBLIC": (
            "-----BEGIN CERTIFICATE-----\n"
            "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArZvjX99s6wyS3IKdmPYOEZ"
            "m0CeFIyWwl/S1D7PyOfJkd3bHFzMrRLbgB7gXubZWxiORQJKAW4gfDpBXq0kes8LEhV"
            "gVdMdmvuCyGqchC5ON8hMXrrycQa8ejr0eq81y+bc1cYCE8mtVQqXdgrTYQAN0ObIkJ"
            "ajzfiQ9KOCoszopZoNoDP9qPYTtlURQvR5VwWeAGmL9ZkqdQqBr2tMlV673kdXo1HuB"
            "97K9mcYLBN8a5mQ/YgdzjPf0+JjpSH/Fx9ElCVJP8zZbBW2/06SMs3xDLCTHmdRcs/o"
            "WLhoyYRMvagq/j0MBNP2fU9dtlqPLFl6ZjJl/M4JdeZJWURkI9ZQIDAQAB\n"
            "-----END CERTIFICATE-----"
        ),
    }

    def test_nonstandard_public_key(self):
        for key_name in ["IOS_PUBLIC", "ANDROID_PUBLIC"]:
            with self.subTest(key_name=key_name):
                processed = utils.preprocess_rsa_key(self.KEYS[key_name])
                self.assertTrue(processed.startswith("-----BEGIN PUBLIC KEY-----"))
                self.assertTrue(processed.endswith("-----END PUBLIC KEY-----"))

    def test_standard_public_key(self):
        # example from `cryptography` documentation
        private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )
        public_key = private_key.public_key()
        public_key_str = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf8")
        self.assertEqual(public_key_str, utils.preprocess_rsa_key(public_key_str))
