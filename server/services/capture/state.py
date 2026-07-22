"""Persistent capture state – JSON-backed resume support."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class CaptureState:
    """JSON-backed state so the pipeline can resume after interruption."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                LOGGER.warning("Corrupt capture state – starting fresh")
        return {"version": 1, "releases": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data["last_updated"] = datetime.now(timezone.utc).isoformat()
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    # -- queries ---------------------------------------------------------

    def is_complete(self, release_id: int) -> bool:
        entry = self._data["releases"].get(str(release_id))
        return bool(entry and entry.get("status") == "complete")

    def last_track(self, release_id: int) -> int:
        entry = self._data["releases"].get(str(release_id))
        if entry and entry.get("status") == "partial":
            # Prefer the contiguous captured prefix when per-track data exists
            if "captured_tracks" in entry:
                return self._contiguous_prefix(set(entry.get("captured_tracks", [])))
            return entry.get("last_track", 0)
        return 0

    def captured_tracks(self, release_id: int) -> set[int]:
        """Set of individual track positions captured for a release."""
        entry = self._data["releases"].get(str(release_id))
        if not entry:
            return set()
        return set(entry.get("captured_tracks", []))

    @staticmethod
    def _contiguous_prefix(captured: set[int]) -> int:
        """Highest n such that tracks 1..n are all captured."""
        n = 0
        while (n + 1) in captured:
            n += 1
        return n

    def has_unfinished(self) -> bool:
        """True if any release is in 'partial' state (interrupted session)."""
        return any(
            r.get("status") == "partial"
            for r in self._data["releases"].values()
        )

    def summary(self) -> dict:
        """Return aggregate counts for progress reporting."""
        releases = self._data["releases"]
        return {
            "total": len(releases),
            "complete": sum(1 for r in releases.values() if r.get("status") == "complete"),
            "partial": sum(1 for r in releases.values() if r.get("status") == "partial"),
            "error": sum(1 for r in releases.values() if r.get("status") == "error"),
        }

    # -- mutations -------------------------------------------------------

    def mark_partial(self, release_id: int, last_track: int, expected: int) -> None:
        self._data["releases"][str(release_id)] = {
            "status": "partial",
            "last_track": last_track,
            "tracks_expected": expected,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()

    def mark_track_captured(self, release_id: int, track_position: int, expected: int) -> None:
        """Record that a single track was captured (single-track mode).

        Accumulates individual track positions so batch recording can skip
        tracks that were already captured live.
        """
        key = str(release_id)
        entry = self._data["releases"].get(key)
        if not entry or entry.get("status") not in ("partial", "complete"):
            entry = {"status": "partial", "tracks_expected": expected}
        captured = set(entry.get("captured_tracks", []))
        captured.add(track_position)
        entry["captured_tracks"] = sorted(captured)
        entry["last_track"] = max(entry.get("last_track", 0), track_position)
        entry["tracks_expected"] = expected
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Promote to complete once every expected track is captured
        if expected and len(captured) >= expected:
            entry["status"] = "complete"
            entry["tracks_captured"] = len(captured)
            entry["completed_at"] = datetime.now(timezone.utc).isoformat()
        else:
            entry["status"] = "partial"
        self._data["releases"][key] = entry
        self.save()

    def mark_complete(self, release_id: int, tracks_captured: int) -> None:
        key = str(release_id)
        existing = self._data["releases"].get(key, {})
        # Preserve per-track data captured by single-track mode
        captured = set(existing.get("captured_tracks", []))
        captured.update(range(1, tracks_captured + 1))
        self._data["releases"][key] = {
            "status": "complete",
            "tracks_captured": max(tracks_captured, len(captured)),
            "captured_tracks": sorted(captured),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()

    def mark_error(self, release_id: int, error: str) -> None:
        self._data["releases"][str(release_id)] = {
            "status": "error",
            "error": error,
            "error_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()
