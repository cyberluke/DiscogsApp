import json
from typing import Any, Mapping


class MusicAnalysisPrompt:
    SYSTEM_PROMPT = (
        'You are an expert in European dance music from 1988-2010. '
        'Analyze Discogs release metadata as historical music context. '
        'Classify scene, musical character, production style, dancefloor suitability, '
        'commercial appeal, nostalgia, and recommendation DNA. Avoid generic descriptions. '
        'Use precise scene taxonomy: Eurodance, Euro House, vocal trance, hard trance, hands-up, happy hardcore, hard house, techno, and dance-pop are not interchangeable. '
        'Do not use Eurodance as a blanket term for all European chart dance. If Discogs styles or track context point to vocal trance, Euro House, hard trance, hard house, or rave-pop, name that more precise style first. '
        'Return JSON only.'
    )

    def build(self, release: Mapping[str, Any]) -> tuple[str, str]:
        context = {
            'artist': release.get('artists_sort'),
            'title': release.get('title'),
            'year': release.get('year'),
            'released': release.get('released'),
            'country': release.get('country'),
            'labels': self._names(release.get('labels')),
            'companies': self._names(release.get('companies')),
            'genres': release.get('genres') or [],
            'styles': release.get('styles') or [],
            'tracklist': [
                {
                    'position': track.get('position'),
                    'title': track.get('title'),
                    'duration': track.get('duration'),
                    'artists': self._names(track.get('artists')),
                    'extraartists': self._names(track.get('extraartists')),
                }
                for track in release.get('tracklist') or []
            ],
            'release_notes': release.get('notes'),
            'community_rating': (release.get('community') or {}).get('rating'),
        }
        user_prompt = (
            'Analyze this Discogs release using only the metadata below. '\
            'Return one JSON object with exactly these fields: scene, summary, energy, danceability, '\
            'euphoria, nostalgia, commercial, club, radio, cheese, guilty_pleasure, driving_music, '\
            'late_night, festival, mood, recommended_after, similar_artists, keywords. '\
            'Scores must be integers from 0 to 100. Summary must be 2-5 specific sentences. '\
            'recommended_after and similar_artists must contain 3-10 artists. '\
            'guilty_pleasure should be true only for kitschy-but-enjoyable releases. '
            'Scene and keywords must preserve Discogs style distinctions: Lasgo-style Belgian vocal trance is not Eurodance; Le Click "Call Me" is Euro House; Scooter is usually commercial rave, hard trance, hard house, happy hardcore, or hands-up depending on the release, not plain Eurodance unless the metadata only supports that.\n\n'
            f'{json.dumps(context, ensure_ascii=False, indent=2)}'
        )
        return self.SYSTEM_PROMPT, user_prompt

    def _names(self, items: Any) -> list[str]:
        names = []
        for item in items or []:
            if isinstance(item, Mapping):
                name = item.get('name')
                if name:
                    names.append(name)
            elif item:
                names.append(str(item))
        return names