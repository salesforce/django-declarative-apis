#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from django.db import models


class TestModel(models.Model):
    int_field = models.IntegerField()

    EXPANDABLE_DICT_RETURN = {"key": "value"}
    EXPANDABLE_STRING_RETURN = "string"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mutate_action(self):
        self.int_field += 1
        self.save()

    @property
    def expandable_dict(self):
        return TestModel.EXPANDABLE_DICT_RETURN

    @property
    def expandable_string(self):
        return TestModel.EXPANDABLE_STRING_RETURN


class ChildModel(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    test = models.ForeignKey(TestModel, on_delete=models.CASCADE)
    parent = models.ForeignKey(
        "ParentModel", related_name="children", on_delete=models.CASCADE
    )


class ParentModel(models.Model):
    nonstandard_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100)
    favorite = models.ForeignKey(ChildModel, null=True, on_delete=models.CASCADE)
    root = models.ForeignKey(
        "RootNode", related_name="parents", null=True, on_delete=models.CASCADE
    )


class RootNode(models.Model):
    id = models.IntegerField(primary_key=True)
    parent_field = models.ForeignKey(ParentModel, on_delete=models.CASCADE)
