#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import json
import pickle
import unittest
from xml.dom import minidom

import django.http
import django.test
import yaml

import tests.models
from django_declarative_apis.resources import emitters


class EmitterTestCase(unittest.TestCase):
    def test_init_data_exception_error(self):
        class TestException(Exception):
            pass

        try:
            raise TestException("something bad happened")
        except TestException as err:
            try:
                emitters.Emitter(err, None)
            except Exception as reraised_err:
                # make sure the new exception is being re-raised from the initial one
                self.assertEqual(
                    reraised_err.__traceback__.tb_frame, err.__traceback__.tb_frame
                )

    def test_method_fields(self):
        class _Handler:
            def test(self):
                pass

            def __call__(self):
                pass

        handler = _Handler()
        em = emitters.Emitter(None, handler)
        fields = em.method_fields(handler, {"test"})
        self.assertEqual(fields["test"], handler.test)

        em = emitters.Emitter(None, None)
        self.assertEqual(em.method_fields(None, {"test"}), {})

    def test_render_raises_not_implemented_error(self):
        em = emitters.Emitter(None, None)
        self.assertRaises(NotImplementedError, em.render, None)

    def test_stream_render(self):
        data = ["foo", "bar"]

        class _StreamEmitter(emitters.Emitter):
            def __init__(self, _, __):
                self.idx = 0

            def render(self, request):
                try:
                    val = data[self.idx]
                except IndexError:
                    raise StopIteration

                self.idx += 1
                return val

        em = _StreamEmitter(None, None)
        for idx, val in enumerate(
            em.stream_render(django.test.RequestFactory().get("/"))
        ):
            self.assertEqual(val, data[idx])

    def test_register_unregister_emitters(self):
        class FooEmitter:
            pass

        emitters.Emitter.register("foo", FooEmitter())
        emitter, content_type = emitters.Emitter.get("foo")
        self.assertIsInstance(emitter, FooEmitter)
        self.assertEqual(content_type, "text/plain")
        emitters.Emitter.unregister("foo")
        self.assertRaises(ValueError, emitters.Emitter.get, "foo")


class XMLEmitterTestCase(unittest.TestCase):
    def test_render_success(self):
        em = emitters.XMLEmitter({"foo": "bar"}, lambda: None)
        resp = em.render(django.test.RequestFactory().get("/"))
        dom = minidom.parseString(resp)
        self.assertEqual(dom.getElementsByTagName("foo")[0].childNodes[0].data, "bar")

    def test_render_list(self):
        em = emitters.XMLEmitter(["foo", "bar"], lambda: None)
        resp = em.render(django.test.RequestFactory().get("/"))
        dom = minidom.parseString(resp)
        self.assertEqual(len(dom.getElementsByTagName("resource")), 2)


class JSONEmitterTestCase(unittest.TestCase):
    def test_decode(self):
        # one bytes object and one string to test internal decoding
        em = emitters.JSONEmitter([b"foo", "bar"], lambda: None)
        resp = em.render(django.test.RequestFactory().get("/"))
        self.assertEqual(json.loads(resp), ["foo", "bar"])


class DjangoEmitterTestCase(unittest.TestCase):
    def test_render_http_response_succes(self):
        class _Handler:
            def __call__(self):
                pass

        resp = django.http.HttpResponse(content=b"foo")
        em = emitters.DjangoEmitter(resp, _Handler())
        self.assertEqual(em.render(None), resp)

    def test_render_str_int_success(self):
        data = "string data"
        em = emitters.DjangoEmitter(data, lambda: None)
        self.assertEqual(em.render(None), data)

        data = 42
        em = emitters.DjangoEmitter(data, lambda: None)
        self.assertEqual(em.render(None), data)

    def test_render_serializable_success(self):
        tests.models.TestModel.objects.all().delete()
        tests.models.TestModel()

        em = emitters.DjangoEmitter(tests.models.TestModel.objects.all(), lambda: None)
        resp = em.render(None, format="json")
        self.assertEqual(json.loads(resp), [])

        obj = tests.models.TestModel(int_field=42)
        obj.save()

        em = emitters.DjangoEmitter(tests.models.TestModel.objects.all(), lambda: None)
        resp = em.render(None, format="json")
        self.assertEqual(
            json.loads(resp),
            [{"model": "tests.testmodel", "pk": obj.pk, "fields": {"int_field": 42}}],
        )


class YAMLEmitterTestCase(unittest.TestCase):
    def test_render(self):
        data = {"foo": "bar"}
        em = emitters.YAMLEmitter(data, lambda: None)
        self.assertEqual(yaml.safe_load(em.render(None)), data)


class PickleEmitterTestCase(unittest.TestCase):
    def test_render(self):
        data = {"foo": "bar"}
        em = emitters.PickleEmitter(data, lambda: None)
        self.assertEqual(pickle.loads(em.render(None)), data)
