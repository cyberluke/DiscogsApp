from collections import defaultdict
import re
from typing import Any, Iterable, Mapping


def normalize(value: Any) -> str:
    return str(value or '').strip().lower()


class MetadataIndexes:
    def __init__(self, releases: Iterable[Mapping[str, Any]]):
        self.releases = list(releases)
        self.artist = defaultdict(set)
        self.album = defaultdict(set)
        self.track = defaultdict(set)
        self.search = defaultdict(set)
        self.genre = defaultdict(set)
        self.style = defaultdict(set)
        self.year = defaultdict(set)
        self.label = defaultdict(set)
        self.deck = defaultdict(set)
        self.cd_position = defaultdict(set)
        self.favourites = set()
        self._build()

    def _build(self):
        for index, release in enumerate(self.releases):
            self._index_release(index, release)

    def _index_release(self, index: int, release: Mapping[str, Any]):
        self._add(self.album, release.get('title'), index)
        self._add_search_terms(release.get('title'), index)
        self._add(self.year, release.get('year'), index)
        self._add(self.deck, release.get('deck_number'), index)
        self._add(self.cd_position, release.get('cd_position'), index)
        self._index_release_artists(index, release)

        for genre in release.get('genres') or []:
            self._add(self.genre, genre, index)

        for style in release.get('styles') or []:
            self._add(self.style, style, index)

        for label in release.get('labels') or []:
            self._add(self.label, label.get('name'), index)

        for track in release.get('tracklist') or []:
            self._index_track(index, track)

    def _index_release_artists(self, index: int, release: Mapping[str, Any]):
        self._add(self.artist, release.get('artists_sort'), index)
        self._add_search_terms(release.get('artists_sort'), index)

        for artist in release.get('artists') or []:
            self._add(self.artist, artist.get('name'), index)
            self._add(self.artist, artist.get('anv'), index)
            self._add_search_terms(artist.get('name'), index)
            self._add_search_terms(artist.get('anv'), index)

    def _index_track(self, index: int, track: Mapping[str, Any]):
        if track.get('_score', 0) >= 1:
            self.favourites.add(index)

        self._add(self.track, track.get('title'), index)
        self._add(self.artist, track.get('artist'), index)
        self._add_search_terms(track.get('title'), index)
        self._add_search_terms(track.get('artist'), index)

        for artist in track.get('artists') or []:
            self._add(self.artist, artist.get('name'), index)
            self._add_search_terms(artist.get('name'), index)

    def _add(self, target: defaultdict[str, set[int]], value: Any, index: int):
        key = normalize(value)
        if key:
            target[key].add(index)

    def _add_search_terms(self, value: Any, index: int):
        key = normalize(value)
        if not key:
            return

        self.search[key].add(index)
        for token in re.findall(r'\w+', key):
            self.search[token].add(index)
