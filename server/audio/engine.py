"""AudioEngine – orchestrates the visualization analysis pipeline.

Wires together the analyzer, beat detector, frame builder, and audio stream,
and runs a dedicated ~60 FPS worker thread that builds frames and publishes
them to subscribers (the WebSocket layer).

Usage::

    engine = AudioEngine(status_provider=playback_runtime.status,
                         capture_audio_provider=lambda: capture_service.audio)
    engine.start()
    unsub = engine.subscribe(lambda frame: ws.send(json.dumps(frame)))
    ...
    engine.stop()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional

from server.audio.analyzer import SpectrumAnalyzer
from server.audio.beat import BeatDetector
from server.audio.frames import FrameBuilder
from server.audio.stream import AudioStream, SAMPLE_RATE

LOGGER = logging.getLogger(__name__)

FRAME_RATE = 60.0
FRAME_INTERVAL = 1.0 / FRAME_RATE


class AudioEngine:
    """Runs the analysis loop and publishes visualization frames."""

    def __init__(
        self,
        status_provider: Callable[[], dict[str, Any]],
        capture_audio_provider: Callable[[], Optional[object]] = lambda: None,
        device_discoverer: Callable[[], int] | None = None,
        frame_rate: float = FRAME_RATE,
        num_bands: int = 128,
        fft_size: int = 2048,
        phrase_length: int = 32,
    ):
        self.frame_rate = frame_rate
        self._frame_interval = 1.0 / frame_rate

        self.analyzer = SpectrumAnalyzer(
            sample_rate=SAMPLE_RATE, fft_size=fft_size, num_bands=num_bands
        )
        self.beat_detector = BeatDetector(
            sample_rate=SAMPLE_RATE, frame_rate=frame_rate, phrase_length=phrase_length
        )
        self.frame_builder = FrameBuilder(
            self.analyzer, self.beat_detector, status_provider
        )
        self.stream = AudioStream(
            self.analyzer,
            capture_audio_provider=capture_audio_provider,
            device_discoverer=device_discoverer,
        )

        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._sub_lock = threading.Lock()

        self._worker: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    # -- lifecycle ------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()
        self.stream.start()
        self._worker = threading.Thread(
            target=self._loop, daemon=True, name="audio-engine"
        )
        self._worker.start()
        LOGGER.info("AudioEngine started (%.0f FPS)", self.frame_rate)

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_event.set()
        self.stream.stop()
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None
        LOGGER.info("AudioEngine stopped")

    def reselect_input(self) -> None:
        """Re-evaluate shared vs dedicated input (call on capture start/stop)."""
        self.stream.reselect_mode()

    @property
    def mode(self) -> str:
        return self.stream.mode

    # -- pub/sub --------------------------------------------------------

    def subscribe(self, subscriber: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        with self._sub_lock:
            self._subscribers.append(subscriber)

        def unsubscribe() -> None:
            with self._sub_lock:
                if subscriber in self._subscribers:
                    self._subscribers.remove(subscriber)

        return unsubscribe

    # -- main loop ------------------------------------------------------

    def _loop(self) -> None:
        next_tick = time.monotonic()
        while not self._stop_event.is_set():
            next_tick += self._frame_interval
            try:
                frame = self.frame_builder.build()
                self._publish(frame)
            except Exception:  # noqa: BLE001 - keep the loop alive
                LOGGER.debug("Frame build failed", exc_info=True)
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # Fell behind – reset the cadence to avoid a burst.
                next_tick = time.monotonic()

    def _publish(self, frame: dict[str, Any]) -> None:
        with self._sub_lock:
            subscribers = list(self._subscribers)
        failed = []
        for subscriber in subscribers:
            try:
                subscriber(frame)
            except Exception:  # noqa: BLE001
                failed.append(subscriber)
        if failed:
            with self._sub_lock:
                for subscriber in failed:
                    if subscriber in self._subscribers:
                        self._subscribers.remove(subscriber)
