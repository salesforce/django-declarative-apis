#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from collections import defaultdict
import inspect
import types

from django.db import models
from django.db.models import ManyToOneRel

NEVER = 0
ALWAYS = 1
IF_TRUTHY = 2

DEFAULT_UNEXPANDED_VALUE = object()
EXPANDABLE_FIELD_KEY = "__expandable__"


class _ExpandableForeignKey:
    def __init__(self, display_key, model_class, inst_field_name):
        self.display_key = display_key
        self.model_class = model_class
        self.inst_field_name = inst_field_name


def expandable(model_class=None, display_key=None, inst_field_name=None):
    if model_class and not issubclass(model_class, (models.Model,)):
        raise ValueError("model_class must be an instance of a Django Model")
    if model_class and display_key:
        try:
            model_class._meta.get_field(display_key)
        except models.FieldDoesNotExist as e:  # noqa
            raise ValueError(f"{display_key} is not a field on {model_class.__name__}")
    return _ExpandableForeignKey(display_key, model_class, inst_field_name)


def _get_unexpanded_field_value(inst, field_name, field_type):
    if not field_type.model_class:
        return DEFAULT_UNEXPANDED_VALUE

    display_key = field_type.display_key or field_type.model_class._meta.pk.name
    inst_field_name = field_type.inst_field_name or field_name
    is_multiple = isinstance(
        inst.__class__._meta.get_field(inst_field_name), ManyToOneRel
    )

    if is_multiple:
        # special case for keys that have multiple values (for instance, inverse fk relations)
        obj = getattr(inst, inst_field_name)
        return [{display_key: getattr(v, display_key)} for v in obj.all()]

    if display_key == field_type.model_class._meta.pk.name:
        # special case - we know this is a primary key, so we can get it without retrieving the object
        return {display_key: getattr(inst, inst_field_name + "_id")}
    else:
        # we're not returning the PK - have to actually retrieve the model
        obj = getattr(inst, inst_field_name)
        return {display_key: getattr(obj, display_key)}


def _get_filtered_field_value(
    inst, field_name, field_type, filter_def, expand_this, expand_children
):
    # get the value from inst
    if field_type == NEVER:
        return None

    if isinstance(field_type, types.FunctionType):
        val = field_type(inst)
    elif isinstance(field_type, _ExpandableForeignKey):
        if expand_this:
            inst_field_name = field_type.inst_field_name or field_name
            val = getattr(inst, inst_field_name)
        else:
            val = _get_unexpanded_field_value(inst, field_name, field_type)
    else:
        try:
            val = getattr(inst, field_name)
        except (AttributeError, models.fields.FieldDoesNotExist) as e:  # noqa
            return None

    if isinstance(val, models.Manager):
        # need to get an iterable to proceed
        val = val.all()

    # should this value be passed through the filters itself?
    if val.__class__ in filter_def or isinstance(
        val, (list, tuple, models.Model, models.query.QuerySet)
    ):
        val = _apply_filters_to_object(
            val, filter_def, expand_children=expand_children, klass=val.__class__
        )

    if (
        (field_type == ALWAYS)
        or isinstance(field_type, types.FunctionType)
        or ((field_type == IF_TRUTHY) and val)
        or isinstance(field_type, _ExpandableForeignKey)
    ):
        return val
    else:
        return None


def _apply_filters_to_object(inst, filter_def, expand_children=None, klass=None):
    if isinstance(inst, (list, tuple, models.query.QuerySet)):
        # if it's a tuple or list, iterate over the collection and call _apply_filters_to_object on each item
        return [
            _apply_filters_to_object(
                item, filter_def, expand_children=expand_children, klass=item.__class__
            )
            for item in inst
        ]
    elif isinstance(inst, (dict,)):
        return {
            k: _apply_filters_to_object(
                v, filter_def, expand_children=expand_children, klass=v.__class__
            )
            for k, v in inst.items()
        }

    fields_def = filter_def.get(klass)
    if fields_def is None:
        # no filter definition for this class.  Check the inheritance chain to see if we have something there
        result = None
        for base_class in inspect.getmro(klass):
            if base_class in filter_def:
                result = _apply_filters_to_object(
                    inst, filter_def, expand_children=expand_children, klass=base_class
                )
                break
        return result
    else:
        # first, recursively populate from any ancestor classes in the inheritance hierarchy
        result = defaultdict(list)
        for base in klass.__bases__:
            filtered_ancestor = _apply_filters_to_object(
                inst, filter_def, expand_children=expand_children, klass=base
            )
            if filtered_ancestor:
                result.update(filtered_ancestor)

        # now populate the fields according to fields defined in filter_def
        expandables = []
        if isinstance(fields_def, types.FunctionType):
            result = fields_def(inst)
        elif fields_def is ALWAYS:
            return inst
        else:
            for field_name, field_type in fields_def.items():
                if isinstance(field_type, _ExpandableForeignKey):
                    expandables.append(field_name)

                value = _get_filtered_field_value(
                    inst,
                    field_name,
                    field_type,
                    filter_def,
                    expand_this=field_name in expand_children,
                    expand_children=expand_children.get(field_name, {}),
                )

                if value is not None and value != DEFAULT_UNEXPANDED_VALUE:
                    result[field_name] = value
                elif (field_type == NEVER) and (field_name in result):
                    del result[field_name]

        if expandables:
            result[EXPANDABLE_FIELD_KEY] += expandables

        return result


def _compile_expansion(expand_fields):
    top = {}
    for field in expand_fields:
        d = top
        for key in field.strip().split("."):
            d.setdefault(key, {})
            d = d[key]
    return top


def apply_filters_to_object(inst, filter_def, expand_header=""):
    if expand_header:
        expand_dict = _compile_expansion(expand_header.split(","))
    else:
        expand_dict = {}
    return _apply_filters_to_object(
        inst, filter_def, expand_children=expand_dict, klass=inst.__class__
    )
