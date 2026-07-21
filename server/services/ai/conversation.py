from collections import Counter
import json
import re
import unicodedata
from typing import Any, Mapping


class ConversationContextBuilder:
    def __init__(self, repository, playback_runtime):
        self.repository = repository
        self.playback_runtime = playback_runtime

    def build(self) -> dict[str, Any]:
        playback = self.playback_runtime.status()
        current_track = playback.get('current_track')
        current_release = self._current_release(current_track)
        releases = self.repository.all_releases()
        return {
            'now_playing': playback,
            'current_release': self._release_summary(current_release) if current_release else None,
            'current_track': current_track,
            'current_playlist': playback.get('current_playlist'),
            'saved_playlists': self._playlist_summaries(),
            'recent_history': self._recent_history(playback),
            'collection': self._collection_statistics(releases),
        }

    def _playlist_summaries(self) -> list[dict[str, Any]]:
        if not hasattr(self.repository, 'all_playlists'):
            return []
        playlists = list(self.repository.all_playlists())
        if hasattr(self.repository, 'favourite_tracks_playlist'):
            playlists.append(self.repository.favourite_tracks_playlist())
        return [
            {'name': playlist.get('name'), 'track_count': len(playlist.get('tracks') or [])}
            for playlist in playlists
            if isinstance(playlist, Mapping) and playlist.get('name')
        ][:50]

    def _recent_history(self, playback: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        for key in ('recent_history', 'recent_tracks', 'history'):
            value = playback.get(key)
            if isinstance(value, list):
                return [track for track in value if isinstance(track, Mapping)][-10:]
        return []

    def _current_release(self, current_track: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not current_track:
            return None
        release_id = current_track.get('release_id')
        if release_id is None:
            return None
        try:
            return self.repository.get_release_by_id(int(release_id))
        except (TypeError, ValueError):
            return None

    def _collection_statistics(self, releases: list[Mapping[str, Any]]) -> dict[str, Any]:
        labels = Counter()
        countries = Counter()
        years = Counter()
        ai_enriched = 0
        track_count = 0

        for release in releases:
            track_count += len(release.get('tracklist') or [])
            if isinstance(release.get('ai'), dict):
                ai_enriched += 1
            country = release.get('country')
            year = release.get('year')
            if country:
                countries[str(country)] += 1
            if year:
                years[str(year)] += 1
            for label in release.get('labels') or []:
                name = label.get('name') if isinstance(label, dict) else label
                if name:
                    labels[str(name)] += 1

        return {
            'release_count': len(releases),
            'track_count': track_count,
            'ai_enriched_release_count': ai_enriched,
            'top_labels': self._counter_items(labels),
            'top_countries': self._counter_items(countries),
            'top_years': self._counter_items(years),
        }

    def _counter_items(self, counter: Counter) -> list[dict[str, Any]]:
        return [{'name': name, 'count': count} for name, count in counter.most_common(10)]

    def _release_summary(self, release: Mapping[str, Any]) -> dict[str, Any]:
        return {
            'id': release.get('id'),
            'release_id': release.get('release_id'),
            'title': release.get('title'),
            'artists_sort': release.get('artists_sort'),
            'year': release.get('year'),
            'country': release.get('country'),
            'genres': release.get('genres') or [],
            'styles': release.get('styles') or [],
            'deck_number': release.get('deck_number'),
            'cd_position': release.get('cd_position'),
            'ai': release.get('ai'),
        }


class IntentAnalyzer:
    def parse(self, request_text: str) -> dict[str, Any]:
        text = (request_text or '').strip().lower()
        intents = set()
        keywords = set()

        mapping = {
            'similar': ('similar',),
            'vibe': ('similar',),
            'continue': ('similar',),
            'harder': ('harder', 'energy'),
            'energetic': ('energy',),
            'faster': ('energy',),
            'less cheesy': ('less_cheesy',),
            'cheesy': ('guilty_pleasure',),
            'guilty pleasure': ('guilty_pleasure',),
            'underground': ('underground',),
            'less commercial': ('underground',),
            'melodic': ('melodic',),
            'emotional': ('emotional',),
            'night driving': ('night_driving',),
            'driving': ('night_driving',),
            'workout': ('workout', 'energy'),
            'surprise': ('surprise',),
            'hidden gem': ('hidden_gem',),
            'forgotten classic': ('forgotten_classic',),
            'female vocal': ('female_vocals',),
            'female vocals': ('female_vocals',),
            'proper eurodance': ('style', 'dj_eurodance'),
            'dj eurodance': ('style', 'dj_eurodance'),
            'club eurodance': ('style', 'dj_eurodance'),
            'rave-pop': ('style', 'dj_eurodance'),
            'poradny eurodance': ('style', 'dj_eurodance'),
            'pořádný eurodance': ('style', 'dj_eurodance'),
            'tancni eurodance': ('style', 'dj_eurodance'),
            'taneční eurodance': ('style', 'dj_eurodance'),
            'euro house': ('style',),
            'dance-pop': ('style',),
            'dance pop': ('style',),
            'hard trance': ('style',),
            'vocal trance': ('style',),
            'trance': ('style',),
            'house': ('style',),
            'eurodance': ('style', 'dj_eurodance'),
            'germany': ('country',),
            'german': ('country',),
        }
        for phrase, phrase_intents in mapping.items():
            if phrase in text:
                intents.update(phrase_intents)
                keywords.add(phrase)

        if not intents:
            intents.add('similar' if text else 'surprise')

        return {'text': text, 'intents': intents, 'keywords': keywords}


class RecommendationParser(IntentAnalyzer):
    pass


class CandidateDiversifier:
    QUOTAS = {
        'similar': 0.4,
        'adjacent': 0.2,
        'unexpected': 0.2,
        'hidden_gem': 0.2,
    }

    def select(self, scored: list[tuple[float, str, Mapping[str, Any], Mapping[str, Any], list[str], list[str]]], limit: int) -> list[tuple[float, str, Mapping[str, Any], Mapping[str, Any], list[str], list[str]]]:
        if limit <= 0:
            return []
        buckets = {name: [] for name in self.QUOTAS}
        for item in scored:
            buckets.setdefault(item[1], []).append(item)

        selected = []
        used = set()
        for group, quota in self.QUOTAS.items():
            group_limit = max(1, round(limit * quota))
            for item in buckets.get(group, [])[:group_limit]:
                selected.append(item)
                used.add(self._key(item))

        for item in scored:
            if len(selected) >= limit:
                break
            key = self._key(item)
            if key in used:
                continue
            selected.append(item)
            used.add(key)
        return selected[:limit]

    def _key(self, item: tuple[float, str, Mapping[str, Any], Mapping[str, Any], list[str], list[str]]) -> tuple[Any, Any]:
        release = item[2]
        track = item[3]
        return (release.get('release_id') or release.get('id'), track.get('position') or track.get('title'))


class MusicRecommendationService:
    SCORE_FIELDS = ('energy', 'danceability', 'euphoria', 'nostalgia', 'commercial', 'club', 'radio', 'cheese')
    PRODUCTION_SCORE_FIELDS = (
        'energy', 'drive', 'groove', 'rhythm_complexity', 'rap_presence', 'vocal_balance',
        'harmony_density', 'dynamic_range', 'production_density', 'commercial_polish',
        'club_focus', 'radio_focus', 'emotional_intensity'
    )
    SONGWRITING_SCORE_FIELDS = ('hook_strength', 'chorus_focus', 'verse_focus', 'instrumental_focus', 'build_up', 'breakdown')
    PRODUCTION_TEXT_FIELDS = ('percussion_style', 'bass_style', 'synth_style', 'vocal_style', 'atmosphere')
    DJ_EURODANCE_TOKENS = (
        'eurodance', 'club mix', 'hard mix', 'extended', 'rave-pop', 'rave pop',
        'dancefloor', 'dj-friendly', 'dj friendly', 'club', 'anthem', 'four-on-the-floor',
        'four on the floor', 'high-energy', 'high energy', 'german', 'dutch', 'italo',
    )
    NON_EURODANCE_STYLES = {'euro house', 'dance-pop', 'dance pop'}
    SOFT_EURODANCE_TOKENS = ('radio pop', 'ballad', 'downtempo', 'soft')

    def __init__(self, repository, parser: IntentAnalyzer | None = None, diversifier: CandidateDiversifier | None = None):
        self.repository = repository
        self.parser = parser or IntentAnalyzer()
        self.diversifier = diversifier or CandidateDiversifier()

    def recommend(self, request_text: str, playback: Mapping[str, Any] | None = None, limit: int = 5) -> list[dict[str, Any]]:
        return self.search_candidates(request_text, playback, limit=limit)

    def search_candidates(self, request_text: str, playback: Mapping[str, Any] | None = None, limit: int = 100) -> list[dict[str, Any]]:
        playback = playback or {}
        limit = max(1, min(150, int(limit or 100)))
        parsed_request = self.parser.parse(request_text)
        current_track = playback.get('current_track')
        current_release = self._current_release(current_track)
        scored = []

        for release in self.repository.all_releases():
            if self._same_release(release, current_release):
                continue
            track = self._representative_track(release, parsed_request)
            if not track:
                continue
            score, shared, differs = self._score_release(release, current_release, parsed_request)
            if score <= 0:
                continue
            scored.append((score, self._candidate_group(score, release, current_release, shared, differs), release, track, shared, differs))

        scored.sort(key=lambda item: item[0], reverse=True)
        diversified = self.diversifier.select(scored, limit)
        return [
            self._recommendation_payload(score, release, track, shared, differs, group)
            for score, group, release, track, shared, differs in diversified
        ]

    def _candidate_group(
        self,
        score: float,
        release: Mapping[str, Any],
        current_release: Mapping[str, Any] | None,
        shared: list[str],
        differs: list[str],
    ) -> str:
        ai = release.get('ai') if isinstance(release.get('ai'), dict) else {}
        if ai and (ai.get('hidden_gem') or self._hidden_gem_score(release, ai) >= 38):
            return 'hidden_gem'
        if current_release and shared and score >= 65:
            return 'similar'
        if differs:
            return 'adjacent'
        return 'unexpected'

    def _score_release(
        self,
        release: Mapping[str, Any],
        current_release: Mapping[str, Any] | None,
        parsed_request: Mapping[str, Any],
    ) -> tuple[float, list[str], list[str]]:
        intents = parsed_request.get('intents') or set()
        keywords = parsed_request.get('keywords') or set()
        ai = release.get('ai') if isinstance(release.get('ai'), dict) else {}
        current_ai = current_release.get('ai') if current_release and isinstance(current_release.get('ai'), dict) else {}
        text = self._search_text(release, ai)
        score = 10.0
        shared = []
        differs = []

        if 'similar' in intents and current_release:
            score += self._similarity_score(release, current_release, shared)
        for keyword in keywords:
            if keyword in text:
                score += 25
                shared.append(keyword)

        if 'style' in intents:
            for keyword in keywords:
                if keyword in text:
                    score += 30
        if 'dj_eurodance' in intents:
            eurodance_score = self._dj_eurodance_score(release, ai, text)
            score += eurodance_score
            if eurodance_score >= 35:
                shared.append('DJ-friendly 90s Eurodance club energy')
        if 'country' in intents and any(keyword in text for keyword in ('germany', 'german')):
            score += 25
            shared.append('German collection context')
        if 'energy' in intents:
            score += self._score_value(ai, 'energy') * 0.25
        if 'harder' in intents and current_ai:
            delta = self._score_value(ai, 'energy') - self._score_value(current_ai, 'energy')
            score += max(0, delta) * 0.7
            differs.append('more forceful energy')
        if 'less_cheesy' in intents:
            score += max(0, 100 - self._score_value(ai, 'cheese')) * 0.35
            differs.append('less kitsch')
        if 'underground' in intents:
            score += max(0, 100 - self._score_value(ai, 'commercial')) * 0.3
            differs.append('less commercial profile')
        if 'night_driving' in intents:
            score += 30 if ai.get('driving_music') or ai.get('late_night') else 0
            score += self._list_match(ai, ('mood', 'keywords'), ('night', 'driving', 'late')) * 12
            shared.append('night drive mood')
        if 'workout' in intents:
            score += self._score_value(ai, 'energy') * 0.2 + self._score_value(ai, 'danceability') * 0.15
        if 'guilty_pleasure' in intents:
            score += 45 if ai.get('guilty_pleasure') else self._score_value(ai, 'cheese') * 0.2
        if 'hidden_gem' in intents:
            score += self._hidden_gem_score(release, ai)
            differs.append('collection sleeper pick')
        if 'forgotten_classic' in intents:
            score += self._score_value(ai, 'nostalgia') * 0.3
            if self._release_year(release) and self._release_year(release) <= 2005:
                score += 20
            shared.append('nostalgic catalogue energy')
        if 'female_vocals' in intents and any(token in text for token in ('feat.', 'featuring', 'vocal', 'female', 'diva')):
            score += 20
            shared.append('vocal-forward dance track')
        if 'melodic' in intents:
            score += self._list_match(ai, ('mood', 'keywords', 'summary'), ('melodic', 'euphoric', 'anthem')) * 14
        if 'emotional' in intents:
            score += self._score_value(ai, 'euphoria') * 0.15 + self._score_value(ai, 'nostalgia') * 0.12

        if ai:
            score += 8
        if not shared:
            shared.extend(self._shared_metadata(release, current_release))
        if not differs:
            differs.extend(self._different_metadata(release, current_release))
        return score, shared[:5], differs[:5]

    def _recommendation_payload(
        self,
        score: float,
        release: Mapping[str, Any],
        track: Mapping[str, Any],
        shared: list[str],
        differs: list[str],
        group: str = 'similar',
    ) -> dict[str, Any]:
        confidence = max(1, min(100, round(score)))
        track_payload = self._track_payload(release, track)
        release_payload = self._release_payload(release)
        reason = self._reason(release, track_payload, shared, differs)
        return {
            'track': track_payload,
            'release': release_payload,
            'reason': reason,
            'confidence': confidence,
            'candidate_group': group,
            'local_score': round(score, 2),
            'musical_dna': {
                'shared': shared,
                'differs': differs,
            },
            'actions': [
                {'type': 'play', 'label': 'Play'},
                {'type': 'queue_next', 'label': 'Queue Next'},
                {'type': 'open_release', 'label': 'Open Release'},
                {'type': 'explain', 'label': 'Explain'},
            ],
        }

    def _reason(self, release: Mapping[str, Any], track: Mapping[str, Any], shared: list[str], differs: list[str]) -> str:
        ai = release.get('ai') if isinstance(release.get('ai'), dict) else {}
        if ai.get('summary'):
            return ai['summary']
        details = ', '.join(shared or differs or release.get('styles') or release.get('genres') or ['local collection fit'])
        return f"{track.get('artist')} - {track.get('title')} fits because of {details}."

    def _track_payload(self, release: Mapping[str, Any], track: Mapping[str, Any]) -> dict[str, Any]:
        artist = release.get('artists_sort')
        if artist == 'Various' and track.get('artists'):
            artist = track['artists'][0].get('name', 'Unknown Artist')
        payload = dict(track)
        payload['release_id'] = release.get('release_id') or release.get('id')
        payload['deck_number'] = release.get('deck_number')
        payload['cd_position'] = release.get('cd_position')
        payload['artist'] = artist or 'Unknown Artist'
        payload['full_name'] = f"{payload['artist']} - {track.get('title', '')}"
        payload['album_title'] = release.get('title')
        payload['artwork_url'] = self._primary_image_url(release)
        return payload

    def _release_payload(self, release: Mapping[str, Any]) -> dict[str, Any]:
        return {
            'id': release.get('id'),
            'release_id': release.get('release_id') or release.get('id'),
            'title': release.get('title'),
            'artists_sort': release.get('artists_sort'),
            'year': release.get('year'),
            'country': release.get('country'),
            'genres': release.get('genres') or [],
            'styles': release.get('styles') or [],
            'deck_number': release.get('deck_number'),
            'cd_position': release.get('cd_position'),
            'images': release.get('images') or [],
            'ai': release.get('ai'),
        }

    def _representative_track(self, release: Mapping[str, Any], parsed_request: Mapping[str, Any]) -> Mapping[str, Any] | None:
        tracks = [track for track in release.get('tracklist') or [] if track.get('title')]
        if not tracks:
            return None
        if 'guilty_pleasure' in parsed_request.get('intents', set()):
            favourite = next((track for track in tracks if track.get('_score', 0) >= 1), None)
            if favourite:
                return favourite
        return tracks[0]

    def _current_release(self, current_track: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not current_track or current_track.get('release_id') is None:
            return None
        try:
            return self.repository.get_release_by_id(int(current_track.get('release_id')))
        except (TypeError, ValueError):
            return None

    def _same_release(self, release: Mapping[str, Any], current_release: Mapping[str, Any] | None) -> bool:
        if not current_release:
            return False
        return (release.get('release_id') or release.get('id')) == (current_release.get('release_id') or current_release.get('id'))

    def _similarity_score(self, release: Mapping[str, Any], current_release: Mapping[str, Any], shared: list[str]) -> float:
        score = 0.0
        ai = release.get('ai') if isinstance(release.get('ai'), dict) else {}
        current_ai = current_release.get('ai') if isinstance(current_release.get('ai'), dict) else {}
        if ai and current_ai:
            score += self._production_similarity_score(ai, current_ai, shared)
            for field in self.SCORE_FIELDS:
                distance = abs(self._score_value(ai, field) - self._score_value(current_ai, field))
                score += max(0, 5 - distance / 12)
            overlap = set(self._lower_list(ai.get('keywords'))).intersection(self._lower_list(current_ai.get('keywords')))
            if overlap:
                score += len(overlap) * 6
                shared.extend(sorted(overlap))
        for field in ('genres', 'styles'):
            overlap = set(self._lower_list(release.get(field))).intersection(self._lower_list(current_release.get(field)))
            if overlap:
                score += len(overlap) * 6
                shared.extend(sorted(overlap))
        return score

    def _production_similarity_score(self, ai: Mapping[str, Any], current_ai: Mapping[str, Any], shared: list[str]) -> float:
        score = 0.0
        signature_overlap = set(self._lower_list(ai.get('production_signature'))).intersection(self._lower_list(current_ai.get('production_signature')))
        if signature_overlap:
            score += len(signature_overlap) * 34
            shared.extend(f'production signature: {signature}' for signature in sorted(signature_overlap))

        production = ai.get('production') if isinstance(ai.get('production'), Mapping) else {}
        current_production = current_ai.get('production') if isinstance(current_ai.get('production'), Mapping) else {}
        for field in self.PRODUCTION_SCORE_FIELDS:
            distance = abs(self._score_value(production, field) - self._score_value(current_production, field))
            score += max(0, 10 - distance / 6)

        songwriting = ai.get('songwriting') if isinstance(ai.get('songwriting'), Mapping) else {}
        current_songwriting = current_ai.get('songwriting') if isinstance(current_ai.get('songwriting'), Mapping) else {}
        for field in self.SONGWRITING_SCORE_FIELDS:
            distance = abs(self._score_value(songwriting, field) - self._score_value(current_songwriting, field))
            score += max(0, 6 - distance / 8)

        text_overlap = self._production_text_overlap(production, current_production)
        if text_overlap:
            score += len(text_overlap) * 10
            shared.extend(text_overlap)
        return score

    def _production_text_overlap(self, production: Mapping[str, Any], current_production: Mapping[str, Any]) -> list[str]:
        shared = []
        for field in self.PRODUCTION_TEXT_FIELDS:
            left = self._normalize_text(production.get(field))
            right = self._normalize_text(current_production.get(field))
            if left and right and (left in right or right in left):
                shared.append(f'{field.replace("_", " ")}: {production.get(field)}')
        return shared

    def _normalize_text(self, value: Any) -> str:
        return re.sub(r'\s+', ' ', str(value or '').strip().lower())

    def _shared_metadata(self, release: Mapping[str, Any], current_release: Mapping[str, Any] | None) -> list[str]:
        if not current_release:
            return self._lower_list(release.get('styles') or release.get('genres'))[:3]
        shared = []
        for field in ('styles', 'genres'):
            shared.extend(sorted(set(self._lower_list(release.get(field))).intersection(self._lower_list(current_release.get(field)))))
        return shared or self._lower_list(release.get('styles') or release.get('genres'))[:3]

    def _different_metadata(self, release: Mapping[str, Any], current_release: Mapping[str, Any] | None) -> list[str]:
        if not current_release:
            return []
        return sorted(set(self._lower_list(release.get('styles'))).difference(self._lower_list(current_release.get('styles'))))[:3]

    def _search_text(self, release: Mapping[str, Any], ai: Mapping[str, Any]) -> str:
        parts = [release.get('title'), release.get('artists_sort'), release.get('country'), ai.get('scene'), ai.get('summary')]
        parts.extend(release.get('genres') or [])
        parts.extend(release.get('styles') or [])
        for field in ('keywords', 'mood', 'recommended_after', 'similar_artists'):
            parts.extend(ai.get(field) or [])
        parts.extend(ai.get('production_signature') or [])
        production = ai.get('production') if isinstance(ai.get('production'), Mapping) else {}
        parts.extend(production.get(field) for field in self.PRODUCTION_TEXT_FIELDS)
        artist_context = ai.get('artist_context') if isinstance(ai.get('artist_context'), Mapping) else {}
        parts.extend(artist_context.values())
        return ' '.join(str(part) for part in parts if part).lower()

    def _dj_eurodance_score(self, release: Mapping[str, Any], ai: Mapping[str, Any], text: str) -> float:
        styles = set(self._lower_list(release.get('styles')))
        has_eurodance_base = 'eurodance' in styles
        if not has_eurodance_base or styles.intersection(self.NON_EURODANCE_STYLES):
            return 0.0
        score = 20.0
        score += self._score_value(ai, 'energy') * 0.22
        score += self._score_value(ai, 'danceability') * 0.22
        score += self._score_value(ai, 'club') * 0.18
        score += max(0, self._score_value(ai, 'club') - self._score_value(ai, 'radio')) * 0.2
        score += self._token_count(text, self.DJ_EURODANCE_TOKENS) * 8
        score -= self._token_count(text, self.SOFT_EURODANCE_TOKENS) * 10
        score -= max(0, self._score_value(ai, 'radio') - self._score_value(ai, 'club')) * 0.15
        return max(0.0, score)

    def _token_count(self, text: str, tokens: tuple[str, ...]) -> int:
        return sum(1 for token in tokens if token in text)

    def _list_match(self, ai: Mapping[str, Any], fields: tuple[str, ...], tokens: tuple[str, ...]) -> int:
        text = ' '.join(str(value) for field in fields for value in self._field_values(ai.get(field))).lower()
        return sum(1 for token in tokens if token in text)

    def _field_values(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value]
        if value:
            return [str(value)]
        return []

    def _score_value(self, ai: Mapping[str, Any], field: str) -> int:
        try:
            return max(0, min(100, int(ai.get(field) or 0)))
        except (TypeError, ValueError):
            return 0

    def _hidden_gem_score(self, release: Mapping[str, Any], ai: Mapping[str, Any]) -> float:
        rating = release.get('community', {}).get('rating', {}) if isinstance(release.get('community'), dict) else {}
        try:
            count = int(rating.get('count') or 0)
            average = float(rating.get('average') or 0)
        except (TypeError, ValueError):
            count = 0
            average = 0
        return max(0, 20 - count) + average * 8 + self._score_value(ai, 'nostalgia') * 0.1

    def _release_year(self, release: Mapping[str, Any]) -> int | None:
        try:
            return int(release.get('year'))
        except (TypeError, ValueError):
            return None

    def _lower_list(self, values: Any) -> list[str]:
        return [str(value).strip().lower() for value in values or [] if str(value).strip()]

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


class PlaylistActionService:
    def __init__(self, repository, playback_runtime):
        self.repository = repository
        self.playback_runtime = playback_runtime

    def play(self, track: Mapping[str, Any]) -> dict[str, Any]:
        return self.playback_runtime.play_track(track)

    def play_playlist(self, playlist: Mapping[str, Any]) -> dict[str, Any]:
        return self.playback_runtime.play_playlist(playlist)

    def transport(self, command: str) -> dict[str, Any]:
        commands = {
            'pause': self.playback_runtime.pause,
            'resume': self.playback_runtime.resume,
            'stop': self.playback_runtime.stop,
            'next': self.playback_runtime.next_track,
            'previous': self.playback_runtime.previous_track,
        }
        if command not in commands:
            raise ValueError(f'Unsupported playback command: {command}')
        return commands[command]()

    def save_playlist(self, playlist: dict[str, Any]) -> None:
        if not hasattr(self.repository, 'save_playlist'):
            raise RuntimeError('Playlist storage is unavailable')
        self.repository.save_playlist(playlist)

    def find_playlist(self, request_text: str) -> dict[str, Any] | None:
        normalized_request = self._normalize(request_text)
        if not normalized_request or not hasattr(self.repository, 'all_playlists'):
            return None
        if self._wants_favourite_tracks(normalized_request) and hasattr(self.repository, 'favourite_tracks_playlist'):
            return self.repository.favourite_tracks_playlist()
        exact = None
        contained = None
        for playlist in self.repository.all_playlists():
            if not isinstance(playlist, Mapping) or not playlist.get('name'):
                continue
            normalized_name = self._normalize(str(playlist.get('name')))
            if normalized_name == normalized_request:
                exact = playlist
                break
            if normalized_name and normalized_name in normalized_request:
                contained = playlist
        return exact or contained

    def analyze_playlist(self, playlist: Mapping[str, Any]) -> dict[str, Any]:
        tracks = [track for track in playlist.get('tracks') or [] if isinstance(track, Mapping)]
        releases = [self._release_for_track(track) for track in tracks]
        releases = [release for release in releases if release]
        styles = Counter(style for release in releases for style in release.get('styles') or [])
        genres = Counter(genre for release in releases for genre in release.get('genres') or [])
        countries = Counter(release.get('country') for release in releases if release.get('country'))
        years = [self._int_value(release.get('year')) for release in releases]
        years = [year for year in years if year]
        energy_values = [self._ai_score(release, 'energy') for release in releases]
        energy_values = [value for value in energy_values if value is not None]
        cheese_values = [self._ai_score(release, 'cheese') for release in releases]
        cheese_values = [value for value in cheese_values if value is not None]
        return {
            'name': playlist.get('name'),
            'track_count': len(tracks),
            'top_styles': self._counter_items(styles),
            'top_genres': self._counter_items(genres),
            'top_countries': self._counter_items(countries),
            'year_range': [min(years), max(years)] if years else None,
            'average_energy': round(sum(energy_values) / len(energy_values), 1) if energy_values else None,
            'average_cheese': round(sum(cheese_values) / len(cheese_values), 1) if cheese_values else None,
            'tracks': [self._compact_playlist_track(track) for track in tracks[:10]],
        }

    def _release_for_track(self, track: Mapping[str, Any]) -> dict[str, Any] | None:
        release_id = track.get('release_id')
        if release_id is None or not hasattr(self.repository, 'get_release_by_id'):
            return None
        try:
            return self.repository.get_release_by_id(int(release_id))
        except (TypeError, ValueError):
            return None

    def _compact_playlist_track(self, track: Mapping[str, Any]) -> dict[str, Any]:
        return {
            'artist': track.get('artist'),
            'title': track.get('title'),
            'full_name': track.get('full_name'),
            'release_id': track.get('release_id'),
            'position': track.get('position'),
        }

    def _counter_items(self, counter: Counter) -> list[dict[str, Any]]:
        return [{'name': name, 'count': count} for name, count in counter.most_common(5)]

    def _ai_score(self, release: Mapping[str, Any], field: str) -> int | None:
        ai = release.get('ai') if isinstance(release.get('ai'), Mapping) else {}
        value = self._int_value(ai.get(field))
        return max(0, min(100, value)) if value is not None else None

    def _int_value(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _normalize(self, value: str) -> str:
        ascii_value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        return re.sub(r'\s+', ' ', ascii_value.strip().lower())

    def _wants_favourite_tracks(self, normalized: str) -> bool:
        favourite_tokens = ('favourite', 'favorite', 'obliben', 'oblub', 'fav')
        track_tokens = ('track', 'tracks', 'skladb', 'pisn', 'song')
        return any(token in normalized for token in favourite_tokens) and any(token in normalized for token in track_tokens)


class PromptBuilder:
    EURO_HOUSE = 'Euro House'
    VOCAL_TRANCE = 'Vocal Trance'
    COMMERCIAL_RAVE = 'Commercial Rave'
    SCOOTER_STYLE_PRIORITY = ('Hard Trance', 'Happy Hardcore', 'Hard House', 'Trance', 'Techno', 'Hands Up', EURO_HOUSE)
    STYLE_PRIORITY = (VOCAL_TRANCE, EURO_HOUSE, 'Hard Trance', 'Progressive Trance', 'Hard House', 'Happy Hardcore', 'Hands Up', 'Techno', 'House', 'Trance')
    GENERIC_STYLE_LABELS = {'eurodance', 'dance-pop', 'ambient'}

    def build(self, message: str, payload: Mapping[str, Any], context: Mapping[str, Any], candidates: list[dict[str, Any]]) -> tuple[str, str]:
        system_prompt = (
            'You are AI DJ inside a Discogs CD collection app. You are an experienced European dance music collector and DJ, '
            'specialized in roughly 1988-2010 dance music. The local recommendation pipeline has already searched the collection. '
            'You curate from the supplied candidate list only. Never invent tracks, never mention external services, and never perform internet lookup. '
            'Recognize playlist momentum and explain transitions like a practical DJ. You can discuss saved playlists, recommend playlist creation, '
            'and suggest CD player actions, but executable playlist and transport commands are handled by the application API. '
            'When the user asks for Eurodance, keep Eurodance narrow: do not merge Euro House or Dance-pop into it. Prefer true high-energy 90s Eurodance with club/extended/hard mixes, strong four-on-the-floor drive, and dancefloor utility. '
            'Use precise dance-music taxonomy: do not call vocal trance, Euro House, hard trance, hard house, hands-up, happy hardcore, techno, or commercial rave "Eurodance" unless the candidate primaryStyle is Eurodance. '
            'Respect candidate primaryStyle and Discogs styles; Lasgo is vocal trance, Le Click - Call Me is Euro House, and Scooter should be described by its actual rave/trance/hard-house/happy-hardcore context. Return JSON only.'
        )
        user_prompt = json.dumps({
            'task': 'Choose 6-10 recommendations from the local candidate tracks and answer the user as AI DJ.',
            'rules': [
                'Use only candidate_id values from candidate_tracks.',
                'Do not search beyond candidate_tracks.',
                'If no candidate fits, return an empty suggested_tracks list and say so clearly.',
                'Explain confidence, transition fit, shared production DNA, and what changes from the current track.',
                'Notice collection and playlist patterns when they are musically relevant.',
                'Prioritize production signature, groove, energy flow, arrangement, mixability, dance floor impact, and production philosophy over artist name similarity.',
                'Do not assume two tracks by the same artist are similar; compare their production eras and production metadata independently.',
                'Use DJ/producer language rather than consumer mood language.',
                'Use candidate primaryStyle as the main style label; do not flatten precise styles into Eurodance.',
                'Treat Eurodance, Euro House, Dance-pop, vocal trance, hard trance, hands-up, and commercial rave as separate selectable lanes.',
                'For Eurodance requests, favor true DJ-useful 90s Eurodance club, extended, and hard mixes; for Euro House or Dance-pop requests, choose those labels explicitly instead.',
            ],
            'response_schema': {
                'response': 'string',
                'suggested_tracks': [
                    {
                        'candidate_id': 'string',
                        'reason': 'string',
                        'confidence': 'integer 1-100',
                        'transition': 'string',
                        'alternative_candidate_id': 'string optional',
                        'musical_dna': {
                            'shared': ['string'],
                            'differs': ['string'],
                        },
                    }
                ],
            },
            'user_request': message,
            'conversation': payload.get('conversation') or payload.get('messages') or [],
            'context': self._ai_context(context),
            'candidate_count': len(candidates),
            'candidate_tracks': [self.compact_candidate(candidate) for candidate in candidates],
        }, ensure_ascii=False)
        return system_prompt, user_prompt

    def _ai_context(self, context: Mapping[str, Any]) -> dict[str, Any]:
        now_playing = context.get('now_playing') or {}
        return {
            'current_track': self._compact_track(context.get('current_track') or {}),
            'current_release': self._compact_release(context.get('current_release') or {}),
            'current_playlist': context.get('current_playlist'),
            'saved_playlists': context.get('saved_playlists') or [],
            'recent_history': [self._compact_track(track) for track in (context.get('recent_history') or [])[-10:]],
            'playback': {
                'state': now_playing.get('playback_state'),
                'deck': now_playing.get('current_deck'),
                'cd': now_playing.get('current_cd'),
                'progress': now_playing.get('progress'),
            },
            'collection': context.get('collection'),
        }

    def compact_candidate(self, candidate: Mapping[str, Any]) -> dict[str, Any]:
        release = candidate.get('release') or {}
        track = candidate.get('track') or {}
        ai = release.get('ai') if isinstance(release.get('ai'), dict) else {}
        return {
            'candidate_id': self.candidate_id(candidate),
            'artist': track.get('artist') or release.get('artists_sort'),
            'track': track.get('title'),
            'position': track.get('position'),
            'duration': track.get('duration'),
            'year': release.get('year'),
            'country': release.get('country'),
            'genres': release.get('genres') or [],
            'styles': release.get('styles') or [],
            'primaryStyle': self._primary_style(release, track),
            'scene': ai.get('scene'),
            'summary': ai.get('summary'),
            'energy': ai.get('energy'),
            'danceability': ai.get('danceability'),
            'euphoria': ai.get('euphoria'),
            'commercial': ai.get('commercial'),
            'club': ai.get('club'),
            'radio': ai.get('radio'),
            'cheese': ai.get('cheese'),
            'guiltyPleasure': ai.get('guilty_pleasure'),
            'drivingMusic': ai.get('driving_music'),
            'festival': ai.get('festival'),
            'keywords': ai.get('keywords') or [],
            'production': ai.get('production') or {},
            'productionSignature': ai.get('production_signature') or [],
            'songwriting': ai.get('songwriting') or {},
            'artistContext': ai.get('artist_context') or {},
            'mood': ai.get('mood') or [],
            'similarArtists': ai.get('similar_artists') or [],
            'localGroup': candidate.get('candidate_group'),
            'localScore': candidate.get('local_score'),
            'localConfidence': candidate.get('confidence'),
            'localReason': candidate.get('reason'),
        }

    def _compact_release(self, release: Mapping[str, Any]) -> dict[str, Any] | None:
        if not release:
            return None
        ai = release.get('ai') if isinstance(release.get('ai'), dict) else {}
        return {
            'id': release.get('release_id') or release.get('id'),
            'artist': release.get('artists_sort'),
            'title': release.get('title'),
            'year': release.get('year'),
            'country': release.get('country'),
            'genres': release.get('genres') or [],
            'styles': release.get('styles') or [],
            'scene': ai.get('scene'),
            'summary': ai.get('summary'),
            'energy': ai.get('energy'),
            'danceability': ai.get('danceability'),
            'euphoria': ai.get('euphoria'),
            'commercial': ai.get('commercial'),
            'club': ai.get('club'),
            'radio': ai.get('radio'),
            'cheese': ai.get('cheese'),
            'keywords': ai.get('keywords') or [],
            'production': ai.get('production') or {},
            'productionSignature': ai.get('production_signature') or [],
            'songwriting': ai.get('songwriting') or {},
            'artistContext': ai.get('artist_context') or {},
            'mood': ai.get('mood') or [],
        }

    def _compact_track(self, track: Mapping[str, Any]) -> dict[str, Any] | None:
        if not track:
            return None
        return {
            'artist': track.get('artist'),
            'track': track.get('title'),
            'fullName': track.get('full_name'),
            'releaseId': track.get('release_id'),
            'position': track.get('position'),
        }

    def _primary_style(self, release: Mapping[str, Any], track: Mapping[str, Any]) -> str | None:
        artist = str(track.get('artist') or release.get('artists_sort') or '').lower()
        title = str(track.get('title') or '').lower()
        styles = [str(style) for style in release.get('styles') or [] if str(style).strip()]
        lower_styles = [style.lower() for style in styles]

        override = self._track_style_override(artist, title)
        if override:
            return override
        if 'scooter' in artist:
            return self._first_matching_style(lower_styles, self.SCOOTER_STYLE_PRIORITY) or self.COMMERCIAL_RAVE
        return self._first_matching_style(lower_styles, self.STYLE_PRIORITY) or self._first_specific_style(styles)

    def _track_style_override(self, artist: str, title: str) -> str | None:
        if 'lasgo' in artist:
            return self.VOCAL_TRANCE
        if 'le click' in artist and 'call me' in title:
            return self.EURO_HOUSE
        return None

    def _first_matching_style(self, lower_styles: list[str], priority: tuple[str, ...]) -> str | None:
        for style in priority:
            if style.lower() in lower_styles:
                return style

    def _first_specific_style(self, styles: list[str]) -> str | None:
        for style in styles:
            if style.lower() not in self.GENERIC_STYLE_LABELS:
                return style
        return styles[0] if styles else None

    def candidate_id(self, candidate: Mapping[str, Any]) -> str:
        track = candidate.get('track') or {}
        release_id = track.get('release_id') or candidate.get('release', {}).get('release_id')
        position = track.get('position') or track.get('title')
        return f'{release_id}:{position}'


class AzureOpenAIRecommendationService:
    def __init__(self, ai_client, prompt_builder: PromptBuilder | None = None):
        self.ai_client = ai_client
        self.prompt_builder = prompt_builder or PromptBuilder()

    def recommend(self, message: str, payload: Mapping[str, Any], context: Mapping[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        system_prompt, user_prompt = self.prompt_builder.build(message, payload, context, candidates)
        return self._parse_ai_json(self.ai_client.analyze(system_prompt, user_prompt))

    def _parse_ai_json(self, raw_response: str) -> dict[str, Any]:
        try:
            parsed = json.loads(raw_response or '{}')
        except json.JSONDecodeError as exc:
            raise RuntimeError('Azure OpenAI returned malformed AI DJ JSON') from exc
        if not isinstance(parsed, dict):
            raise RuntimeError('Azure OpenAI returned an unsupported AI DJ response')
        return parsed


class RecommendationPipeline:
    def __init__(self, recommendation_service: MusicRecommendationService, azure_service: AzureOpenAIRecommendationService | None = None):
        self.recommendation_service = recommendation_service
        self.azure_service = azure_service

    def local_candidates(self, message: str, context: Mapping[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        return self.recommendation_service.search_candidates(message, context.get('now_playing'), limit=limit)

    def curate(self, message: str, payload: Mapping[str, Any], context: Mapping[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        if self.azure_service is None:
            raise RuntimeError('Azure OpenAI recommendation service is unavailable')
        return self.azure_service.recommend(message, payload, context, candidates)


class ChatService:
    def __init__(
        self,
        context_builder: ConversationContextBuilder,
        recommendation_service: MusicRecommendationService,
        ai_client=None,
        playlist_action_service: PlaylistActionService | None = None,
    ):
        self.context_builder = context_builder
        self.recommendation_service = recommendation_service
        self.playlist_action_service = playlist_action_service
        if ai_client is None:
            try:
                from services.ai import AzureOpenAIClient
            except ImportError:
                from server.services.ai import AzureOpenAIClient
            ai_client = AzureOpenAIClient()
        self.ai_client = ai_client
        self.prompt_builder = PromptBuilder()
        self.pipeline = RecommendationPipeline(
            recommendation_service,
            AzureOpenAIRecommendationService(ai_client, self.prompt_builder),
        )

    def context(self) -> dict[str, Any]:
        return self.context_builder.build()

    def chat(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        message = self._message_from_payload(payload)
        context = self.context_builder.build()

        action_response = self._handle_action_message(message, payload, context)
        if action_response:
            return action_response

        candidates = self.pipeline.local_candidates(message, context, limit=self._candidate_limit(payload))
        candidates = self._without_recent_recommendations(candidates, payload)
        if not candidates:
            return {
                'response': 'I could not find a suitable local track in this collection for that request.',
                'suggested_tracks': [],
                'actions': [],
                'context': context,
                'ai_used': False,
            }

        ai_response = self.pipeline.curate(message, payload, context, candidates)
        recommendations = self._recommendations_from_ai(ai_response, candidates)
        return {
            'response': ai_response.get('response') or self._response_text(recommendations, context),
            'suggested_tracks': recommendations,
            'actions': self._actions(recommendations),
            'context': context,
            'ai_used': True,
        }

    def _handle_action_message(self, message: str, payload: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any] | None:
        if self.playlist_action_service is None:
            return None
        normalized = message.strip().lower()
        if not normalized:
            return None

        transport_command = self._transport_command(normalized)
        if transport_command:
            playback = self.playlist_action_service.transport(transport_command)
            return self._action_response(f'CD player command sent: {transport_command}.', context, playback=playback)

        playlist = self.playlist_action_service.find_playlist(message)
        if playlist and (self._wants_analysis(normalized) or self._is_playlist_name_only(normalized, playlist)):
            analysis = self.playlist_action_service.analyze_playlist(playlist)
            return self._action_response(self._playlist_analysis_text(analysis), context, playlist=playlist, analysis=analysis)
        if playlist and self._wants_playlist_play(normalized):
            playback = self.playlist_action_service.play_playlist(playlist)
            return self._action_response(f"Playing playlist {playlist.get('name')} on the CD player.", context, playback=playback, playlist=playlist)
        if self._wants_playlist_creation(normalized):
            return self._create_playlist_response(message, payload, context)
        return None

    def _create_playlist_response(self, message: str, payload: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
        limit = self._playlist_size(payload)
        recent_recommendations = self._recent_recommendations_from_payload(payload)
        if self._wants_recent_recommendations(message.lower()) and recent_recommendations:
            recommendations = recent_recommendations[:limit]
        else:
            candidates = self.pipeline.local_candidates(message, context, limit=max(10, limit * 3))
            recommendations = candidates[:limit]
        if not recommendations:
            return self._action_response('I could not find enough local tracks to create that playlist.', context)
        name = self._playlist_name(message) or 'AI DJ Playlist'
        playlist = {'name': name, 'tracks': [recommendation['track'] for recommendation in recommendations]}
        self.playlist_action_service.save_playlist(playlist)
        playback = None
        if self._wants_playlist_play(message.lower()):
            playback = self.playlist_action_service.play_playlist(playlist)
        return {
            'response': f"Created playlist {name} with {len(playlist['tracks'])} tracks." + (' Playback started.' if playback else ''),
            'suggested_tracks': recommendations,
            'actions': [{'type': 'replace_queue', 'label': 'Play Playlist'}],
            'context': context,
            'ai_used': False,
            'playlist': playlist,
            'playback': playback,
        }

    def _recent_recommendations_from_payload(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        direct = self._valid_recommendations(payload.get('recent_recommendations'))
        if direct:
            return direct
        conversation = payload.get('conversation') or payload.get('messages') or []
        if not isinstance(conversation, list):
            return []
        for message in reversed(conversation):
            if not isinstance(message, Mapping):
                continue
            recommendations = self._valid_recommendations(message.get('suggested_tracks'))
            if recommendations:
                return recommendations
        return []

    def _without_recent_recommendations(self, candidates: list[dict[str, Any]], payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        recent_recommendations = self._recent_recommendations_from_payload(payload)
        if not recent_recommendations:
            return candidates

        recent_ids = {self.prompt_builder.candidate_id(recommendation) for recommendation in recent_recommendations}
        filtered = [candidate for candidate in candidates if self.prompt_builder.candidate_id(candidate) not in recent_ids]
        return filtered or candidates

    def _valid_recommendations(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        recommendations = []
        for item in value:
            if not isinstance(item, Mapping) or not isinstance(item.get('track'), Mapping):
                continue
            recommendations.append(dict(item))
        return recommendations

    def _action_response(
        self,
        response: str,
        context: Mapping[str, Any],
        playback: Mapping[str, Any] | None = None,
        playlist: Mapping[str, Any] | None = None,
        analysis: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            'response': response,
            'suggested_tracks': [],
            'actions': [],
            'context': context,
            'ai_used': False,
        }
        if playback is not None:
            payload['playback'] = playback
        if playlist is not None:
            payload['playlist'] = playlist
        if analysis is not None:
            payload['playlist_analysis'] = analysis
        return payload

    def _transport_command(self, normalized: str) -> str | None:
        compact = re.sub(r'[^a-z0-9á-ž ]+', ' ', normalized)
        words = set(compact.split())
        mapping = {
            'pause': {'pause', 'pauza', 'pozastav'},
            'resume': {'resume', 'pokračuj', 'pokracuj'},
            'stop': {'stop', 'zastav'},
            'next': {'next', 'další', 'dalsi'},
            'previous': {'previous', 'prev', 'předchozí', 'predchozi'},
        }
        for command, triggers in mapping.items():
            if words.intersection(triggers):
                return command
        return None

    def _wants_analysis(self, normalized: str) -> bool:
        return any(token in normalized for token in ('analyz', 'rozober', 'rozeb', 'analyze'))

    def _wants_playlist_play(self, normalized: str) -> bool:
        return any(token in normalized for token in ('pusti', 'pusť', 'spust', 'play', 'prehr', 'zahraj'))

    def _wants_playlist_creation(self, normalized: str) -> bool:
        return any(token in normalized for token in ('vytvor', 'vytvoř', 'create', 'sprav', 'udelaj', 'udělej')) and 'playlist' in normalized

    def _wants_recent_recommendations(self, normalized: str) -> bool:
        return any(token in normalized for token in (
            'z toho',
            'z týchto',
            'z techto',
            'z těchto',
            'z odporuceni',
            'z doporučení',
            'from that',
            'from these',
            'these recommendations',
            'those recommendations',
        ))

    def _is_playlist_name_only(self, normalized: str, playlist: Mapping[str, Any]) -> bool:
        return normalized == str(playlist.get('name') or '').strip().lower()

    def _playlist_analysis_text(self, analysis: Mapping[str, Any]) -> str:
        styles = ', '.join(item['name'] for item in analysis.get('top_styles') or []) or 'mixed styles'
        years = analysis.get('year_range')
        year_text = f" from {years[0]}-{years[1]}" if years else ''
        energy = analysis.get('average_energy')
        energy_text = f", average energy {energy}/100" if energy is not None else ''
        return f"Playlist {analysis.get('name')} has {analysis.get('track_count')} tracks{year_text}. Main styles: {styles}{energy_text}."

    def _playlist_size(self, payload: Mapping[str, Any]) -> int:
        try:
            return max(3, min(25, int(payload.get('limit') or payload.get('playlist_size') or 10)))
        except (TypeError, ValueError):
            return 10

    def _playlist_name(self, message: str) -> str | None:
        lower = message.lower()
        marker_index = lower.find('playlist')
        if marker_index < 0:
            return None
        name = message[marker_index + len('playlist'):].strip(' .:-"\'')
        for prefix in ('named ', 'called ', 's nazvom ', 's názvem ', 'nazvany ', 'nazvaný '):
            if name.lower().startswith(prefix):
                name = name[len(prefix):]
                break
        for token in ('pusti', 'pusť', 'spust', 'play', 'prehrat', 'prehraj'):
            name = re.sub(rf'\b{token}\b', '', name, flags=re.IGNORECASE)
        for filler in ('z toho', 'z týchto', 'z techto', 'z těchto', 'from that', 'from these'):
            name = name.replace(filler, '')
        name = name.strip(' .:-"\'')
        return name[:80] or None

    def recommendations_for_current(self, limit: int = 5) -> dict[str, Any]:
        context = self.context_builder.build()
        recommendations = self.recommendation_service.recommend('play something similar', context.get('now_playing'), limit=limit)
        return {
            'response': self._response_text(recommendations, context),
            'suggested_tracks': recommendations,
            'context': context,
        }

    def _message_from_payload(self, payload: Mapping[str, Any]) -> str:
        if payload.get('message'):
            return str(payload.get('message'))
        conversation = payload.get('conversation') or payload.get('messages') or []
        if isinstance(conversation, list) and conversation:
            latest = conversation[-1]
            if isinstance(latest, dict):
                return str(latest.get('content') or latest.get('message') or '')
            return str(latest)
        return ''

    def _candidate_limit(self, payload: Mapping[str, Any]) -> int:
        try:
            return max(50, min(150, int(payload.get('candidate_limit') or 100)))
        except (TypeError, ValueError):
            return 100

    def _response_text(self, recommendations: list[dict[str, Any]], context: Mapping[str, Any]) -> str:
        if not recommendations:
            return 'I could not find a suitable local track in this collection for that request.'
        current_track = context.get('current_track') or {}
        current_name = current_track.get('full_name') or current_track.get('title') or 'the current track'
        top = recommendations[0]
        track = top['track']
        return (
            f"From {current_name}, I would move to {track.get('full_name')}. "
            f"It fits your request because {top.get('reason')}"
        )

    def _actions(self, recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not recommendations:
            return []
        return recommendations[0].get('actions') or []

    def _recommendations_from_ai(self, ai_response: Mapping[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidate_map = {self.prompt_builder.candidate_id(candidate): candidate for candidate in candidates}
        selected = []
        selected_ids = set()
        for item in ai_response.get('suggested_tracks') or []:
            if not isinstance(item, dict):
                continue
            candidate_id = str(item.get('candidate_id') or '')
            candidate = candidate_map.get(candidate_id)
            if not candidate:
                continue
            selected.append(self._merge_ai_recommendation(candidate, item))
            selected_ids.add(candidate_id)
            if len(selected) >= 10:
                break
        target_count = min(8, len(candidates))
        if len(selected) < target_count:
            for candidate in candidates:
                candidate_id = self.prompt_builder.candidate_id(candidate)
                if candidate_id in selected_ids:
                    continue
                selected.append(candidate)
                selected_ids.add(candidate_id)
                if len(selected) >= target_count:
                    break
        return selected or candidates[:target_count]

    def _merge_ai_recommendation(self, candidate: dict[str, Any], item: Mapping[str, Any]) -> dict[str, Any]:
        merged = dict(candidate)
        if item.get('reason'):
            merged['reason'] = str(item.get('reason'))
        merged['confidence'] = self._confidence(item.get('confidence'), candidate.get('confidence'))
        musical_dna = item.get('musical_dna') if isinstance(item.get('musical_dna'), dict) else {}
        if musical_dna:
            merged['musical_dna'] = {
                'shared': self._string_list(musical_dna.get('shared')),
                'differs': self._string_list(musical_dna.get('differs')),
            }
        return merged

    def _confidence(self, value: Any, fallback: Any) -> int:
        try:
            return max(1, min(100, int(value)))
        except (TypeError, ValueError):
            try:
                return max(1, min(100, int(fallback)))
            except (TypeError, ValueError):
                return 50

    def _string_list(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        return [str(value) for value in values if str(value).strip()][:6]