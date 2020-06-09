#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import django.test
import mock

from django_declarative_apis.machinery import filtering

from . import filters
from . import models


class FiltersTestCase(django.test.TestCase):
    def setUp(self):
        self.test_model = models.TestModel.objects.create(id=1, int_field=1)
        self.p1 = models.ParentModel.objects.create(nonstandard_id=2, name="p1")
        self.p1c1 = models.ChildModel.objects.create(
            id=3, test=self.test_model, name="p1c1", parent=self.p1
        )
        self.p1c2 = models.ChildModel.objects.create(
            id=4, test=self.test_model, name="p1c2", parent=self.p1
        )
        self.p1.favorite = self.p1c1
        self.p1.save()

        self.root = models.RootNode.objects.create(id=5, parent_field=self.p1)
        self.p1.root = self.root
        self.p1.save()

    def test_expandable_field_not_expanded_by_default(self):
        filtered = filtering.apply_filters_to_object(self.root, filters.DEFAULT_FILTERS)
        self.assertEqual(4, len(filtered))
        self.assertTrue("parent_field" in filtered)
        self.assertEqual(1, len(filtered["parent_field"]))
        self.assertEqual(
            self.p1.nonstandard_id, filtered["parent_field"]["nonstandard_id"]
        )

    def test_expand_single_level(self):
        filtered = filtering.apply_filters_to_object(
            self.root, filters.DEFAULT_FILTERS, expand_header="parent_field"
        )
        self.assertEqual(4, len(filtered))
        self.assertTrue("parent_field" in filtered)
        self.assertEqual(5, len(filtered["parent_field"]))
        self.assertEqual(
            self.p1.nonstandard_id, filtered["parent_field"]["nonstandard_id"]
        )
        self.assertEqual(self.p1.name, filtered["parent_field"]["name"])
        self.assertEqual(self.p1c1.name, filtered["parent_field"]["favorite"]["name"])
        self.assertEqual(2, len(filtered["parent_field"]["children"]))
        for child in filtered["parent_field"]["children"]:
            self.assertEqual(1, len(child))
            self.assertTrue("name" in child)

    def test_expand_multi_level(self):
        filtered = filtering.apply_filters_to_object(
            self.root, filters.DEFAULT_FILTERS, expand_header="parent_field.favorite"
        )
        self.assertEqual(4, len(filtered))
        self.assertTrue("parent_field" in filtered)
        self.assertEqual(5, len(filtered["parent_field"]))
        self.assertEqual(
            self.p1.nonstandard_id, filtered["parent_field"]["nonstandard_id"]
        )
        self.assertEqual(self.p1.name, filtered["parent_field"]["name"])
        self.assertEqual(5, len(filtered["parent_field"]["favorite"]))
        self.assertEqual(self.p1c1.name, filtered["parent_field"]["favorite"]["name"])
        self.assertEqual(2, len(filtered["parent_field"]["children"]))
        for child in filtered["parent_field"]["children"]:
            self.assertEqual(1, len(child))
            self.assertTrue("name" in child)

    def test_expand_multi_level_reverse_fk_relation(self):
        filtered = filtering.apply_filters_to_object(
            self.root, filters.DEFAULT_FILTERS, expand_header="parent_field.children"
        )
        self.assertEqual(4, len(filtered))
        self.assertTrue("parent_field" in filtered)
        self.assertEqual(5, len(filtered["parent_field"]))
        self.assertEqual(
            self.p1.nonstandard_id, filtered["parent_field"]["nonstandard_id"]
        )
        self.assertEqual(self.p1.name, filtered["parent_field"]["name"])
        self.assertEqual(1, len(filtered["parent_field"]["favorite"]))
        self.assertTrue("name" in filtered["parent_field"]["favorite"])
        self.assertEqual(self.p1c1.name, filtered["parent_field"]["favorite"]["name"])
        self.assertEqual(2, len(filtered["parent_field"]["children"]))
        for child in filtered["parent_field"]["children"]:
            self.assertEqual(5, len(child))
            self.assertTrue("pk" in child)
            self.assertTrue("name" in child)
            self.assertTrue("test" in child)
            self.assertTrue("parent" in child)
            self.assertEqual(1, len(child["parent"]))

    def test_expand_multi_level_more_than_one_field(self):
        filtered = filtering.apply_filters_to_object(
            self.root,
            filters.DEFAULT_FILTERS,
            expand_header="parent_field,parent_field.children, parent_field.favorite.test",
        )
        self.assertEqual(4, len(filtered))
        self.assertTrue("parent_field" in filtered)
        self.assertEqual(5, len(filtered["parent_field"]))
        self.assertEqual(
            self.p1.nonstandard_id, filtered["parent_field"]["nonstandard_id"]
        )
        self.assertEqual(self.p1.name, filtered["parent_field"]["name"])
        self.assertEqual(5, len(filtered["parent_field"]["favorite"]))
        self.assertTrue("pk" in filtered["parent_field"]["favorite"])
        self.assertTrue("name" in filtered["parent_field"]["favorite"])
        self.assertTrue("test" in filtered["parent_field"]["favorite"])
        self.assertEqual(3, len(filtered["parent_field"]["favorite"]["test"]))
        self.assertTrue("parent" in filtered["parent_field"]["favorite"])
        self.assertEqual(self.p1c1.name, filtered["parent_field"]["favorite"]["name"])
        self.assertEqual(2, len(filtered["parent_field"]["children"]))
        for child in filtered["parent_field"]["children"]:
            self.assertEqual(5, len(child))
            self.assertTrue("pk" in child)
            self.assertTrue("name" in child)
            self.assertTrue("test" in child)
            self.assertEqual(1, len(child["test"]))
            self.assertTrue("parent" in child)
            self.assertEqual(1, len(child["parent"]))

    def test_expandable_properties(self):
        filtered = filtering.apply_filters_to_object(
            self.test_model,
            filters.DEFAULT_FILTERS,
            expand_header="expandable_dict,expandable_string",
        )

        self.assertEqual(5, len(filtered))
        self.assertTrue("expandable_dict" in filtered)
        self.assertEqual(
            filtered["expandable_dict"], models.TestModel.EXPANDABLE_DICT_RETURN
        )
        self.assertTrue("expandable_string" in filtered)
        self.assertEqual(
            filtered["expandable_string"], models.TestModel.EXPANDABLE_STRING_RETURN
        )
        self.assertTrue("__expandable__" in filtered)
        self.assertTrue("expandable_dict" in filtered["__expandable__"])
        self.assertTrue("expandable_string" in filtered["__expandable__"])

        with mock.patch(
            "tests.models.TestModel.expandable_dict"
        ) as dict_mock, mock.patch(
            "tests.models.TestModel.expandable_string"
        ) as str_mock:
            filtered = filtering.apply_filters_to_object(
                self.test_model, filters.DEFAULT_FILTERS
            )

            self.assertEqual(3, len(filtered))
            self.assertFalse("expandable_dict" in filtered)
            dict_mock.assert_not_called()
            self.assertFalse("expandable_string" in filtered)
            str_mock.assert_not_called()
            self.assertTrue("__expandable__" in filtered)
            self.assertTrue("expandable_dict" in filtered["__expandable__"])
            self.assertTrue("expandable_string" in filtered["__expandable__"])

    def test_expandable_absent_if_no_expandable_fields(self):
        filtered = filtering.apply_filters_to_object(
            self.test_model, filters.DEFAULT_FILTERS_NO_EXPANDABLE
        )

        self.assertEqual(4, len(filtered))
        self.assertTrue("expandable_dict" in filtered)
        self.assertEqual(
            filtered["expandable_dict"], models.TestModel.EXPANDABLE_DICT_RETURN
        )
        self.assertTrue("expandable_string" in filtered)
        self.assertEqual(
            filtered["expandable_string"], models.TestModel.EXPANDABLE_STRING_RETURN
        )

    def test_rename_expandable_foreign_key(self):
        filtered = filtering.apply_filters_to_object(
            self.p1c1, filters.RENAMED_EXPANDABLE_MODEL_FIELDS
        )

        self.assertEqual(filtered["renamed_test"], {"id": self.p1c1.test.pk})
        self.assertEqual(
            filtered["renamed_parent"], {"nonstandard_id": self.p1c1.parent.pk}
        )

        filtered = filtering.apply_filters_to_object(
            self.p1c1,
            filters.RENAMED_EXPANDABLE_MODEL_FIELDS,
            expand_header="renamed_test,renamed_parent",
        )
        self.assertTrue(2, len(filtered["renamed_test"]))
        self.assertIn("int_field", filtered["renamed_test"])
        self.assertNotIn("renamed_expandable_dict", filtered["renamed_test"])
        self.assertTrue(4, len(filtered["renamed_parent"]))

        filtered = filtering.apply_filters_to_object(
            self.p1c1,
            filters.RENAMED_EXPANDABLE_MODEL_FIELDS,
            expand_header="renamed_test,renamed_test.renamed_expandable_dict",
        )
        self.assertTrue(3, len(filtered["renamed_test"]))
        self.assertIn("renamed_expandable_dict", filtered["renamed_test"])
        self.assertEqual(
            self.test_model.expandable_dict,
            filtered["renamed_test"]["renamed_expandable_dict"],
        )
        self.assertNotIn("renamed_expandable_string", filtered["renamed_test"])

        filtered = filtering.apply_filters_to_object(
            self.p1c1,
            filters.RENAMED_EXPANDABLE_MODEL_FIELDS,
            expand_header="renamed_test,renamed_test.renamed_expandable_dict,renamed_test.renamed_expandable_string",
        )
        self.assertTrue(4, len(filtered["renamed_test"]))
        self.assertIn("renamed_expandable_dict", filtered["renamed_test"])
        self.assertIn("renamed_expandable_string", filtered["renamed_test"])
