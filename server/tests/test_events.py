import unittest

from server.websocket.events import EventHub


class EventHubTest(unittest.TestCase):
    def test_publish_notifies_subscribers(self):
        hub = EventHub()
        events = []

        hub.subscribe(lambda event_type, payload: events.append((event_type, payload)))
        hub.publish('snapshot', {'playback_state': 'idle'})

        self.assertEqual(events, [('snapshot', {'playback_state': 'idle'})])

    def test_unsubscribe_removes_subscriber(self):
        hub = EventHub()
        events = []

        def subscriber(event_type, payload):
            events.append((event_type, payload))

        hub.subscribe(subscriber)
        hub.unsubscribe(subscriber)
        hub.publish('snapshot', {'playback_state': 'idle'})

        self.assertEqual(events, [])

    def test_publish_removes_failed_subscribers_without_blocking_healthy_subscribers(self):
        hub = EventHub()
        events = []

        def failed_subscriber(event_type, payload):
            raise RuntimeError('socket closed')

        hub.subscribe(failed_subscriber)
        hub.subscribe(lambda event_type, payload: events.append((event_type, payload)))

        hub.publish('progress_tick', {'playback_state': 'playing'})
        hub.publish('playback_stopped', {'playback_state': 'stopped'})

        self.assertEqual(events, [
            ('progress_tick', {'playback_state': 'playing'}),
            ('playback_stopped', {'playback_state': 'stopped'}),
        ])


if __name__ == '__main__':
    unittest.main()