"""Musical key estimation from a 12-bin pitch-class chroma.

Uses the Krumhansl–Schmuckler key-finding algorithm: the chroma is correlated
against major and minor key profiles for all 12 tonics, and the best-scoring
key is selected. The result is mapped onto the Camelot wheel (the notation DJs
use, e.g. ``8A`` / ``9B``) so the display can show a harmonically meaningful key.

The detector is deliberately *stable*: it only changes its reported key when a
new key has been the best match for several consecutive frames, so the readout
does not flicker between closely related keys as the harmony shifts.
"""

from __future__ import annotations

import numpy as np

# Krumhansl–Kessler key profiles (pitch-class weights for C major / A minor,
# rotated for every other tonic).
_MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88],
    dtype=np.float32,
)
_MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17],
    dtype=np.float32,
)

# Camelot wheel mapping. Index = pitch class (0=C .. 11=B).
# Minor keys -> "A" ring, major keys -> "B" ring.
_CAMELOT_MINOR = [
    "5A", "12A", "7A", "2A", "9A", "4A",
    "11A", "6A", "1A", "8A", "3A", "10A",
]
_CAMELOT_MAJOR = [
    "8B", "3B", "10B", "5B", "12B", "7B",
    "2B", "9B", "4B", "11B", "6B", "1B",
]

# How many consecutive frames a candidate must win before we switch to it.
_STABILITY_FRAMES = 12


class KeyDetector:
    """Estimates a stable Camelot key from successive chroma vectors."""

    def __init__(self) -> None:
        self._current: str | None = None
        self._candidate: str | None = None
        self._candidate_count = 0

    def update(self, chroma: np.ndarray) -> str | None:
        """Feed a 12-bin chroma (0..1) and return the current stable key."""
        chroma = np.asarray(chroma, dtype=np.float32)
        if chroma.size != 12 or float(np.sum(chroma)) < 1e-3:
            # Silence / no tonal content — hold the last known key.
            return self._current

        best_key = self._best_key(chroma)

        if best_key == self._current:
            self._candidate = None
            self._candidate_count = 0
            return self._current

        if best_key == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = best_key
            self._candidate_count = 1

        if self._candidate_count >= _STABILITY_FRAMES:
            self._current = best_key
            self._candidate = None
            self._candidate_count = 0

        return self._current

    def reset(self) -> None:
        self._current = None
        self._candidate = None
        self._candidate_count = 0

    @staticmethod
    def _best_key(chroma: np.ndarray) -> str:
        best_score = -np.inf
        best_key = "8A"
        for tonic in range(12):
            major = np.roll(_MAJOR_PROFILE, tonic)
            minor = np.roll(_MINOR_PROFILE, tonic)
            score_major = _correlate(chroma, major)
            score_minor = _correlate(chroma, minor)
            if score_major > best_score:
                best_score = score_major
                best_key = _CAMELOT_MAJOR[tonic]
            if score_minor > best_score:
                best_score = score_minor
                best_key = _CAMELOT_MINOR[tonic]
        return best_key


def _correlate(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation between two profiles."""
    a = a - np.mean(a)
    b = b - np.mean(b)
    denom = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
    if denom < 1e-9:
        return 0.0
    return float(np.sum(a * b) / denom)
