import json
from typing import Any, Mapping


class MusicAnalysisParser:
    SCORE_FIELDS = ('energy', 'danceability', 'euphoria', 'nostalgia', 'commercial', 'club', 'radio', 'cheese')
    PRODUCTION_SCORE_FIELDS = (
        'energy', 'drive', 'groove', 'rhythm_complexity', 'rap_presence', 'vocal_balance',
        'harmony_density', 'dynamic_range', 'production_density', 'commercial_polish',
        'club_focus', 'radio_focus', 'emotional_intensity'
    )
    PRODUCTION_TEXT_FIELDS = ('percussion_style', 'bass_style', 'synth_style', 'vocal_style', 'atmosphere')
    SONGWRITING_SCORE_FIELDS = ('hook_strength', 'chorus_focus', 'verse_focus', 'instrumental_focus', 'build_up', 'breakdown')
    SONGWRITING_LENGTH_FIELDS = ('intro_length', 'outro_length')
    ARTIST_CONTEXT_FIELDS = ('era', 'producer', 'production_team', 'label_period', 'lineup')
    BOOLEAN_FIELDS = ('guilty_pleasure', 'driving_music', 'late_night', 'festival')
    LIST_FIELDS = ('mood', 'recommended_after', 'similar_artists', 'keywords')

    def parse(self, raw_response: str | Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(raw_response) if isinstance(raw_response, Mapping) else json.loads(raw_response)

        result = {
            'scene': str(payload.get('scene') or 'Unknown'),
            'summary': str(payload.get('summary') or ''),
        }
        for field in self.SCORE_FIELDS:
            result[field] = self._score(payload.get(field))
        for field in self.BOOLEAN_FIELDS:
            result[field] = bool(payload.get(field, False))
        for field in self.LIST_FIELDS:
            result[field] = self._string_list(payload.get(field))
        result['production'] = self._production(payload.get('production'))
        result['production_signature'] = self._string_list(payload.get('production_signature'))
        result['songwriting'] = self._songwriting(payload.get('songwriting'))
        result['artist_context'] = self._artist_context(payload.get('artist_context'))
        return result

    def _production(self, value: Any) -> dict[str, Any]:
        payload = value if isinstance(value, Mapping) else {}
        result = {field: self._score(payload.get(field)) for field in self.PRODUCTION_SCORE_FIELDS}
        for field in self.PRODUCTION_TEXT_FIELDS:
            result[field] = str(payload.get(field) or '').strip()
        return result

    def _songwriting(self, value: Any) -> dict[str, Any]:
        payload = value if isinstance(value, Mapping) else {}
        result = {field: self._score(payload.get(field)) for field in self.SONGWRITING_SCORE_FIELDS}
        for field in self.SONGWRITING_LENGTH_FIELDS:
            result[field] = str(payload.get(field) or '').strip()
        return result

    def _artist_context(self, value: Any) -> dict[str, str]:
        payload = value if isinstance(value, Mapping) else {}
        return {field: str(payload.get(field) or '').strip() for field in self.ARTIST_CONTEXT_FIELDS}

    def _score(self, value: Any) -> int:
        try:
            score = int(round(float(value)))
        except (TypeError, ValueError):
            return 0
        return min(max(score, 0), 100)

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]