"""Assembles the per-frame visualization payload.

Combines the :class:`~server.audio.analyzer.SpectrumAnalyzer` features and
the :class:`~server.audio.beat.BeatDetector` state with the current track
metadata from the playback runtime into the single JSON object the frontend
expects:

    {
      "timestamp": 0,
      "fft": [...128 values...],
      "vuLeft": 0.82, "vuRight": 0.77,
      "bass": 0.91, "mid": 0.48, "treble": 0.31,
      "energy": 0.74,
      "beat": true, "bpm": 141,
      "phraseProgress": 12, "phraseLength": 32,
      "track": {"artist": "Cappella", "title": "U & Me"},
      "nextTransition": {"seconds": 18, "score": 0.97}
    }
"""

from __future__ import annotations

from typing import Any, Callable

from server.audio.analyzer import SpectrumAnalyzer
from server.audio.beat import BeatDetector
from server.audio.key import KeyDetector


def _track_value(track: Any, name: str) -> Any:
    """Best-effort field lookup on a track dict/object."""
    if track is None:
        return None
    if isinstance(track, dict):
        return track.get(name)
    return getattr(track, name, None)


class FrameBuilder:
    """Builds visualization frames from the analyzer + beat detector."""

    def __init__(
        self,
        analyzer: SpectrumAnalyzer,
        beat_detector: BeatDetector,
        status_provider: Callable[[], dict[str, Any]],
    ):
        self._analyzer = analyzer
        self._beat = beat_detector
        self._status_provider = status_provider
        self._key_detector = KeyDetector()
        self._start_time = self._now()

    @staticmethod
    def _now() -> float:
        import time

        return time.monotonic()

    def build(self) -> dict[str, Any]:
        features = self._analyzer.analyze()
        rhythm = self._beat.update(features["_onset"], features["energy"])
        key = self._key_detector.update(features["chroma"])

        track = self._current_track()
        remaining = self._remaining_seconds()
        transition_seconds = self._transition_seconds(remaining, rhythm["transition"])

        return {
            "timestamp": round((self._now() - self._start_time) * 1000),
            "fft": [round(float(v), 4) for v in features["fft"]],
            "peaks": [round(float(v), 4) for v in features["peaks"]],
            "vuLeft": round(float(features["vu_left"]), 4),
            "vuRight": round(float(features["vu_right"]), 4),
            "peakLeft": round(float(features["peak_left"]), 4),
            "peakRight": round(float(features["peak_right"]), 4),
            "bass": round(float(features["bass"]), 4),
            "mid": round(float(features["mid"]), 4),
            "treble": round(float(features["treble"]), 4),
            "energy": round(float(features["energy"]), 4),
            "width": round(float(features["width"]), 4),
            "beat": bool(rhythm["beat"]),
            "bpm": rhythm["bpm"],
            "key": key,
            "phraseProgress": rhythm["phraseProgress"],
            "phraseLength": rhythm["phraseLength"],
            "track": track,
            "nextTransition": {
                "seconds": transition_seconds,
                "score": round(float(rhythm["transition"]), 4),
            },
        }

    # -- playback metadata ---------------------------------------------

    def _current_track(self) -> dict[str, str]:
        status = self._safe_status()
        track = status.get("current_track")
        artist = (
            _track_value(track, "artist")
            or _track_value(track, "full_name")
            or _track_value(track, "artists_sort")
            or ""
        )
        title = _track_value(track, "title") or ""
        return {"artist": str(artist or ""), "title": str(title or "")}

    def _remaining_seconds(self) -> int | None:
        status = self._safe_status()
        remaining = status.get("remaining")
        try:
            return int(remaining) if remaining is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _transition_seconds(remaining: int | None, score: float) -> int | None:
        """Estimate seconds until the next mix point.

        Uses the remaining track time scaled by how close the phrase/energy
        analysis thinks we are to a transition. Falls back to remaining time.
        """
        if remaining is None:
            return None
        if score <= 0:
            return remaining
        # Blend: high transition score => transition imminent.
        return max(0, int(remaining * (1.0 - score * 0.5)))

    def _safe_status(self) -> dict[str, Any]:
        try:
            return self._status_provider() or {}
        except Exception:
            return {}
