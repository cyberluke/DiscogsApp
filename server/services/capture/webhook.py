"""Webhook receiver for ESP32 S-Link events during capture."""

import json
import logging
import queue
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

LOGGER = logging.getLogger(__name__)

DEFAULT_WEBHOOK_PORT = 5001


class _WebhookHandler(BaseHTTPRequestHandler):
    """Minimal POST /webhook handler."""

    event_queue: queue.Queue | None = None

    def do_POST(self):  # noqa: N802
        if self.path == "/webhook":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                if _WebhookHandler.event_queue is not None:
                    _WebhookHandler.event_queue.put(data)
            except (json.JSONDecodeError, ValueError):
                pass
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):  # noqa: ARG002
        pass


class WebhookReceiver:
    """Threaded HTTP server that collects ESP32 S-Link webhook events."""

    def __init__(self, port: int = DEFAULT_WEBHOOK_PORT):
        self.port = port
        self.event_queue: queue.Queue = queue.Queue()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        _WebhookHandler.event_queue = self.event_queue
        self._server = HTTPServer(("0.0.0.0", self.port), _WebhookHandler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name="capture-webhook-rx"
        )
        self._thread.start()
        LOGGER.info("Capture webhook receiver listening on port %d", self.port)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            if self._thread:
                self._thread.join(timeout=5)
            self._server = None
            self._thread = None
            LOGGER.info("Capture webhook receiver stopped")

    def wait_for_event(self, timeout: float | None = None) -> dict | None:
        """Block until the next webhook event or *timeout* seconds."""
        try:
            return self.event_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def drain(self) -> None:
        """Discard all queued events."""
        while not self.event_queue.empty():
            try:
                self.event_queue.get_nowait()
            except queue.Empty:
                break
