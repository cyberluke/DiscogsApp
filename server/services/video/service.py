from __future__ import annotations

import os
import re
import math
import subprocess
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol


VIDEO_EXTENSIONS = {'.mp4', '.webm', '.ogg', '.ogv', '.m4v', '.mov'}
NO_CURRENT_TRACK_MESSAGE = 'No current track.'


class VideoAudioAnalyzer:
    def __init__(
        self,
        executable: str = 'ffmpeg',
        scan_seconds: int = 45,
        silence_threshold_db: int = -45,
        min_intro_seconds: float = 0.75,
        main_program_scan_seconds: int = 12,
        rms_sample_rate: int = 8000,
        rms_window_seconds: float = 0.25,
        main_program_threshold_ratio: float = 0.65,
        main_program_window_seconds: float = 3.0,
        main_program_min_hit_ratio: float = 0.5,
        timeout_seconds: int = 20,
    ):
        self.executable = executable
        self.scan_seconds = scan_seconds
        self.silence_threshold_db = silence_threshold_db
        self.min_intro_seconds = min_intro_seconds
        self.main_program_scan_seconds = main_program_scan_seconds
        self.rms_sample_rate = rms_sample_rate
        self.rms_window_seconds = rms_window_seconds
        self.main_program_threshold_ratio = main_program_threshold_ratio
        self.main_program_window_seconds = main_program_window_seconds
        self.main_program_min_hit_ratio = main_program_min_hit_ratio
        self.timeout_seconds = timeout_seconds
        self._cache: dict[tuple[str, float, int], int] = {}

    def intro_silence_offset(self, path: Path) -> int:
        try:
            stat = path.stat()
        except OSError:
            return 0

        cache_key = (str(path.resolve()), stat.st_mtime, stat.st_size)
        if cache_key not in self._cache:
            self._cache[cache_key] = self._detect_intro_silence(path)
        return self._cache[cache_key]

    def _detect_intro_silence(self, path: Path) -> int:
        envelope = self._rms_envelope(path)
        main_program_offset = self._detect_main_program_offset(envelope)
        if main_program_offset:
            return main_program_offset
        return self._detect_digital_silence(path)

    def _detect_digital_silence(self, path: Path) -> int:
        command = [
            self.executable,
            '-hide_banner',
            '-nostats',
            '-nostdin',
            '-t',
            str(self.scan_seconds),
            '-i',
            str(path),
            '-af',
            f'silencedetect=noise={self.silence_threshold_db}dB:d=0.25',
            '-f',
            'null',
            os.devnull,
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return 0
        return self._parse_intro_silence(completed.stderr or completed.stdout or '')

    def _rms_envelope(self, path: Path) -> list[float]:
        command = [
            self.executable,
            '-hide_banner',
            '-loglevel',
            'error',
            '-nostdin',
            '-t',
            str(self.scan_seconds),
            '-i',
            str(path),
            '-vn',
            '-ac',
            '1',
            '-ar',
            str(self.rms_sample_rate),
            '-f',
            's16le',
            '-',
        ]
        try:
            raw_audio = subprocess.check_output(command, stderr=subprocess.DEVNULL, timeout=self.timeout_seconds)
        except (OSError, subprocess.SubprocessError):
            return []

        samples = memoryview(raw_audio).cast('h')
        window_size = max(1, int(self.rms_sample_rate * self.rms_window_seconds))
        envelope: list[float] = []
        for start in range(0, len(samples) - window_size + 1, window_size):
            window = samples[start:start + window_size]
            envelope.append(math.sqrt(sum(sample * sample for sample in window) / len(window)))
        return envelope

    def _detect_main_program_offset(self, envelope: list[float]) -> int:
        positive_values = sorted(value for value in envelope if value > 50)
        if len(positive_values) < 8:
            return 0

        p90 = positive_values[int((len(positive_values) - 1) * 0.9)]
        threshold = p90 * self.main_program_threshold_ratio
        windows_per_second = 1 / self.rms_window_seconds
        scan_windows = min(len(envelope), int(self.main_program_scan_seconds * windows_per_second))
        block_windows = max(1, int(self.main_program_window_seconds * windows_per_second))
        required_hits = math.ceil(block_windows * self.main_program_min_hit_ratio)

        for index in range(0, max(0, scan_windows - block_windows + 1)):
            block = envelope[index:index + block_windows]
            sorted_block = sorted(block)
            median = sorted_block[len(sorted_block) // 2]
            hit_count = sum(1 for value in block if value >= threshold)
            if median >= threshold and hit_count >= required_hits:
                offset = index * self.rms_window_seconds
                if offset < self.min_intro_seconds:
                    continue
                return max(1, math.ceil(offset))
        return 0

    def _parse_intro_silence(self, output: str) -> int:
        intro_started_at_zero = False
        for line in output.splitlines():
            start_match = re.search(r'silence_start:\s*([0-9.]+)', line)
            if start_match:
                intro_started_at_zero = float(start_match.group(1)) <= 0.15
                continue

            end_match = re.search(r'silence_end:\s*([0-9.]+)', line)
            if intro_started_at_zero and end_match:
                silence_end = float(end_match.group(1))
                if silence_end >= self.min_intro_seconds:
                    return max(1, int(round(silence_end)))
                return 0
        return 0


@dataclass(frozen=True)
class VideoCandidate:
    provider: str
    provider_id: str
    title: str
    channel: str
    source_url: str
    artist: str
    track: str
    duration: int | str | None = None
    thumbnail: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'provider': self.provider,
            'provider_id': self.provider_id,
            'title': self.title,
            'channel': self.channel,
            'source_url': self.source_url,
            'artist': self.artist,
            'track': self.track,
            'duration': self.duration,
            'thumbnail': self.thumbnail,
            'confidence': self.confidence,
        }


class VideoResolver(Protocol):
    def resolve(self, artist: str, title: str, duration: int | None = None) -> VideoCandidate | None:
        ...


class VideoCache:
    def __init__(self, directories: list[str], stream_prefix: str = '/video/local', audio_analyzer: VideoAudioAnalyzer | None = None):
        self.directories = [Path(path) for path in directories]
        self.stream_prefix = stream_prefix.rstrip('/')
        self.audio_analyzer = audio_analyzer or VideoAudioAnalyzer()

    @property
    def primary_directory(self) -> Path:
        return self.directories[0] if self.directories else Path('server/local_videos')

    def locate(self, artist: str, title: str, duration: int | None = None) -> dict[str, Any] | None:
        input_artist = normalize(artist)
        input_title = normalize(title)
        best_match = self._best_local_match(input_artist, input_title)
        if best_match is None:
            return None

        score, root, path = best_match
        return self.video_result(path, root, artist, title, duration, score)

    def _best_local_match(self, input_artist: str, input_title: str) -> tuple[float, Path, Path] | None:
        best_match: tuple[float, Path, Path] | None = None

        for root in self.directories:
            for path in self._video_files(root):
                score = self._score(input_artist, input_title, path.stem)
                if score < 0.55:
                    continue
                if best_match is None or score > best_match[0]:
                    best_match = (score, root, path)
        return best_match

    def _video_files(self, root: Path):
        if not root.is_dir():
            return
        for path in root.rglob('*'):
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                yield path

    def video_result(
        self,
        path: Path,
        root: Path | None,
        artist: str,
        title: str,
        duration: int | str | None,
        confidence: float | None = None,
    ) -> dict[str, Any]:
        root = root or self._owning_root(path) or self.primary_directory
        relative_path = path.relative_to(root).as_posix()
        offset_seconds = self.audio_analyzer.intro_silence_offset(path)
        return {
            'video_id': relative_path,
            'provider': 'local',
            'provider_id': relative_path,
            'title': path.stem,
            'channel': 'Local video library',
            'thumbnail': None,
            'duration': duration,
            'url': f'{self.stream_prefix}/{relative_path}',
            'confidence': round(confidence, 2) if confidence is not None else None,
            'offset_seconds': offset_seconds,
            'offset_parts': seconds_to_parts(offset_seconds),
            'offset_source': 'audio_intro_detect' if offset_seconds else 'none',
            'artist': artist,
            'track': title,
        }

    def acquisition_path(self, artist: str, title: str, provider_id: str) -> Path:
        self.primary_directory.mkdir(parents=True, exist_ok=True)
        slug = slugify(' '.join(part for part in (artist, title, provider_id) if part))
        return self.primary_directory / f'{slug}.%(ext)s'

    def _owning_root(self, path: Path) -> Path | None:
        resolved_path = path.resolve()
        for root in self.directories:
            try:
                resolved_path.relative_to(root.resolve())
                return root
            except ValueError:
                continue
        return None

    def _score(self, input_artist: str, input_title: str, stem: str) -> float:
        stem_words = set(normalize(stem).split())
        title_words = set(input_title.split())
        artist_words = {word for word in input_artist.split() if word not in {'feat', 'ft', 'and', 'the'}}
        if not title_words:
            return 0
        title_score = len(stem_words & title_words) / len(title_words)
        artist_score = len(stem_words & artist_words) / len(artist_words) if artist_words else 0
        return min(1, title_score * 0.75 + artist_score * 0.25)


class VideoOffsetStore:
    def __init__(self, path: str | Path = 'video_offsets.json'):
        self.path = Path(path)

    def preference_for(self, video: Mapping[str, Any], track: Mapping[str, Any] | None = None) -> dict[str, Any]:
        record = self._find_record(video, track)
        return {
            'manual_offset_seconds': self._number(record.get('manual_offset_seconds')) if record else 0,
            'use_detected_offset': bool(record.get('use_detected_offset')) if record and 'use_detected_offset' in record else True,
        }

    def save_preference(
        self,
        video: Mapping[str, Any],
        track: Mapping[str, Any] | None,
        manual_offset_seconds: Any,
        use_detected_offset: Any,
    ) -> dict[str, Any]:
        data = self._read()
        records = data.setdefault('data', [])
        record = self._find_record_in(records, video, track)
        if record is None:
            record = self._new_record(video, track)
            records.append(record)

        record['manual_offset_seconds'] = self._number(manual_offset_seconds)
        record['use_detected_offset'] = bool(use_detected_offset)
        self._write(data)
        return self.preference_for(video, track)

    def apply(self, video: dict[str, Any], track: Mapping[str, Any] | None = None) -> dict[str, Any]:
        preference = self.preference_for(video, track)
        detected_offset = self._number(video.get('offset_seconds'))
        manual_offset = preference['manual_offset_seconds']
        use_detected = preference['use_detected_offset']
        video['detected_offset_seconds'] = detected_offset
        video['manual_offset_seconds'] = manual_offset
        video['use_detected_offset'] = use_detected
        video['effective_offset_seconds'] = (detected_offset if use_detected else 0) + manual_offset
        return video

    def _find_record(self, video: Mapping[str, Any], track: Mapping[str, Any] | None) -> dict[str, Any] | None:
        return self._find_record_in(self._read().get('data') or [], video, track)

    def _find_record_in(
        self,
        records: list[Any],
        video: Mapping[str, Any],
        track: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        video_id = str(video.get('video_id') or video.get('provider_id') or '')
        for record in records:
            if isinstance(record, dict) and video_id and record.get('video_id') == video_id:
                return record

        normalized_title = normalize(track.get('title') if track else video.get('track') or video.get('title'))
        normalized_artist = normalize(track.get('artist') if track else video.get('artist'))
        for record in records:
            if not isinstance(record, dict):
                continue
            record_title = normalize(record.get('title'))
            record_artist = normalize(self._record_artist(record.get('artist')))
            if normalized_title and normalized_artist and record_title == normalized_title and record_artist == normalized_artist:
                return record
        return None

    def _new_record(self, video: Mapping[str, Any], track: Mapping[str, Any] | None) -> dict[str, Any]:
        return {
            'video_id': video.get('video_id') or video.get('provider_id'),
            'provider': video.get('provider'),
            'title': track.get('title') if track else video.get('track') or video.get('title'),
            'artist': track.get('artist') if track else video.get('artist'),
            'alias': '',
            'videos_offsets': [0, 0, 0],
        }

    def _read(self) -> dict[str, Any]:
        try:
            with self.path.open('r', encoding='utf-8') as offset_file:
                data = json.load(offset_file)
        except (OSError, json.JSONDecodeError):
            return {'data': []}
        return data if isinstance(data, dict) else {'data': []}

    def _write(self, data: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('w', encoding='utf-8') as offset_file:
            json.dump(data, offset_file, indent=3, ensure_ascii=False)

    def _record_artist(self, artist: Any) -> str:
        if isinstance(artist, list):
            return ', '.join(str(value) for value in artist)
        return str(artist or '')

    def _number(self, value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0


class YouTubeVideoResolver:
    def __init__(self, youtube_search_service):
        self.youtube_search_service = youtube_search_service
        self._candidate_cache: dict[str, VideoCandidate | None] = {}

    def resolve(self, artist: str, title: str, duration: int | None = None) -> VideoCandidate | None:
        cache_key = f'{normalize(artist)}::{normalize(title)}'
        if cache_key in self._candidate_cache:
            return self._candidate_cache[cache_key]

        candidates = self.youtube_search_service._search_youtube(artist, title)
        selected = self.youtube_search_service._select_youtube_video(artist, title, candidates)
        if not selected:
            self._candidate_cache[cache_key] = None
            return None

        snippet = selected.get('snippet') or {}
        youtube_id = selected.get('id', {}).get('videoId')
        if not youtube_id:
            self._candidate_cache[cache_key] = None
            return None

        thumbnails = snippet.get('thumbnails') or {}
        thumbnail = (
            thumbnails.get('maxres', {}).get('url')
            or thumbnails.get('high', {}).get('url')
            or thumbnails.get('medium', {}).get('url')
            or thumbnails.get('default', {}).get('url')
        )

        candidate = VideoCandidate(
            provider='youtube',
            provider_id=str(youtube_id),
            title=str(snippet.get('title') or title),
            channel=str(snippet.get('channelTitle') or artist),
            source_url=f'https://www.youtube.com/watch?v={youtube_id}',
            artist=artist,
            track=title,
            duration=selected.get('_duration') or duration,
            thumbnail=thumbnail,
            confidence=selected.get('_confidence'),
        )
        self._candidate_cache[cache_key] = candidate
        return VideoCandidate(
            provider=candidate.provider,
            provider_id=candidate.provider_id,
            title=candidate.title,
            channel=candidate.channel,
            source_url=candidate.source_url,
            artist=candidate.artist,
            track=candidate.track,
            duration=candidate.duration,
            thumbnail=candidate.thumbnail,
            confidence=candidate.confidence,
        )


class YtDlpAcquisitionProvider:
    def __init__(self, executable: str = 'yt-dlp', timeout_seconds: int = 900):
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def download(self, candidate: VideoCandidate, output_template: Path) -> Path:
        command = [
            self.executable,
            '--no-playlist',
            '--restrict-filenames',
            '-f',
            'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b',
            '--merge-output-format',
            'mp4',
            '-o',
            str(output_template),
            candidate.source_url,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=self.timeout_seconds, check=False)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or 'yt-dlp failed').strip()
            raise RuntimeError(detail[-1000:])

        stem = output_template.name.replace('.%(ext)s', '')
        matches = sorted(output_template.parent.glob(f'{stem}.*'), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in matches:
            if path.suffix.lower() in VIDEO_EXTENSIONS and path.is_file():
                return path
        raise RuntimeError('yt-dlp completed but no playable video file was created')


class VideoLibraryService:
    def __init__(self, cache: VideoCache, resolvers: list[VideoResolver], acquisition_provider: YtDlpAcquisitionProvider | None = None):
        self.cache = cache
        self.resolvers = resolvers
        self.acquisition_provider = acquisition_provider

    def resolve(
        self,
        release: Mapping[str, Any] | None = None,
        track: Mapping[str, Any] | None = None,
        artist: str | None = None,
        title: str | None = None,
        duration: int | None = None,
    ) -> dict[str, Any]:
        artist, title = track_identity(release=release, track=track, artist=artist, title=title)
        if not title:
            return missing_video_result(NO_CURRENT_TRACK_MESSAGE)

        local_video = self.cache.locate(artist, title, duration)
        if local_video:
            return {'video': local_video, 'candidate': None, 'can_download': False, 'message': None}

        candidate = self._candidate(artist, title, duration)
        return {
            'video': None,
            'candidate': candidate.to_dict() if candidate else None,
            'can_download': candidate is not None and self.acquisition_provider is not None,
            'message': 'Local video file is missing.' if candidate else 'No acquisition candidate found.',
        }

    def download(
        self,
        release: Mapping[str, Any] | None = None,
        track: Mapping[str, Any] | None = None,
        artist: str | None = None,
        title: str | None = None,
        duration: int | None = None,
    ) -> dict[str, Any]:
        if self.acquisition_provider is None:
            return {'video': None, 'candidate': None, 'can_download': False, 'message': 'Video acquisition is not configured.'}

        artist, title = track_identity(release=release, track=track, artist=artist, title=title)
        if not title:
            return missing_video_result(NO_CURRENT_TRACK_MESSAGE)

        local_video = self.cache.locate(artist, title, duration)
        if local_video:
            return {'video': local_video, 'candidate': None, 'can_download': False, 'message': None}

        candidate = self._candidate(artist, title, duration)
        if candidate is None:
            return {'video': None, 'candidate': None, 'can_download': False, 'message': 'No acquisition candidate found.'}

        output_template = self.cache.acquisition_path(artist, title, candidate.provider_id)
        path = self.acquisition_provider.download(candidate, output_template)
        video = self.cache.video_result(path, None, artist, title, candidate.duration, candidate.confidence)
        return {'video': video, 'candidate': candidate.to_dict(), 'can_download': False, 'message': None}

    def _candidate(self, artist: str, title: str, duration: int | None = None) -> VideoCandidate | None:
        for resolver in self.resolvers:
            candidate = resolver.resolve(artist, title, duration)
            if candidate:
                return candidate
        return None


class VideoSyncService:
    def __init__(self, video_library_service: VideoLibraryService, playback_runtime, offset_store: VideoOffsetStore | None = None):
        self.video_library_service = video_library_service
        self.playback_runtime = playback_runtime
        self.offset_store = offset_store or VideoOffsetStore()

    def current_state(self) -> dict[str, Any]:
        return self.sync_state(self.playback_runtime.status())

    def download_current(self) -> dict[str, Any]:
        status = self.playback_runtime.status()
        track = status.get('current_track')
        result = self.video_library_service.download(track=track) if isinstance(track, Mapping) else missing_video_result(NO_CURRENT_TRACK_MESSAGE)
        return self._with_playback(result, status)

    def sync_state(self, playback_status: Mapping[str, Any]) -> dict[str, Any]:
        track = playback_status.get('current_track')
        result = self.video_library_service.resolve(track=track) if isinstance(track, Mapping) else missing_video_result(NO_CURRENT_TRACK_MESSAGE)
        return self._with_playback(result, playback_status)

    def save_current_offset_preference(self, manual_offset_seconds: Any, use_detected_offset: Any) -> dict[str, Any]:
        status = self.playback_runtime.status()
        track = status.get('current_track')
        result = self.video_library_service.resolve(track=track) if isinstance(track, Mapping) else missing_video_result(NO_CURRENT_TRACK_MESSAGE)
        video = result.get('video')
        if not isinstance(video, Mapping):
            raise ValueError(NO_CURRENT_TRACK_MESSAGE)
        self.offset_store.save_preference(video, track if isinstance(track, Mapping) else None, manual_offset_seconds, use_detected_offset)
        refreshed = self.video_library_service.resolve(track=track)
        return self._with_playback(refreshed, status)

    def _with_playback(self, result: dict[str, Any], playback_status: Mapping[str, Any]) -> dict[str, Any]:
        video = result.get('video')
        elapsed = int(float(playback_status.get('elapsed') or 0))
        playback_state = playback_status.get('playback_state') or 'idle'
        track = playback_status.get('current_track')
        if isinstance(video, dict):
            self.offset_store.apply(video, track if isinstance(track, Mapping) else None)
        offset_seconds = float(video.get('effective_offset_seconds') or 0) if video else 0
        return {
            **result,
            'playback_state': playback_state,
            'seek_seconds': max(0, elapsed + offset_seconds),
            'should_play': playback_state == 'playing' and video is not None,
            'should_pause': playback_state in ('paused', 'stopped', 'idle', 'preparing', 'error'),
            'source': 'playback_session',
        }


def track_identity(
    release: Mapping[str, Any] | None,
    track: Mapping[str, Any] | None,
    artist: str | None,
    title: str | None,
) -> tuple[str, str]:
    if track:
        title = title or str(track.get('title') or '')
        artist = artist or str(track.get('artist') or '')
        if not artist and track.get('artists'):
            artists = track.get('artists') or []
            artist = ', '.join(item.get('name', '') for item in artists if isinstance(item, Mapping))
    if release:
        artist = artist or str(release.get('artists_sort') or '')
    return str(artist or '').strip(), str(title or '').strip()


def normalize(value: Any) -> str:
    text = str(value or '').lower()
    text = re.sub(r'\([^)]*\)|\[[^]]*\]', ' ', text)
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def slugify(value: str) -> str:
    slug = normalize(value).replace(' ', '-')
    return slug[:180] or 'video'


def missing_video_result(message: str) -> dict[str, Any]:
    return {'video': None, 'candidate': None, 'can_download': False, 'message': message}


def seconds_to_parts(seconds: int) -> list[int]:
    safe_seconds = max(0, int(seconds))
    hours = safe_seconds // 3600
    minutes = (safe_seconds % 3600) // 60
    remainder = safe_seconds % 60
    return [hours, minutes, remainder]