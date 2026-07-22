"""Persistent store for Spotify audio features in a dedicated JSON file."""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PATH = os.path.join('server', 'spotify_audio_features.json')


class SpotifyStore:
    """Reads/writes spotify_audio_features.json keyed by release_id."""

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = path
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as fh:
                    self._data = json.load(fh)
                logger.info('Loaded %d Spotify entries from %s', len(self._data), self.path)
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning('Failed to load Spotify store: %s', exc)
                self._data = {}
        else:
            self._data = {}

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=1)

    def has_release(self, release_id: str | int) -> bool:
        return str(release_id) in self._data

    def get_release(self, release_id: str | int) -> dict[str, Any] | None:
        return self._data.get(str(release_id))

    def set_release(self, release_id: str | int, entry: dict[str, Any]) -> None:
        self._data[str(release_id)] = entry

    def all_entries(self) -> dict[str, Any]:
        return self._data

    def count(self) -> int:
        return len(self._data)
