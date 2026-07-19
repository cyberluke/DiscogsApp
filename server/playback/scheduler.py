import threading
import time
from collections.abc import Callable


class PlaybackScheduler:
    def __init__(
        self,
        lock: threading.RLock,
        is_playing: Callable[[], bool],
        update_progress: Callable[[], None],
        should_advance: Callable[[], bool],
        advance: Callable[[], None],
        interval_seconds: float = 1,
    ):
        self.lock = lock
        self.is_playing = is_playing
        self.update_progress = update_progress
        self.should_advance = should_advance
        self.advance = advance
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self.stop_event.set()

    def tick(self):
        with self.lock:
            if self.is_playing():
                self.update_progress()
                if self.should_advance():
                    self.advance()

    def _loop(self):
        while not self.stop_event.is_set():
            self.tick()
            time.sleep(self.interval_seconds)