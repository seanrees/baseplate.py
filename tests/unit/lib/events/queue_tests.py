import unittest

from unittest import mock

from baseplate.lib.events import EventQueue
from baseplate.lib.events import EventQueueFullError
from baseplate.lib.events import EventTooLargeError
from baseplate.lib.events import MAX_EVENT_SIZE
from baseplate.lib.message_queue import InMemoryMessageQueue
from baseplate.lib.message_queue import PosixMessageQueue
from baseplate.lib.message_queue import TimedOutError


class PosixEventQueueTests(unittest.TestCase):
    @mock.patch("baseplate.lib.events.PosixMessageQueue", autospec=PosixMessageQueue)
    def setUp(self, PosixMessageQueue):
        self.message_queue = PosixMessageQueue.return_value
        self.mock_serializer = mock.Mock()
        self.queue = EventQueue("test", event_serializer=self.mock_serializer)

    def test_send_event(self):
        self.mock_serializer.return_value = "i_am_serialized"
        event = object()

        self.queue.put(event)

        self.assertEqual(self.message_queue.put.call_count, 1)
        self.mock_serializer.assert_called_with(event)
        args, kwargs = self.message_queue.put.call_args
        self.assertEqual(args[0], self.mock_serializer.return_value)

    def test_event_too_large(self):
        self.mock_serializer.return_value = "x" * (MAX_EVENT_SIZE + 1)

        with self.assertRaises(EventTooLargeError):
            self.queue.put(object())

    def test_event_queue_full(self):
        self.mock_serializer.return_value = ""

        self.message_queue.put.side_effect = TimedOutError

        with self.assertRaises(EventQueueFullError):
            self.queue.put(object())


class InMemoryEventQueueTests(unittest.TestCase):
    @mock.patch("baseplate.lib.events.InMemoryMessageQueue", autospec=InMemoryMessageQueue)
    def setUp(self, InMemoryMessageQueue):
        self.message_queue = InMemoryMessageQueue.return_value
        self.mock_serializer = mock.Mock()
        self.queue = EventQueue(
            "test", event_serializer=self.mock_serializer, use_in_memory_queue=True
        )

    def test_send_event(self):
        self.mock_serializer.return_value = "i_am_serialized"
        event = object()

        self.queue.put(event)

        self.assertEqual(self.message_queue.put.call_count, 1)
        self.mock_serializer.assert_called_with(event)
        args, kwargs = self.message_queue.put.call_args
        self.assertEqual(args[0], self.mock_serializer.return_value)

    def test_event_queue_full(self):
        self.mock_serializer.return_value = ""

        self.message_queue.put.side_effect = TimedOutError

        with self.assertRaises(EventQueueFullError):
            self.queue.put(object())
