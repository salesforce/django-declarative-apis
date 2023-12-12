#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#
from abc import ABC, abstractmethod
from collections import defaultdict
import inspect
import logging
import types

import pydantic
from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import ManyToOneRel
from django.db.models.fields.reverse_related import ForeignObjectRel

logger = logging.getLogger(__name__)

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
        except FieldDoesNotExist:
            raise ValueError(f"{display_key} is not a field on {model_class.__name__}")
    return _ExpandableForeignKey(display_key, model_class, inst_field_name)


class ExpandableGeneric(ABC):
    @abstractmethod
    def get_unexpanded_view(self, inst) -> dict:
        raise NotImplementedError()

    @abstractmethod
    def get_expanded_view(self, inst) -> dict:
        raise NotImplementedError()


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


def _is_relation(field):
    return field.is_relation or getattr(field, "is_fake_relation", False)


def _is_reverse_relation(field):
    return isinstance(field, ForeignObjectRel)


def _get_callable_field_value_with_cache(inst, field_name, model_cache, field_type):
    cache_relation = True

    try:
        field_meta = inst._meta.get_field(field_name)
        if not _is_relation(field_meta) or _is_reverse_relation(field_meta):
            # no `attname` in reverse relations
            cache_relation = False
    except (AttributeError, FieldDoesNotExist):
        # inst doesn't look like a django model
        cache_relation = False

    if cache_relation:
        # we're caching a foreign key field on a django model.  Cache it by (model, fk_pk) so that if
        # other objects reference this same instance, we'll get a cache hit
        fk_pk = getattr(inst, field_meta.attname)
        val_cls = field_meta.related_model
        cache_key = _make_model_cache_key(val_cls, fk_pk)
    else:
        # not a foreign key.  Cache it by (inst, field_name) - it won't be a cache hit on another instance, but
        # will be cached if this same inst is returned later in the response
        cache_key = (id(inst), field_name)

    if cache_key in model_cache:
        logger.debug("ev=model_cache, status=hit, key=%s", cache_key)
        result = model_cache[cache_key]
    else:
        logger.debug("ev=model_cache, status=miss, key=%s", cache_key)
        result = field_type(inst)

        if isinstance(result, models.Manager):
            # need to get an iterable to proceed
            result = result.all()
        model_cache[cache_key] = result
    return result


def _get_filtered_field_value(  # noqa: C901
    inst,
    field_name,
    field_type,
    filter_def,
    expand_this,
    expand_children,
    filter_cache,
    model_cache,
):
    # get the value from inst
    if field_type == NEVER:
        return None

    if isinstance(field_type, types.FunctionType):
        if is_caching_enabled():
            val = _get_callable_field_value_with_cache(
                inst, field_name, model_cache, field_type
            )
        else:
            val = field_type(inst)
    elif isinstance(field_type, _ExpandableForeignKey):
        if expand_this:
            inst_field_name = field_type.inst_field_name or field_name
            val = getattr(inst, inst_field_name)
        else:
            val = _get_unexpanded_field_value(inst, field_name, field_type)
    elif isinstance(field_type, ExpandableGeneric):
        if expand_this:
            val = field_type.get_expanded_view(inst)
        else:
            val = field_type.get_unexpanded_view(inst)
    else:
        try:
            if isinstance(inst, (models.Model)):
                try:
                    field_meta = inst._meta.get_field(field_name)
                    if _is_relation(field_meta):
                        val_pk = getattr(inst, field_meta.attname)
                        val_cls = field_meta.related_model
                        val_expand_children = expand_children.get(field_name, {})
                        cache_key = _make_filter_cache_key(
                            val_expand_children, val_cls, val_pk
                        )
                        if cache_key in filter_cache:
                            logger.debug(
                                "ev=filter_cache, status=hit, key=%s", cache_key
                            )
                            return filter_cache[cache_key]
                except FieldDoesNotExist:
                    # this happens when you reference the special field "pk" in filters
                    pass

            val = getattr(inst, field_name)
        except (AttributeError, FieldDoesNotExist):
            return None

    if isinstance(val, models.Manager):
        # need to get an iterable to proceed
        val = val.all()

    # should this value be passed through the filters itself?
    # `dict` is intentionally excluded to allow endpoints to return an arbitrary response that bypasses filtering
    if val.__class__ in filter_def or isinstance(
        val, (list, tuple, models.Model, models.query.QuerySet, pydantic.BaseModel)
    ):
        val = _apply_filters_to_object(
            val, filter_def, expand_children, val.__class__, filter_cache, model_cache
        )

    if (
        (field_type == ALWAYS)
        or isinstance(field_type, types.FunctionType)
        or ((field_type == IF_TRUTHY) and val)
        or isinstance(field_type, _ExpandableForeignKey)
        or isinstance(field_type, ExpandableGeneric)
    ):
        return val
    else:
        return None


def _make_filter_cache_key(expand_children, klass, pk):
    return (str(expand_children), klass, str(pk))


def _make_model_cache_key(klass, pk):
    return (klass, str(pk))


# TODO: make this method less complex and remove the `noqa`
def _apply_filters_to_object(  # noqa: C901
    inst, filter_def, expand_children, klass, filter_cache, model_cache
):
    is_cacheable = False
    if (
        is_caching_enabled()
        and isinstance(inst, (models.Model,))
        and filter_cache is not None
    ):
        is_cacheable = True
        pk = getattr(inst, "pk")
        cache_key = _make_filter_cache_key(expand_children, klass, pk)
        if cache_key in filter_cache:
            logger.debug("ev=filter_cache, status=hit, key=%s", cache_key)
            return filter_cache[cache_key]
        else:
            logger.debug("ev=filter_cache, status=miss, key=%s", cache_key)
    if isinstance(inst, (list, tuple, models.query.QuerySet)):
        # if it's a tuple or list, iterate over the collection and call _apply_filters_to_object on each item
        return [
            _apply_filters_to_object(
                item,
                filter_def,
                expand_children,
                item.__class__,
                filter_cache,
                model_cache,
            )
            for item in inst
        ]
    elif isinstance(inst, (dict,)):
        return {
            k: _apply_filters_to_object(
                v,
                filter_def,
                expand_children,
                v.__class__,
                filter_cache,
                model_cache,
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
                    inst,
                    filter_def,
                    expand_children,
                    base_class,
                    filter_cache,
                    model_cache,
                )
                break

        if is_cacheable:
            filter_cache[cache_key] = result

        return result
    else:
        # first, recursively populate from any ancestor classes in the inheritance hierarchy
        result = defaultdict(list)
        for base in klass.__bases__:
            filtered_ancestor = _apply_filters_to_object(
                inst, filter_def, expand_children, base, filter_cache, model_cache
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
                if isinstance(field_type, (_ExpandableForeignKey, ExpandableGeneric)):
                    expandables.append(field_name)

                value = _get_filtered_field_value(
                    inst,
                    field_name,
                    field_type,
                    filter_def,
                    expand_this=field_name in expand_children,
                    expand_children=expand_children.get(field_name, {}),
                    filter_cache=filter_cache,
                    model_cache=model_cache,
                )

                if value is not None and value != DEFAULT_UNEXPANDED_VALUE:
                    result[field_name] = value
                elif (field_type == NEVER) and (field_name in result):
                    del result[field_name]

        if expandables:
            result[EXPANDABLE_FIELD_KEY] += expandables

        if is_cacheable:
            filter_cache[cache_key] = result

        return result


def _compile_expansion(expand_fields):
    top = {}
    for field in expand_fields:
        d = top
        for key in field.strip().split("."):
            d.setdefault(key, {})
            d = d[key]
    return top


def is_caching_enabled():
    return getattr(settings, "DDA_FILTER_MODEL_CACHING_ENABLED", False)


def apply_filters_to_object(inst, filter_def, expand_header=""):
    if expand_header:
        expand_dict = _compile_expansion(expand_header.split(","))
    else:
        expand_dict = {}
    return _apply_filters_to_object(
        inst,
        filter_def,
        expand_children=expand_dict,
        klass=inst.__class__,
        filter_cache={},
        model_cache={},
    )
