#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import logging
from pydoc import locate

from django.core.cache import cache


logger = logging.getLogger(__name__)


def rate_limit_exceeded(key="", timeout=1):
    """
    :param key: rate limit bin
    :param timeout: number of seconds to enforce between requests
    :return: True if rate limit has been exceeded (request should be throttled)

    The maximum supported rate limit is 1 request/second

    Bins should be narrow enough that multiple requests per second are not
    necessary (i.e. a requester could make many requests per second, but we
    would expect that requests related to any given RequesterUser are limited
    to a max of 1 per 5 seconds or something).

    The options for supporting rate limits higher than 1/second would all
    involve making multiple redis calls per request to enforce the rate limit,
    and would require more complex data structures in redis.

    This is not intended to be used for denial-of-service protection - that is
    frankly too complex for our API, and should probably come from a proxy.
    The design intent of this feature is protecting OTP authentication against
    brute-force attacks.
    """
    result = not cache.add("ratelimit:{0}".format(key), "1", timeout=timeout)
    if result:
        logger.warning("Detected rate limit exceeded! key='%s'", key)

    return result


def locate_object(namespaced_name):
    name_components = namespaced_name.split(".")
    module_name = ".".join(name_components[:-1])
    module = locate(module_name)
    class_name = name_components[-1]
    return getattr(module, class_name)


def instantiate_class(namespaced_class_name, *args, **kwargs):
    cls = locate_object(namespaced_class_name)
    return cls(*args, **kwargs)
