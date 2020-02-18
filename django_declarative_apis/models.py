#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import importlib
import random as python_random
import string

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models as django_models
from django.conf import settings

KEY_SIZE = 18
SECRET_SIZE = 32

random = python_random.SystemRandom()


def get_consumer(key):
    getter_str = getattr(settings, "DECLARATIVE_ENDPOINT_CONSUMER_GETTER", None)
    if getter_str is None:
        try:
            return OauthConsumer.objects.get(key=key)
        except OauthConsumer.DoesNotExist:
            return None
    else:
        module, getter = getter_str.rsplit(".", 1)
        module = importlib.import_module(module)
        getter = getattr(module, getter)
        if not callable(getter):
            raise TypeError(f"Consumer getter ({getter_str}) must be callable")
        return getter(key)


def get_random_string(
    length=20, chars=string.ascii_lowercase + string.ascii_uppercase + string.digits
):
    return "".join(random.choice(chars) for _ in range(length))


class BaseConsumer(django_models.Model):
    class Meta:
        abstract = True

    name = django_models.CharField(max_length=100, null=True, blank=True)

    content_type = django_models.ForeignKey(
        ContentType, on_delete=django_models.CASCADE, null=True
    )
    object_id = django_models.CharField(max_length=100, null=True)
    associated_object = GenericForeignKey()

    TYPE_READ_ONLY = "RO"
    TYPE_READ_WRITE = "RW"
    TYPES = ((TYPE_READ_ONLY, "Read Only"), (TYPE_READ_WRITE, "Read/Write"))
    type = django_models.CharField(
        max_length=2, choices=TYPES, default=TYPE_READ_WRITE, db_index=True
    )


class OauthConsumerManager(django_models.Manager):
    def create(self, **kwargs):
        key = kwargs.pop("key", get_random_string(length=KEY_SIZE))
        secret = kwargs.pop("secret", get_random_string(length=SECRET_SIZE))
        return super(OauthConsumerManager, self).create(
            key=key, secret=secret, **kwargs
        )


class OauthConsumer(BaseConsumer):
    objects = OauthConsumerManager()

    key = django_models.CharField(max_length=KEY_SIZE, db_index=True)
    """ Consumer key as defined by OAuth 1.0a
    """
    secret = django_models.CharField(max_length=SECRET_SIZE)
    rsa_public_key_pem = django_models.TextField(blank=True, null=True)
