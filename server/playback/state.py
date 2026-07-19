from dataclasses import dataclass, field
import time
from typing import Any, Mapping


PLAYBACK_IDLE = 'idle'
PLAYBACK_PLAYING = 'playing'
PLAYBACK_PAUSED = 'paused'
PLAYBACK_STOPPED = 'stopped'
PLAYBACK_PREPARING = 'preparing'
PLAYBACK_ERROR = 'error'


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
    error: str | None = None

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
            'error': self.error,
        }


def track_value(track: Any, name: str):
    if track is None:
        return None
    if isinstance(track, Mapping):
        return track.get(name)
    return getattr(track, name, None)