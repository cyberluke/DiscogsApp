"""Spectral analysis: FFT bands, RMS/peak VU, bass/mid/treble, stereo width.

All DSP lives here. The analyzer is fed PCM blocks from the audio stream
callback and queried at ~60 FPS by the engine to produce a feature snapshot.

Design notes
------------
* A fixed-size ring buffer holds the most recent ``fft_size`` stereo frames.
  The sounddevice callback writes into it (~10 Hz); the engine reads the
  latest window at ~60 FPS. Writing uses a write index to avoid per-call
  allocation in the real-time callback.
* The 128 output bands are logarithmically spaced (20 Hz – 20 kHz) to match
  human pitch perception, then smoothed with fast-attack / slow-release and a
  falling peak-hold, exactly like a hardware spectrum analyzer.
* Uses only ``numpy`` (no scipy) to keep the dependency footprint minimal.
"""

from __future__ import annotations

import threading

import numpy as np

# Frequency range for the log-spaced bands.
MIN_FREQ = 20.0
MAX_FREQ = 20000.0

# Band boundaries (Hz) for the three-way energy meter.
BASS_MAX = 250.0
MID_MAX = 4000.0
TREBLE_MAX = 16000.0

# Smoothing coefficients (fast attack, slow release).
ATTACK = 0.6
RELEASE = 0.15
PEAK_FALL = 0.012  # per-frame peak decay


class RingBuffer:
    """Fixed-size stereo float32 ring buffer.

    ``write`` appends interleaved stereo frames and never allocates on the
    hot path (it copies into a pre-allocated array). ``latest`` returns the
    most recent ``n`` frames as a contiguous ``(n, 2)`` array.
    """

    def __init__(self, capacity: int, channels: int = 2):
        self.capacity = capacity
        self.channels = channels
        self._data = np.zeros((capacity, channels), dtype=np.float32)
        self._write_pos = 0
        self._filled = 0
        self._lock = threading.Lock()

    def write(self, frames: np.ndarray) -> None:
        """Append ``frames`` (shape ``(n, channels)``) into the buffer."""
        n = frames.shape[0]
        if n == 0:
            return
        with self._lock:
            if n >= self.capacity:
                # Block larger than the buffer: keep only the tail.
                self._data[:] = frames[-self.capacity:]
                self._write_pos = 0
                self._filled = self.capacity
                return
            end = self._write_pos + n
            if end <= self.capacity:
                self._data[self._write_pos:end] = frames
            else:
                first = self.capacity - self._write_pos
                self._data[self._write_pos:] = frames[:first]
                self._data[: n - first] = frames[first:]
            self._write_pos = end % self.capacity
            self._filled = min(self._filled + n, self.capacity)

    def latest(self, n: int) -> np.ndarray:
        """Return the most recent ``n`` frames as a contiguous array."""
        with self._lock:
            n = min(n, self._filled)
            if n <= 0:
                return np.zeros((self._data.shape[1],), dtype=np.float32)
            start = (self._write_pos - n) % self.capacity
            if start + n <= self.capacity:
                return self._data[start : start + n].copy()
            return np.concatenate(
                (self._data[start:], self._data[: n - (self.capacity - start)])
            )

    def clear(self) -> None:
        with self._lock:
            self._data[:] = 0
            self._write_pos = 0
            self._filled = 0


class SpectrumAnalyzer:
    """Computes spectrum bands and level meters from a PCM ring buffer."""

    def __init__(
        self,
        sample_rate: int = 44100,
        fft_size: int = 2048,
        num_bands: int = 128,
    ):
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.num_bands = num_bands

        self._window = np.hanning(fft_size).astype(np.float32)
        self._buffer = RingBuffer(fft_size, channels=2)

        # Log-spaced band edges -> FFT bin ranges.
        self._band_bins = self._compute_band_bins()

        # Smoothing / peak-hold state (reused every frame, no allocation).
        self._smoothed = np.zeros(num_bands, dtype=np.float32)
        self._peaks = np.zeros(num_bands, dtype=np.float32)

    # -- feed -----------------------------------------------------------

    def push(self, frames: np.ndarray) -> None:
        """Feed interleaved stereo float32 frames in [-1, 1]."""
        self._buffer.write(frames)

    def reset(self) -> None:
        self._buffer.clear()
        self._smoothed[:] = 0
        self._peaks[:] = 0

    # -- analysis -------------------------------------------------------

    def analyze(self) -> dict:
        """Return the current feature snapshot (dict of numpy scalars/arrays)."""
        window = self._buffer.latest(self.fft_size)
        if window.ndim != 2 or window.shape[0] < self.fft_size:
            # Not enough audio yet – pad with silence.
            pad = np.zeros((self.fft_size, 2), dtype=np.float32)
            if window.ndim == 2:
                pad[-window.shape[0]:] = window
            window = pad

        left = window[:, 0]
        right = window[:, 1]
        mono = (left + right) * 0.5

        spectrum = self._magnitude_spectrum(mono)
        bands = self._to_bands(spectrum)
        self._smooth(bands)

        return {
            "fft": self._smoothed.copy(),
            "peaks": self._peaks.copy(),
            "vu_left": self._level(left),
            "vu_right": self._level(right),
            "peak_left": float(np.max(np.abs(left))) if left.size else 0.0,
            "peak_right": float(np.max(np.abs(right))) if right.size else 0.0,
            "bass": self._band_energy(spectrum, MIN_FREQ, BASS_MAX),
            "mid": self._band_energy(spectrum, BASS_MAX, MID_MAX),
            "treble": self._band_energy(spectrum, MID_MAX, TREBLE_MAX),
            "energy": self._level(mono),
            "width": self._stereo_width(left, right),
            # 12-bin pitch-class chroma (C, C#, D, ... B), 0..1, for key detection.
            "chroma": self._chroma(spectrum),
            # Raw onset signal for the beat detector (spectral flux input).
            "_onset": float(np.mean(bands)),
        }

    # -- internals ------------------------------------------------------

    def _compute_band_bins(self) -> list[tuple[int, int]]:
        edges = np.logspace(
            np.log10(MIN_FREQ), np.log10(MAX_FREQ), self.num_bands + 1
        )
        nyquist_bins = self.fft_size // 2
        bins_per_hz = self.fft_size / self.sample_rate
        ranges: list[tuple[int, int]] = []
        for lo, hi in zip(edges[:-1], edges[1:]):
            start = max(1, int(lo * bins_per_hz))
            stop = min(nyquist_bins, max(start + 1, int(hi * bins_per_hz)))
            ranges.append((start, stop))
        return ranges

    def _magnitude_spectrum(self, mono: np.ndarray) -> np.ndarray:
        windowed = mono * self._window
        fft = np.fft.rfft(windowed)
        mag = np.abs(fft).astype(np.float32)
        # Log compression to a 0..1 display range.
        return np.log1p(mag * 8.0) / np.log1p(8.0 * self.fft_size * 0.25)

    def _to_bands(self, spectrum: np.ndarray) -> np.ndarray:
        bands = np.empty(self.num_bands, dtype=np.float32)
        for i, (start, stop) in enumerate(self._band_bins):
            stop = min(stop, spectrum.shape[0])
            if stop <= start:
                bands[i] = 0.0
            else:
                bands[i] = float(np.mean(spectrum[start:stop]))
        return np.clip(bands, 0.0, 1.0)

    def _smooth(self, bands: np.ndarray) -> None:
        # Fast attack, slow release.
        rising = bands > self._smoothed
        self._smoothed[rising] = (
            self._smoothed[rising] * (1 - ATTACK) + bands[rising] * ATTACK
        )
        self._smoothed[~rising] = (
            self._smoothed[~rising] * (1 - RELEASE) + bands[~rising] * RELEASE
        )
        # Falling peak hold.
        self._peaks = np.maximum(self._smoothed, self._peaks - PEAK_FALL)

    @staticmethod
    def _level(samples: np.ndarray) -> float:
        if samples.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(samples * samples)))
        return min(1.0, rms * 1.4)  # scale so a full-scale sine ≈ 1.0

    def _band_energy(self, spectrum: np.ndarray, lo: float, hi: float) -> float:
        bins_per_hz = self.fft_size / self.sample_rate
        start = max(1, int(lo * bins_per_hz))
        stop = min(spectrum.shape[0], int(hi * bins_per_hz))
        if stop <= start:
            return 0.0
        return float(np.clip(np.mean(spectrum[start:stop]) * 1.6, 0.0, 1.0))

    @staticmethod
    def _stereo_width(left: np.ndarray, right: np.ndarray) -> float:
        mid = (left + right) * 0.5
        side = (left - right) * 0.5
        mid_rms = float(np.sqrt(np.mean(mid * mid)))
        side_rms = float(np.sqrt(np.mean(side * side)))
        if mid_rms < 1e-6:
            return 0.0
        return float(np.clip(side_rms / mid_rms, 0.0, 1.0))

    def _chroma(self, spectrum: np.ndarray) -> np.ndarray:
        """Fold the magnitude spectrum into 12 pitch-class bins (C..B).

        Each FFT bin is mapped to the nearest semitone across all octaves and
        its energy accumulated into the corresponding pitch class. The result
        is normalised to 0..1 and used downstream for Camelot key estimation.
        """
        chroma = np.zeros(12, dtype=np.float32)
        bins = spectrum.shape[0]
        if bins < 2:
            return chroma

        # Frequency of each rfft bin.
        freqs = np.arange(bins, dtype=np.float32) * (self.sample_rate / self.fft_size)

        # Only consider the musically useful range (~55 Hz – 2 kHz).
        mask = (freqs >= 55.0) & (freqs <= 2000.0)
        idx = np.nonzero(mask)[0]
        if idx.size == 0:
            return chroma

        f = freqs[idx]
        # MIDI note number (A4 = 69 = 440 Hz), rounded to nearest semitone.
        midi = np.round(69.0 + 12.0 * np.log2(f / 440.0)).astype(np.int32)
        pitch_class = np.mod(midi, 12)

        energy = spectrum[idx]
        np.add.at(chroma, pitch_class, energy)

        peak = float(np.max(chroma))
        if peak > 1e-6:
            chroma /= peak
        return chroma
