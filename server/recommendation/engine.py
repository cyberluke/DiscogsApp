from typing import Any, Mapping

try:
    from recommendation.index_builder import MetadataIndexes, normalize
except ImportError:
    from server.recommendation.index_builder import MetadataIndexes, normalize


class RecommendationEngine:
    def __init__(self, releases):
        self.indexes = MetadataIndexes(releases)

    def search(self, query: Mapping[str, Any]) -> list[dict[str, Any]]:
        matching_indexes = self._matching_indexes(query)
        limit = int(query.get('limit') or 50)
        return [self._summarize(self.indexes.releases[index]) for index in sorted(matching_indexes)[:limit]]

    def _matching_indexes(self, query: Mapping[str, Any]) -> set[int]:
        all_indexes = set(range(len(self.indexes.releases)))
        filters = []

        self._append_q_filter(filters, query.get('q'))
        self._append_filter(filters, self.indexes.artist, query.get('artist'))
        self._append_filter(filters, self.indexes.album, query.get('album') or query.get('release'))
        self._append_filter(filters, self.indexes.genre, query.get('genre'))
        self._append_filter(filters, self.indexes.style, query.get('style'))
        self._append_filter(filters, self.indexes.year, query.get('year'))
        self._append_filter(filters, self.indexes.label, query.get('label'))
        self._append_filter(filters, self.indexes.deck, query.get('deck'))
        self._append_filter(filters, self.indexes.cd_position, query.get('cd_position'))

        if str(query.get('favourites', '')).lower() in ('1', 'true', 'yes'):
            filters.append(set(self.indexes.favourites))

        if not filters:
            return all_indexes

        matching = filters[0]
        for filter_set in filters[1:]:
            matching = matching.intersection(filter_set)
        return matching

    def _append_filter(self, filters: list[set[int]], index: Mapping[str, set[int]], value: Any):
        key = normalize(value)
        if key:
            filters.append(set(index.get(key, set())))

    def _append_q_filter(self, filters: list[set[int]], value: Any):
        key = normalize(value)
        if not key:
            return

        matches = set(self.indexes.search.get(key, set()))
        matches.update(self.indexes.artist.get(key, set()))
        matches.update(self.indexes.album.get(key, set()))
        matches.update(self.indexes.track.get(key, set()))
        filters.append(matches)

    def _summarize(self, release: Mapping[str, Any]) -> dict[str, Any]:
        release_id = release.get('release_id') or release.get('id')
        artist_name = release.get('artists_sort')
        return {
            'id': release.get('id'),
            'release_id': release_id,
            'title': release.get('title'),
            'artists_sort': artist_name,
            'year': release.get('year'),
            'genres': release.get('genres') or [],
            'styles': release.get('styles') or [],
            'labels': release.get('labels') or [],
            'deck_number': release.get('deck_number'),
            'cd_position': release.get('cd_position'),
            'images': release.get('images') or [],
            'tracklist': [self._summarize_track(release, track) for track in release.get('tracklist') or []],
        }

    def _summarize_track(self, release: Mapping[str, Any], track: Mapping[str, Any]) -> dict[str, Any]:
        artist_name = release.get('artists_sort')
        if artist_name == 'Various' and track.get('artists'):
            artist_name = track['artists'][0].get('name', 'Unknown Artist')

        summarized_track = dict(track)
        summarized_track['release_id'] = release.get('release_id') or release.get('id')
        summarized_track['deck_number'] = release.get('deck_number')
        summarized_track['cd_position'] = release.get('cd_position')
        summarized_track['artist'] = artist_name
        summarized_track['full_name'] = f"{artist_name} - {track.get('title', '')}"
        summarized_track['album_title'] = release.get('title')
        summarized_track['artwork_url'] = self._primary_image_url(release)
        return summarized_track

    def _primary_image_url(self, release: Mapping[str, Any]) -> str | None:
        images = release.get('images') or []
        image = next((item for item in images if item.get('type') == 'primary'), None)
        if image is None:
            image = next((item for item in images if item.get('type') == 'secondary'), None)
        if image is None and images:
            image = images[0]
        if image is None:
            return None
        return image.get('primary_image') or image.get('uri')