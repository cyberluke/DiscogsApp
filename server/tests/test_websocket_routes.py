import unittest
from importlib.util import find_spec

from flask import Flask

from server.websocket.events import EventHub
from server.websocket.routes import create_playback_socket


class FakeRuntime:
    def status(self):
        return {'playback_state': 'idle'}


class WebSocketRoutesTest(unittest.TestCase):
    def test_registers_playback_events_route_when_dependency_available(self):
        if find_spec('flask_sock') is None:
            self.skipTest('flask-sock is not installed in this Python environment')

        app = Flask(__name__)

        registered = create_playback_socket(app, FakeRuntime(), EventHub())

        self.assertTrue(registered)
        self.assertIn('/playback/events', str(app.url_map))

    def test_disables_playback_events_route_when_dependency_missing(self):
        if find_spec('flask_sock') is not None:
            self.skipTest('flask-sock is installed in this Python environment')

        app = Flask(__name__)

        registered = create_playback_socket(app, FakeRuntime(), EventHub())

        self.assertFalse(registered)
        self.assertNotIn('/playback/events', str(app.url_map))


if __name__ == '__main__':
    unittest.main()