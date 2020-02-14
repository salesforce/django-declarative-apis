#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from django_declarative_apis.machinery.filtering import ALWAYS, expandable

from . import models

DEFAULT_FILTERS = {
    str: ALWAYS,
    int: ALWAYS,
    dict: ALWAYS,
    models.TestModel: {
        "pk": ALWAYS,
        "int_field": ALWAYS,
        "expandable_dict": expandable(),
        "expandable_string": expandable(),
    },
    models.ChildModel: {
        "pk": ALWAYS,
        "test": expandable(model_class=models.TestModel),
        "name": ALWAYS,
        "parent": expandable(model_class=models.ParentModel),
    },
    models.ParentModel: {
        "nonstandard_id": ALWAYS,
        "name": ALWAYS,
        "favorite": expandable(model_class=models.ChildModel, display_key="name"),
        "children": expandable(model_class=models.ChildModel, display_key="name"),
    },
    models.RootNode: {
        "pk": ALWAYS,
        "parent_field": expandable(model_class=models.ParentModel),
        "parents": expandable(model_class=models.ParentModel),
    },
}

DEFAULT_FILTERS_NO_EXPANDABLE = {
    str: ALWAYS,
    int: ALWAYS,
    dict: ALWAYS,
    models.TestModel: {
        "pk": ALWAYS,
        "int_field": ALWAYS,
        "expandable_dict": ALWAYS,
        "expandable_string": ALWAYS,
    },
}
