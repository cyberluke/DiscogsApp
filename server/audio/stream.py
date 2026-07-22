"""Dual-mode SPDIF audio input for visualization.

Two operating modes, chosen automatically:

* **Shared mode** – when the :class:`CaptureService` is actively recording,
  we tap into its existing ``AudioCapture`` callback so no second audio
  device is opened (the RME SPDIF input is exclusive on some drivers).
* **Dedicated mode** – when capture is idle, we open a lightweight
  ``sounddevice.InputStream`` solely for visualization.

If no SPDIF device is present, the stream produces silence so the frontend
stays connected and renders an idle display.

The stream converts int16 PCM to float32 in [-1, 1] and pushes it into the
:class:`~server.audio.analyzer.SpectrumAnalyzer` ring buffer.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

import numpy as np

from server.audio.analyzer import SpectrumAnalyzer

LOGGER = logging.getLogger(__name__)

SAMPLE_RATE = 44100
CHANNELS = 2
DEDICATED_BLOCK_SIZE = 2048


class AudioStream:
    """Feeds the analyzer from either a shared tap or a dedicated stream."""

    def __init__(
        self,
        analyzer: SpectrumAnalyzer,
        capture_audio_provider: Callable[[], Optional[object]] = lambda: None,
        device_discoverer: Callable[[], int] | None = None,
    ):
        self._analyzer = analyzer
        # Returns the active AudioCapture (with add_tap/remove_tap) or None.
        self._capture_audio_provider = capture_audio_provider
        self._device_discoverer = device_discoverer

        self._lock = threading.Lock()
        self._mode = "idle"  # idle | shared | dedicated | silence
        self._dedicated_stream = None
        self._tapped_audio = None
        self._running = False

    # -- lifecycle ------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
        self._select_mode()
        LOGGER.info("Visualization audio stream started (mode=%s)", self._mode)

    def stop(self) -> None:
        with self._lock:
            self._running = False
        self._teardown_dedicated()
        self._detach_tap()
        self._mode = "idle"
        LOGGER.info("Visualization audio stream stopped")

    def reselect_mode(self) -> None:
        """Re-evaluate shared vs dedicated (call when capture starts/stops)."""
        if not self._running:
            return
        self._select_mode()

    @property
    def mode(self) -> str:
        return self._mode

    # -- mode selection -------------------------------------------------

    def _select_mode(self) -> None:
        capture_audio = self._capture_audio_provider()
        if capture_audio is not None and hasattr(capture_audio, "add_tap"):
            self._teardown_dedicated()
            self._attach_tap(capture_audio)
            self._mode = "shared"
            return

        self._detach_tap()
        if self._try_start_dedicated():
            self._mode = "dedicated"
        else:
            self._mode = "silence"

    def _attach_tap(self, capture_audio) -> None:
        if self._tapped_audio is capture_audio:
            return
        self._detach_tap()
        capture_audio.add_tap(self._on_capture_block)
        self._tapped_audio = capture_audio

    def _detach_tap(self) -> None:
        if self._tapped_audio is not None:
            try:
                self._tapped_audio.remove_tap(self._on_capture_block)
            except Exception:  # noqa: BLE001
                pass
            self._tapped_audio = None

    def _try_start_dedicated(self) -> bool:
        if self._dedicated_stream is not None:
            return True
        try:
            import sounddevice as sd
        except ImportError:
            LOGGER.warning("sounddevice not installed; visualization runs on silence")
            return False

        try:
            device_id = self._device_discoverer() if self._device_discoverer else None
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("No SPDIF device for visualization: %s", exc)
            return False

        try:
            self._dedicated_stream = sd.InputStream(
                device=device_id,
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=DEDICATED_BLOCK_SIZE,
                callback=self._on_dedicated_block,
            )
            self._dedicated_stream.start()
            return True
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Could not open dedicated visualization stream: %s", exc)
            self._dedicated_stream = None
            return False

    def _teardown_dedicated(self) -> None:
        if self._dedicated_stream is not None:
            try:
                self._dedicated_stream.stop()
                self._dedicated_stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._dedicated_stream = None

    # -- PCM -> analyzer ------------------------------------------------

    def _on_capture_block(self, indata) -> None:
        self._feed(indata)

    def _on_dedicated_block(self, indata, frames, time_info, status):  # noqa: ARG002
        self._feed(indata)

    def _feed(self, indata) -> None:
        try:
            arr = np.asarray(indata)
            if arr.dtype != np.float32:
                # int16 -> float32 in [-1, 1]
                arr = arr.astype(np.float32) / 32768.0
            if arr.ndim == 1:
                arr = arr.reshape(-1, CHANNELS)
            self._analyzer.push(arr)
        except Exception:  # noqa: BLE001 - never break the audio callback
            LOGGER.debug("Visualization feed failed", exc_info=True)
