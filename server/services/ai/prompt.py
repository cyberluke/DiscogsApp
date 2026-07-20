import json
from typing import Any, Mapping


class MusicAnalysisPrompt:
    SYSTEM_PROMPT = (
        'You are an expert in European dance music from 1988-2010. '
        'Analyze Discogs release metadata as historical music context. '
        'Classify scene, per-track production style, dancefloor suitability, '
        'commercial appeal, nostalgia, and recommendation DNA. Avoid generic descriptions. '
        'Do not assume all songs by the same artist are similar; analyze each release and track independently before inferring relationships. '
        'Prioritize production school, groove, arrangement, rhythm section, synth palette, vocal/rap balance, mixability, and dancefloor function over artist identity. '
        'Use precise scene taxonomy: Eurodance, Euro House, vocal trance, hard trance, hands-up, happy hardcore, hard house, techno, and dance-pop are not interchangeable. '
        'Do not use Eurodance as a blanket term for all European chart dance. If Discogs styles or track context point to vocal trance, Euro House, hard trance, hard house, or rave-pop, name that more precise style first. '
        'When a release is true Eurodance, distinguish DJ-oriented 90s Eurodance from separate Euro House and Dance-pop lanes: favor high energy, club mixes, hard mixes, four-on-the-floor drive, and dancefloor utility in the summary and keywords without merging those subgenres. '
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
            'late_night, festival, mood, recommended_after, similar_artists, keywords, production, production_signature, songwriting, artist_context. '\
            'Scores must be integers from 0 to 100. Summary must be 2-5 specific sentences. '\
            'Summary must use DJ/producer language: production school, groove, arrangement, percussion, bass, synth palette, vocal/rap balance, mixability, and dance floor impact. '\
            'recommended_after and similar_artists must contain 3-10 artists. '\
            'guilty_pleasure should be true only for kitschy-but-enjoyable releases. '
            'production must contain integer scores energy, drive, groove, rhythm_complexity, rap_presence, vocal_balance, harmony_density, dynamic_range, production_density, commercial_polish, club_focus, radio_focus, emotional_intensity plus text fields percussion_style, bass_style, synth_style, vocal_style, atmosphere. '
            'production_signature must be 1-5 recognizable production schools such as early_90s_raw_eurodance, german_dance, swedish_pop, italian_house, trance_classic, hands_up, rave; these are not genres. '
            'songwriting must contain integer scores hook_strength, chorus_focus, verse_focus, instrumental_focus, build_up, breakdown plus text fields intro_length and outro_length. '
            'artist_context must contain era, producer, production_team, label_period, lineup when metadata supports it; otherwise empty strings. '
            'Scene and keywords must preserve Discogs style distinctions: Lasgo-style Belgian vocal trance is not Eurodance; Le Click "Call Me" is Euro House; Scooter is usually commercial rave, hard trance, hard house, happy hardcore, or hands-up depending on the release, not plain Eurodance unless the metadata only supports that.\n\n'
            'For user-facing recommendations, keep Eurodance, Euro House, and Dance-pop separate. Identify proper DJ Eurodance only when it is true Eurodance with strong energy, club/extended/hard mixes, and less soft radio-pop weighting.\n\n'
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