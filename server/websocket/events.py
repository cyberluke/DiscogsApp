from collections.abc import Callable
import threading
from typing import Any


PLAYBACK_STARTED = 'playback_started'
PLAYBACK_STOPPED = 'playback_stopped'
PROGRESS_TICK = 'progress_tick'
QUEUE_CHANGED = 'queue_changed'
PLAYLIST_CHANGED = 'playlist_changed'
PLAYBACK_PAUSED = 'playback_paused'
PLAYBACK_ERROR = 'playback_error'


class EventHub:
    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: list[Callable[[str, dict[str, Any]], None]] = []

    def subscribe(self, subscriber: Callable[[str, dict[str, Any]], None]):
        with self._lock:
            self._subscribers.append(subscriber)

    def unsubscribe(self, subscriber: Callable[[str, dict[str, Any]], None]):
        with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    def publish(self, event_type: str, payload: dict[str, Any]):
        with self._lock:
            subscribers = list(self._subscribers)

        failed_subscribers = []
        for subscriber in subscribers:
            try:
                subscriber(event_type, payload)
            except Exception:
                failed_subscribers.append(subscriber)

        if failed_subscribers:
            with self._lock:
                for subscriber in failed_subscribers:
                    if subscriber in self._subscribers:
                        self._subscribers.remove(subscriber)