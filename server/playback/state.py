from dataclasses import dataclass, field
import time
from typing import Any, Mapping


PLAYBACK_IDLE = 'idle'
PLAYBACK_PLAYING = 'playing'
PLAYBACK_PAUSED = 'paused'
PLAYBACK_STOPPED = 'stopped'
PLAYBACK_PREPARING = 'preparing'
PLAYBACK_ERROR = 'error'

REPEAT_OFF = 'off'
REPEAT_ONE = 'one'
REPEAT_ALL = 'all'


@dataclass
class PlaybackState:
    current_track: Any = None
    current_playlist: str | None = None
    queue: list[Any] = field(default_factory=list)
    current_index: int = -1
    elapsed: int = 0
    duration: int = 0
    remaining: int = 0
    progress: float = 0
    current_deck: Any = None
    current_cd: Any = None
    playback_state: str = PLAYBACK_IDLE
    last_update_timestamp: float = field(default_factory=time.time)
    started_at: float | None = None
    paused_elapsed: int = 0
    load_delay_seconds: float = 0
    load_delay_remaining: float = 0
    mechanical_state: str = 'unknown'
    hardware_ready: bool = False
    display_disc: Any = None
    loaded_disc: Any = None
    door_open: bool = False
    power_state: str = 'unknown'
    model: Any = None
    player_status_raw: Any = None
    last_hardware_event: str | None = None
    error: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    shuffle: bool = False
    repeat: str = REPEAT_OFF

    @classmethod
    def idle(cls, playback_state: str = PLAYBACK_IDLE) -> 'PlaybackState':
        return cls(playback_state=playback_state)

    def mark_updated(self):
        self.last_update_timestamp = time.time()

    def snapshot(self) -> dict[str, Any]:
        return {
            'current_track': self.current_track,
            'current_playlist': self.current_playlist,
            'queue': list(self.queue),
            'upcoming': list(self.queue[self.current_index + 1:]),
            'elapsed': self.elapsed,
            'duration': self.duration,
            'remaining': self.remaining,
            'progress': self.progress,
            'current_deck': self.current_deck,
            'current_cd': self.current_cd,
            'playback_state': self.playback_state,
            'last_update_timestamp': self.last_update_timestamp,
            'load_delay_seconds': self.load_delay_seconds,
            'load_delay_remaining': self.load_delay_remaining,
            'mechanical_state': self.mechanical_state,
            'hardware_ready': self.hardware_ready,
            'display_disc': self.display_disc,
            'loaded_disc': self.loaded_disc,
            'door_open': self.door_open,
            'power_state': self.power_state,
            'model': self.model,
            'player_status_raw': self.player_status_raw,
            'last_hardware_event': self.last_hardware_event,
            'error': self.error,
            'recent_history': list(self.history[-20:]),
            'shuffle': self.shuffle,
            'repeat': self.repeat,
            'queue_stats': self._queue_stats(),
        }

    def _queue_stats(self) -> dict[str, Any]:
        tracks = self.queue
        if not tracks:
            return {
                'track_count': 0,
                'total_duration_seconds': 0,
                'unique_artists': 0,
                'unique_releases': 0,
            }
        artists = set()
        releases = set()
        total_seconds = 0
        for t in tracks:
            artist = track_value(t, 'artist') or track_value(t, 'full_name') or ''
            if artist:
                artists.add(artist)
            release_id = track_value(t, 'release_id')
            if release_id:
                releases.add(release_id)
            dur = track_value(t, 'duration') or ''
            total_seconds += _duration_to_seconds(dur)
        return {
            'track_count': len(tracks),
            'total_duration_seconds': total_seconds,
            'unique_artists': len(artists),
            'unique_releases': len(releases),
        }


def track_value(track: Any, name: str):
    if track is None:
        return None
    if isinstance(track, Mapping):
        return track.get(name)
    return getattr(track, name, None)


def _duration_to_seconds(duration_str: str) -> int:
    """Convert 'MM:SS' or 'HH:MM:SS' duration string to total seconds."""
    if not duration_str:
        return 0
    parts = str(duration_str).strip().split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(parts[0])
    except (ValueError, TypeError):
        return 0