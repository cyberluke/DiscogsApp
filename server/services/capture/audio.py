"""RME SPDIF audio capture – 44100 Hz, stereo, 16-bit PCM WAV."""

import logging
import threading
import wave
from pathlib import Path

LOGGER = logging.getLogger(__name__)

SAMPLE_RATE = 44100
CHANNELS = 2
SAMPLE_WIDTH = 2  # 16-bit PCM – CD audio is natively 16-bit
BLOCK_SIZE = 4096


def discover_rme_spdif() -> int:
    """Return the sounddevice index of the RME SPDIF input.

    Scans ``sounddevice.query_devices()`` for an *input* device whose
    name contains both ``SPDIF`` and ``RME`` (case-insensitive).
    Raises ``RuntimeError`` when no matching device is found.
    """
    import sounddevice as sd

    for idx, dev in enumerate(sd.query_devices()):
        name_upper = dev["name"].upper()
        if "SPDIF" in name_upper and "RME" in name_upper and dev["max_input_channels"] >= 2:
            LOGGER.info("Discovered RME SPDIF input: [%d] %s (in=%d)",
                        idx, dev["name"], dev["max_input_channels"])
            return idx

    LOGGER.error("RME SPDIF input not found. Available devices:")
    for idx, dev in enumerate(sd.query_devices()):
        LOGGER.error("  [%d] %s  (in=%d out=%d)",
                     idx, dev["name"],
                     dev["max_input_channels"], dev["max_output_channels"])
    raise RuntimeError(
        "No input device whose name contains both 'SPDIF' and 'RME' was found. "
        "Check that the RME RayDAT driver is installed and the SPDIF input is visible."
    )


class AudioCapture:
    """Records SPDIF audio to WAV files, splitting on track boundaries."""

    def __init__(self, device_id: int):
        self.device_id = device_id
        self._writer: wave.Wave_write | None = None
        self._lock = threading.Lock()
        self._stream = None
        self._current_path: str | None = None
        self._frames_written: int = 0
        # Optional taps receive each raw int16 indata block (shared-mode
        # visualization). Kept separate from the writer lock so a slow tap
        # never blocks WAV recording.
        self._taps: list = []
        self._taps_lock = threading.Lock()

    # -- lifecycle -------------------------------------------------------

    def start(self) -> None:
        import sounddevice as sd

        self._stream = sd.InputStream(
            device=self.device_id,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=BLOCK_SIZE,
            callback=self._audio_callback,
        )
        self._stream.start()
        LOGGER.info(
            "Audio stream started  device=%d  %d Hz  %d ch  %d-bit PCM",
            self.device_id, SAMPLE_RATE, CHANNELS, SAMPLE_WIDTH * 8,
        )

    def stop(self) -> None:
        self.close_track()
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
            LOGGER.info("Audio stream stopped")

    @property
    def is_recording(self) -> bool:
        return self._writer is not None

    # -- visualization taps (shared-mode) --------------------------------

    def add_tap(self, tap) -> None:
        """Register a callable ``tap(indata_int16)`` fed every audio block."""
        with self._taps_lock:
            if tap not in self._taps:
                self._taps.append(tap)

    def remove_tap(self, tap) -> None:
        with self._taps_lock:
            if tap in self._taps:
                self._taps.remove(tap)

    @property
    def current_path(self) -> str | None:
        return self._current_path

    @property
    def frames_written(self) -> int:
        return self._frames_written

    @property
    def current_duration(self) -> float:
        return self._frames_written / SAMPLE_RATE if self._writer else 0.0

    # -- track file management -------------------------------------------

    def open_track(self, path: Path) -> None:
        with self._lock:
            self._close_writer_locked()
            path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = wave.open(str(path), "wb")
            self._writer.setnchannels(CHANNELS)
            self._writer.setsampwidth(SAMPLE_WIDTH)
            self._writer.setframerate(SAMPLE_RATE)
            self._current_path = str(path)
            self._frames_written = 0
        LOGGER.info("▶ Recording  %s", path)

    def close_track(self) -> None:
        with self._lock:
            self._close_writer_locked()

    def _close_writer_locked(self) -> None:
        if self._writer is not None:
            self._writer.close()
            duration = self._frames_written / SAMPLE_RATE
            LOGGER.info("■ Closed     %s  (%.1f s)", self._current_path, duration)
            self._writer = None
            self._current_path = None
            self._frames_written = 0

    # -- sounddevice callback (real-time thread) -------------------------

    def _audio_callback(self, indata, frames, time_info, status):  # noqa: ARG002
        if status:
            LOGGER.warning("Audio callback status: %s", status)
        with self._lock:
            if self._writer is not None:
                raw = indata.tobytes() if hasattr(indata, "tobytes") else bytes(indata)
                self._writer.writeframes(raw)
                self._frames_written += frames
        # Feed visualization taps outside the writer lock. Failures in a tap
        # must never interrupt recording.
        with self._taps_lock:
            taps = list(self._taps)
        for tap in taps:
            try:
                tap(indata)
            except Exception:  # noqa: BLE001 - taps are best-effort
                LOGGER.debug("Visualization tap failed", exc_info=True)
