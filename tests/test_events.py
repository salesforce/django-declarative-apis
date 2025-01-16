#
# Copyright (c) 2019, salesforce.com, inc.
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


class ImportHookTest(unittest.TestCase):
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
            "Invalid hook path: 'invalid_path'. Must be in the format 'module_name.function_name'.",
        )

    def test_nonexistent_function(self):
        with self.assertRaises(ImportError) as context:
            _import_hook("tests.test_events.no_function")
        self.assertIn(
            "Module 'tests.test_events' does not have an attribute 'no_function': module 'tests.test_events' has no attribute 'no_function'",
            str(context.exception),
        )


class EmitEventsTest(unittest.TestCase):
    def setUp(self):
        self.logger = Mock()
        self.custom_hook = "tests.test_events.test_function"

    @patch("django_declarative_apis.events.newrelic_agent")
    @patch("django_declarative_apis.events._import_hook")
    @patch("django_declarative_apis.events.logger")
    @override_settings(DDA_EVENT_HOOK="tests.test_events.test_function")
    def test_emit_events_with_hook_and_newrelic(
        self, mock_logger, mock_import_hook, mock_newrelic_agent
    ):
        event_type = "test_event"
        payload = {"key": "value"}

        mock_hook_function = Mock()
        mock_import_hook.return_value = mock_hook_function
        mock_newrelic_agent.record_custom_event = Mock()

        emit_events(event_type, payload)
        mock_import_hook.assert_called_once_with("tests.test_events.test_function")
        mock_hook_function.assert_called_once_with(event_type, payload)
        mock_newrelic_agent.record_custom_event.assert_called_once_with(
            event_type, payload
        )
        assert mock_logger.info.call_count == 2
        log_calls = [args[0] for args, _ in mock_logger.info.call_args_list]
        assert "Event emitted via custom hook: test_event" in log_calls
        assert "Event emitted to New Relic: test_event" in log_calls

    @patch("django_declarative_apis.events.newrelic_agent")
    @patch("django_declarative_apis.events.logger")
    def test_emit_events_with_new_relic(self, mock_logger, mock_newrelic_agent):
        event_type = "test_event"
        payload = {"key": "value"}
        mock_newrelic_agent.record_custom_event = Mock()
        emit_events(event_type, payload)
        mock_newrelic_agent.record_custom_event.assert_called_once_with(
            event_type, payload
        )
        assert mock_logger.info.call_count == 2
        log_calls = [args[0] for args, _ in mock_logger.info.call_args_list]
        assert (
            "No custom hook configured. Skipping custom hook for event: test_event"
            in log_calls
        )
        assert "Event emitted to New Relic: test_event" in log_calls

    @patch("django_declarative_apis.events.logger")
    def test_emit_events_with_no_hook_new_relic(self, mock_logger):
        event_type = "test_event"
        payload = {"key": "value"}
        emit_events(event_type, payload)
        assert mock_logger.info.call_count == 2
        log_calls = [args[0] for args, _ in mock_logger.info.call_args_list]
        assert (
            "No custom hook configured. Skipping custom hook for event: test_event"
            in log_calls
        )
        assert "No New Relic agent configured. Event test_event not sent." in log_calls

        assert mock_logger.warning.call_count == 1
        mock_logger.warning.assert_called_once_with(
            f"No event emitter configured for event: {event_type}. Event not sent."
        )
