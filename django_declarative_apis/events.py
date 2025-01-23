#
# Copyright (c) 2025, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import importlib
from enum import Enum
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

HOOK = getattr(settings, "DDA_EVENT_HOOK", None)


# Enum for event types
class EventType(Enum):
    QUEUE_SNAPSHOT = "queue_snapshot"
    TASK_RETRY_ATTEMPT = "task_retry"


def _import_hook(hook_path):
    """
    Import and return a hook function from a string path.

    This function dynamically imports a hook function specified by a dotted string path.
    It ensures that the imported object is callable and raises an error if it is not.

    Args:
        hook_path (str): The dotted string path to the hook function.
                         For example, 'module.submodule.function'.

    Returns:
        Callable: The imported hook function.

    Raises:
        TypeError: If the imported object is not callable.
    """
    module_path, function_name = hook_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    function = getattr(module, function_name)
    if not callable(function):
        raise TypeError(f"Consumer getter ({hook_path}) must be callable")
    return function


def emit_events(event_type, payload):
    """
    Emit a metric event using the configured hook.
    This function sends an event to a custom hook, if configured, with the specified
    event type and payload. The hook is dynamically imported and executed. Logs any errors
    encountered during the hook execution.

    Args:
        event_type (EventType): The type of the event, as defined in the EventType enum.
        payload (dict): A dictionary containing the data associated with the event.
                        This data is passed to the custom hook for processing.
    Raises:
        Exception: Logs an error if the custom hook encounters an issue during execution.
    """
    if HOOK:
        try:
            hook_callable = _import_hook(HOOK)
            hook_callable(event_type, payload)
            logger.info(f"Event emitted via custom hook: {event_type}")
        except Exception as e:
            logger.error(f"Error in custom hook for events: {e}", exc_info=True)
