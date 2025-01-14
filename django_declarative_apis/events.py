#
# Copyright (c) 2019, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

from enum import Enum
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from newrelic import agent as newrelic_agent
except ImportError:
    newrelic_agent = None


# Enum for event types
class EventType(Enum):
    QUEUE_LENGTH = "task_runner:queue_length"
    TASK_RETRY = "task_runner:retry"


def _import_hook(hook_path):
    """
    Import a hook function from a string path.

    Args:
        hook_path (str): The dotted path to the hook function.

    Returns:
        Callable: The hook function.
    """
    module_name, func_name = hook_path.rsplit(".", 1)
    module = __import__(module_name, fromlist=[func_name])
    return getattr(module, func_name)


def emit_events(metric_type, payload):
    """
    Emit a metric event using the configured hook or default to New Relic.

    Args:
        metric_type (str): Type of the metric (from MetricType enum).
        payload (dict): The data associated with the metric.
    """
    # Check if a custom hook is configured
    hook = getattr(settings, "DDA_METRIC_HOOK", None)

    if hook:
        try:
            # Dynamically load and call the hook
            hook_callable = _import_hook(hook)
            hook_callable(metric_type, payload)
            logger.info(f"Metric emitted via custom hook: {metric_type}")
        except Exception as e:
            logger.error(f"Error in custom hook for metrics: {e}", exc_info=True)
    else:
        # Fallback to New Relic if no hook is configured
        if newrelic_agent:
            try:
                newrelic_agent.record_custom_event(metric_type, payload)
                logger.info(f"Metric emitted to New Relic: {metric_type}")
            except Exception as e:
                logger.error(f"Error sending metric to New Relic: {e}", exc_info=True)
        else:
            logger.warning(
                "No metrics hook or New Relic agent configured. Metric not sent."
            )
