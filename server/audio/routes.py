"""WebSocket endpoint streaming visualization frames at ~60 FPS.

Separate from ``/playback/events`` because it is high-frequency and carries
render data, not playback state. The :class:`AudioEngine` publishes frames;
this module forwards them to each connected socket as JSON.
"""

import json
import threading
from typing import Any


def create_visualization_socket(app, audio_engine) -> bool:
    try:
        from flask_sock import Sock
    except ImportError:
        app.logger.warning(
            "flask-sock is not installed; /visualization/frames WebSocket disabled"
        )
        return False

    sock = Sock(app)

    @sock.route('/visualization/frames')
    def visualization_frames(socket):
        socket_lock = threading.Lock()

        def send_frame(frame: dict[str, Any]):
            with socket_lock:
                socket.send(json.dumps(frame))

        unsubscribe = audio_engine.subscribe(send_frame)
        try:
            while True:
                if socket.receive() is None:
                    break
        finally:
            unsubscribe()

    return True
