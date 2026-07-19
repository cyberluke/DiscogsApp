import json
from typing import Any, Mapping


class MusicAnalysisParser:
    SCORE_FIELDS = ('energy', 'danceability', 'euphoria', 'nostalgia', 'commercial', 'club', 'radio', 'cheese')
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
        return result

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