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

    Raises:
        ValueError: If the hook path is invalid.
        ImportError: If the module or function cannot be imported.
    """
    module_name = None
    func_name = None

    try:
        module_name, func_name = hook_path.rsplit(".", 1)
    except ValueError:
        raise ValueError(
            f"Invalid hook path: '{hook_path}'. Must be in the format 'module_name.function_name'."
        )

    try:
        module = __import__(module_name, fromlist=[func_name])
        return getattr(module, func_name)
    except ImportError as e:
        raise ImportError(f"Could not import module '{module_name}': {e}") from e
    except AttributeError as e:
        raise ImportError(
            f"Module '{module_name}' does not have an attribute '{func_name}': {e}"
        ) from e


def emit_events(event_type, payload):
    """
    Emit a metric event using the configured hook and New Relic if configured.

    Args:
        metric_type (str): Type of the metric (from MetricType enum).
        payload (dict): The data associated with the metric.
    """
    hook = getattr(settings, "DDA_EVENT_HOOK", None)

    if hook:
        try:
            hook_callable = _import_hook(hook)
            hook_callable(event_type, payload)
            logger.info(f"Event emitted via custom hook: {event_type}")
        except Exception as e:
            logger.error(f"Error in custom hook for events: {e}", exc_info=True)
    
    if newrelic_agent:
        try:
            newrelic_agent.record_custom_event(event_type, payload)
            logger.info(f"Event emitted to New Relic: {event_type}")
        except Exception as e:
            logger.error(f"Error sending event to New Relic: {e}", exc_info=True)
    else:
        logger.warning(
            "No New Relic agent configured. Event not sent."
        )
