#
# Copyright (c) 2025, salesforce.com, inc.
# All rights reserved.
# SPDX-License-Identifier: BSD-3-Clause
# For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
#

import unittest
from unittest.mock import patch, Mock
from django_declarative_apis.events import _import_hook, emit_events
from django.test import override_settings


def test_function():
    pass


class EmitEventsTest(unittest.TestCase):
    @override_settings(DDA_EVENT_HOOK="tests.test_events.test_function")
    def test_import_hook(self):
        hook_path = "tests.test_events.test_function"
        hook_function = _import_hook(hook_path)
        self.assertTrue(callable(hook_function))
        self.assertEqual(hook_function.__name__, "test_function")

    def test_invalid_hook_path(self):
        with self.assertRaises(ValueError) as context:
            _import_hook("invalid_path")
        self.assertEqual(
            str(context.exception),
            "not enough values to unpack (expected 2, got 1)",
        )

    def test_nonexistent_function(self):
        with self.assertRaises(AttributeError) as context:
            _import_hook("tests.test_events.no_function")
        self.assertIn(
            "module 'tests.test_events' has no attribute 'no_function'",
            str(context.exception),
        )

    @patch("django_declarative_apis.events._import_hook")
    @patch("django_declarative_apis.events.logger")
    def test_emit_events_with_hook(self, mock_logger, mock_import_hook):
        event_type, payload = "test_event", {"key": "value"}
        mock_hook_function = Mock()
        mock_import_hook.return_value = mock_hook_function
        with patch(
            "django_declarative_apis.events.HOOK", "tests.test_events.test_function"
        ):
            emit_events(event_type, payload)
            mock_import_hook.assert_called_once_with("tests.test_events.test_function")
            mock_hook_function.assert_called_once_with(event_type, payload)
            mock_logger.info.assert_called_once_with(
                "Event emitted via custom hook: test_event"
            )

    @patch("django_declarative_apis.events._import_hook")
    @patch("django_declarative_apis.events.logger")
    @override_settings(DDA_EVENT_HOOK="tests.test_events.test_function")
    def test_emit_events_with_exception_calling_hook(
        self, mock_logger, mock_import_hook
    ):
        event_type, payload = "test_event", {"key": "value"}
        mock_import_hook.return_value.side_effect = Exception("Simulated Exception")
        with patch(
            "django_declarative_apis.events.HOOK", "tests.test_events.test_function"
        ):
            emit_events(event_type, payload)
            mock_logger.error.assert_called_once_with(
                "Error in custom hook for events: Simulated Exception", exc_info=True
            )
