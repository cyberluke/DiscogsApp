import json
import threading
from typing import Any


def create_playback_socket(app, playback_runtime, event_hub) -> bool:
    try:
        from flask_sock import Sock
    except ImportError:
        app.logger.warning("flask-sock is not installed; /playback/events WebSocket disabled")
        return False

    sock = Sock(app)

    @sock.route('/playback/events')
    def playback_events(socket):
        socket_lock = threading.Lock()

        def send_event(event_type: str, payload: dict[str, Any]):
            message = json.dumps({'type': event_type, 'payload': payload})
            with socket_lock:
                socket.send(message)

        event_hub.subscribe(send_event)
        send_event('snapshot', playback_runtime.status())

        try:
            while True:
                if socket.receive() is None:
                    break
        finally:
            event_hub.unsubscribe(send_event)

    return True