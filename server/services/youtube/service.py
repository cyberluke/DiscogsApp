from __future__ import annotations

import json
import os
import re
from typing import Any, Mapping
from urllib.parse import unquote

import requests


class YouTubeSearchService:
    def __init__(
        self,
        repository,
        api_key: str | None = None,
        cache_path: str = os.path.join('server', 'youtube_video_cache.json'),
        timeout_seconds: float = 4,
    ):
        self.repository = repository
        self.api_key = api_key
        self.cache_path = cache_path
        self.timeout_seconds = timeout_seconds
        self._kodi_music_videos: list[dict[str, Any]] = []
        self._memory_cache: dict[str, dict[str, Any] | None] = {}
        self._load_cache()

    def set_kodi_music_videos(self, music_videos: list[dict[str, Any]]) -> None:
        self._kodi_music_videos = list(music_videos or [])

    def find_best_video(
        self,
        release: Mapping[str, Any] | None = None,
        track: Mapping[str, Any] | None = None,
        artist: str | None = None,
        title: str | None = None,
        duration: int | None = None,
    ) -> dict[str, Any] | None:
        return self.find_best_youtube_video(release=release, track=track, artist=artist, title=title, duration=duration)

    def find_best_youtube_video(
        self,
        release: Mapping[str, Any] | None = None,
        track: Mapping[str, Any] | None = None,
        artist: str | None = None,
        title: str | None = None,
        duration: int | None = None,
    ) -> dict[str, Any] | None:
        artist, title = self._track_identity(release=release, track=track, artist=artist, title=title)
        if not title or not self.api_key:
            return None

        cache_key = self._cache_key(artist, title)
        if cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            if cached and cached.get('embeddable') is True:
                return dict(cached)

        input_title = title.lower()
        input_artist = artist.lower()
        existing_video = self.repository.find_video_offset_by_alias(input_title)
        if existing_video:
            input_title = self._text(existing_video.get('title')).lower()
            input_artist = self._text(existing_video.get('artist')).lower()

        candidates = self._search_youtube(input_artist, input_title)
        selected_video = self._select_youtube_video(input_artist, input_title, candidates)
        result = self._youtube_video_result(selected_video, artist, title, duration) if selected_video else None
        self._memory_cache[cache_key] = result
        self._save_cache()
        return dict(result) if result else None

    def find_best_kodi_music_video(
        self,
        release: Mapping[str, Any] | None = None,
        track: Mapping[str, Any] | None = None,
        artist: str | None = None,
        title: str | None = None,
        duration: int | None = None,
        music_videos: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        artist, title = self._track_identity(release=release, track=track, artist=artist, title=title)
        if not title:
            return None

        candidates = self._kodi_music_videos if music_videos is None else list(music_videos or [])
        cache_key = self._cache_key(artist, title)
        if music_videos is None and cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            return dict(cached) if cached else None

        if not candidates:
            return None

        input_title = title.lower()
        input_artist = artist.lower()
        existing_video = self.repository.find_video_offset_by_alias(input_title)
        if existing_video:
            input_title = self._text(existing_video.get('title')).lower()
            input_artist = self._text(existing_video.get('artist')).lower()

        selected_video = self._select_kodi_music_video(input_artist, input_title, candidates)
        result = self._kodi_video_result(selected_video, artist, title, duration) if selected_video else None
        if music_videos is None:
            self._memory_cache[cache_key] = result
            self._save_cache()
        return dict(result) if result else None

    def sync_state(self, playback_status: Mapping[str, Any]) -> dict[str, Any]:
        track = playback_status.get('current_track')
        video = self.find_best_video(track=track) if isinstance(track, Mapping) else None
        elapsed = int(float(playback_status.get('elapsed') or 0))
        playback_state = playback_status.get('playback_state') or 'idle'
        offset_seconds = int(video.get('offset_seconds') or 0) if video else 0
        seek_seconds = max(0, elapsed + offset_seconds)

        return {
            'video': video,
            'message': None if video else 'No suitable music video found.',
            'playback_state': playback_state,
            'seek_seconds': seek_seconds,
            'should_play': playback_state == 'playing' and video is not None,
            'should_pause': playback_state in ('paused', 'stopped', 'idle', 'preparing', 'error'),
            'source': 'playback_session',
        }

    def _select_kodi_music_video(self, input_artist: str, input_title: str, videos: list[dict[str, Any]]) -> dict[str, Any] | None:
        for video in videos:
            video_title = self._text(video.get('title')).lower()
            video_artist = self._text((video.get('artist') or [''])[0] if isinstance(video.get('artist'), list) else video.get('artist')).lower()

            video_title_words = video_title.split()
            video_artist_words = video_artist.split()
            input_title_words = input_title.split()
            input_artist_words = input_artist.split()

            title_similarity = len(set(video_title_words) & set(input_title_words))
            artist_similarity = len(set(video_artist_words) & set(input_artist_words))

            if title_similarity >= len(video_title_words):
                selected = dict(video)
                selected['_confidence'] = self._confidence(title_similarity, video_title_words, artist_similarity, video_artist_words)
                return selected
        return None

    def _search_youtube(self, artist: str, title: str) -> list[dict[str, Any]]:
        query = ' '.join(part for part in (artist, title, 'official music video') if part).strip()
        try:
            search_response = requests.get(
                'https://www.googleapis.com/youtube/v3/search',
                params={
                    'part': 'snippet',
                    'type': 'video',
                    'maxResults': 10,
                    'q': query,
                    'videoEmbeddable': 'true',
                    'key': self.api_key,
                },
                timeout=self.timeout_seconds,
            )
            search_response.raise_for_status()
        except requests.RequestException:
            return []

        items = search_response.json().get('items') or []
        video_ids = [item.get('id', {}).get('videoId') for item in items if item.get('id', {}).get('videoId')]
        details_by_id = self._video_details(video_ids)
        for item in items:
            video_id = item.get('id', {}).get('videoId')
            if video_id:
                details = details_by_id.get(video_id, {})
                item['_duration'] = details.get('duration')
                item['_embeddable'] = details.get('embeddable')
                item['_playback_safe'] = details.get('playback_safe')
        return items

    def _video_details(self, video_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not video_ids:
            return {}
        try:
            response = requests.get(
                'https://www.googleapis.com/youtube/v3/videos',
                params={
                    'part': 'contentDetails,status',
                    'id': ','.join(video_ids),
                    'key': self.api_key,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException:
            return {}
        return {
            item.get('id'): {
                'duration': item.get('contentDetails', {}).get('duration'),
                'embeddable': item.get('status', {}).get('embeddable'),
                'playback_safe': self._is_playback_safe(item.get('status', {})),
            }
            for item in response.json().get('items') or []
            if item.get('id')
        }

    def _select_youtube_video(self, input_artist: str, input_title: str, videos: list[dict[str, Any]]) -> dict[str, Any] | None:
        scored = []
        for video in videos:
            if video.get('_embeddable') is not True:
                continue
            if video.get('_playback_safe') is not True:
                continue
            if not self._is_trusted_youtube_candidate(input_artist, video):
                continue
            score = self._youtube_score(input_artist, input_title, video)
            if score >= 0.45:
                selected = dict(video)
                selected['_confidence'] = round(score, 2)
                scored.append((score, selected))
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1]

    def _youtube_video_result(self, video: Mapping[str, Any], artist: str, title: str, duration: int | None) -> dict[str, Any]:
        snippet = video.get('snippet') or {}
        youtube_id = video.get('id', {}).get('videoId')
        channel = self._text(snippet.get('channelTitle')) or artist
        video_title = self._text(snippet.get('title')) or title
        offset = self.repository.ensure_video_offset(video_title, channel)
        offset_parts = offset.get('videos_offsets') or [0, 0, 0]
        thumbnails = snippet.get('thumbnails') or {}
        thumbnail = (
            thumbnails.get('maxres', {}).get('url')
            or thumbnails.get('high', {}).get('url')
            or thumbnails.get('medium', {}).get('url')
            or thumbnails.get('default', {}).get('url')
        )

        return {
            'video_id': youtube_id or '',
            'youtube_id': youtube_id,
            'provider_id': youtube_id,
            'title': video_title,
            'channel': channel,
            'thumbnail': thumbnail,
            'duration': video.get('_duration') or duration,
            'embeddable': video.get('_embeddable') is True,
            'playback_safe': video.get('_playback_safe') is True,
            'url': f'https://www.youtube.com/watch?v={youtube_id}' if youtube_id else None,
            'confidence': video.get('_confidence'),
            'offset_seconds': self._offset_seconds(offset_parts),
            'offset_parts': offset_parts,
            'artist': artist,
            'track': title,
        }

    def _is_playback_safe(self, status: Mapping[str, Any]) -> bool:
        return (
            status.get('embeddable') is True
            and status.get('privacyStatus', 'public') == 'public'
            and status.get('uploadStatus', 'processed') == 'processed'
        )

    def _is_trusted_youtube_candidate(self, artist: str, video: Mapping[str, Any]) -> bool:
        snippet = video.get('snippet') or {}
        raw_title = self._text(snippet.get('title')).lower()
        channel = self._normalize(snippet.get('channelTitle'))
        artist_words = [word for word in self._normalize(artist).split() if len(word) > 2 and word not in {'feat', 'ft', 'and', 'the'}]
        title_blocklist = ('lyrics', 'lyric', 'karaoke', 'cover', 'reaction', 'nightcore', 'sped up', 'slowed', 'reverb', 'just dance', 'live', 'bst hyde park')
        channel_blocklist = ('radio', 'hits', 'lyrics', 'music', 'media', 'korner', 'vibes')

        if any(token in raw_title for token in title_blocklist):
            return False
        if 'vevo' in channel or 'official' in channel:
            return True
        if artist_words and any(word in channel for word in artist_words):
            return not any(token in channel for token in channel_blocklist)
        return False

    def _kodi_video_result(self, video: Mapping[str, Any], artist: str, title: str, duration: int | None) -> dict[str, Any]:
        provider_id = video.get('musicvideoid')
        file_url = self._text(video.get('file'))
        youtube_id = self._extract_youtube_id(file_url)
        channel = self._text((video.get('artist') or [''])[0] if isinstance(video.get('artist'), list) else video.get('artist')) or artist
        video_title = self._text(video.get('title')) or title
        offset = self.repository.ensure_video_offset(video_title, video.get('artist') or channel)
        offset_parts = offset.get('videos_offsets') or [0, 0, 0]

        return {
            'video_id': youtube_id or str(provider_id or ''),
            'youtube_id': youtube_id,
            'provider_id': provider_id,
            'title': video_title,
            'channel': channel,
            'thumbnail': video.get('thumbnail'),
            'duration': video.get('runtime') or duration,
            'url': f'https://www.youtube.com/watch?v={youtube_id}' if youtube_id else file_url,
            'confidence': video.get('_confidence'),
            'offset_seconds': self._offset_seconds(offset_parts),
            'offset_parts': offset_parts,
            'artist': artist,
            'track': title,
        }

    def _track_identity(
        self,
        release: Mapping[str, Any] | None,
        track: Mapping[str, Any] | None,
        artist: str | None,
        title: str | None,
    ) -> tuple[str, str]:
        if track:
            title = title or self._text(track.get('title'))
            artist = artist or self._text(track.get('artist'))
            if not artist and track.get('full_name') and ' - ' in self._text(track.get('full_name')):
                artist = self._text(track.get('full_name')).split(' - ', 1)[0]
        if release:
            artist = artist or self._text(release.get('artists_sort'))
        return self._text(artist), self._text(title)

    def _cache_key(self, artist: str, title: str) -> str:
        return f'{artist.strip().lower()}::{title.strip().lower()}'

    def _load_cache(self) -> None:
        if not os.path.exists(self.cache_path):
            return
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as cache_file:
                data = json.load(cache_file)
            self._memory_cache = data.get('data') if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            self._memory_cache = {}

    def _save_cache(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.cache_path) or '.', exist_ok=True)
            with open(self.cache_path, 'w', encoding='utf-8') as cache_file:
                json.dump({'data': self._memory_cache}, cache_file, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def _extract_youtube_id(self, value: str) -> str | None:
        decoded = unquote(value or '')
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{6,})',
            r'(?:video_id|videoid|videoId)=([A-Za-z0-9_-]{6,})',
        ]
        for pattern in patterns:
            match = re.search(pattern, decoded)
            if match:
                return match.group(1)
        return None

    def _offset_seconds(self, offset_parts: list[Any]) -> int:
        minutes = self._offset_part(offset_parts, 0)
        seconds = self._offset_part(offset_parts, 1)
        milliseconds = self._offset_part(offset_parts, 2)
        return minutes * 60 + seconds + round(milliseconds / 1000)

    def _offset_part(self, offset_parts: list[Any], index: int) -> int:
        if len(offset_parts) <= index:
            return 0
        try:
            return int(offset_parts[index])
        except (TypeError, ValueError):
            return 0

    def _confidence(self, title_similarity: int, title_words: list[str], artist_similarity: int, artist_words: list[str]) -> float:
        title_score = title_similarity / max(1, len(title_words))
        artist_score = artist_similarity / max(1, len(artist_words))
        return round((title_score * 0.8) + (artist_score * 0.2), 2)

    def _youtube_score(self, artist: str, title: str, video: Mapping[str, Any]) -> float:
        snippet = video.get('snippet') or {}
        raw_title = self._text(snippet.get('title')).lower()
        raw_channel = self._text(snippet.get('channelTitle')).lower()
        video_title = self._normalize(snippet.get('title'))
        channel = self._normalize(snippet.get('channelTitle'))
        artist_text = self._normalize(artist)
        title_text = self._normalize(title)
        artist_words = set(artist_text.split())
        title_words = set(title_text.split())
        video_words = set(video_title.split())

        title_score = len(title_words & video_words) / max(1, len(title_words))
        artist_score = max(
            len(artist_words & video_words) / max(1, len(artist_words)),
            len(artist_words & set(channel.split())) / max(1, len(artist_words)),
        )
        score = (title_score * 0.6) + (artist_score * 0.3)
        if 'vevo' in raw_channel or 'official' in raw_channel:
            score += 0.22
        if 'official video' in raw_title or 'official music video' in raw_title:
            score += 0.14
        elif 'official audio' in raw_title:
            score -= 0.1
        if any(token in raw_title for token in ('lyrics', 'lyric video', 'karaoke', 'cover', 'reaction', 'nightcore', 'sped up')):
            score -= 0.25
        if 'live' in raw_title and 'official video' not in raw_title:
            score -= 0.22
        if any(token in raw_channel for token in ('radio', 'hits', 'lyrics', 'music', 'media')) and 'vevo' not in raw_channel:
            score -= 0.18
        return max(0, min(score, 1))

    def _normalize(self, value: Any) -> str:
        text = self._text(value).lower()
        text = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', text)
        text = re.sub(r'[^a-z0-9]+', ' ', text)
        return re.sub(r'\s+', ' ', text).strip()

    def _text(self, value: Any) -> str:
        if isinstance(value, list):
            return ' '.join(self._text(item) for item in value if item is not None).strip()
        return str(value or '').strip()


class YouTubeSyncService:
    def __init__(self, search_service: YouTubeSearchService, playback_runtime):
        self.search_service = search_service
        self.playback_runtime = playback_runtime

    def current_state(self) -> dict[str, Any]:
        return self.search_service.sync_state(self.playback_runtime.status())
