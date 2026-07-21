import importlib.util
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable, Mapping

try:
    from playback.scheduler import PlaybackScheduler
    from sony.slink import SLinkClient, duration_to_seconds
    from playback.queue import PlaybackQueue
    from playback.state import (
        PLAYBACK_PAUSED,
        PLAYBACK_PLAYING,
        PLAYBACK_PREPARING,
        PLAYBACK_STOPPED,
        PLAYBACK_ERROR,
        PlaybackState,
        track_value,
    )
except ImportError:
    from server.playback.scheduler import PlaybackScheduler
    from server.sony.slink import SLinkClient, duration_to_seconds
    from server.playback.queue import PlaybackQueue
    from server.playback.state import (
        PLAYBACK_PAUSED,
        PLAYBACK_PLAYING,
        PLAYBACK_PREPARING,
        PLAYBACK_STOPPED,
        PLAYBACK_ERROR,
        PlaybackState,
        track_value,
    )

try:
    from server.websocket.events import (
        EventHub,
        PLAYBACK_PAUSED as EVENT_PLAYBACK_PAUSED,
        PLAYBACK_STARTED as EVENT_PLAYBACK_STARTED,
        PLAYBACK_STOPPED as EVENT_PLAYBACK_STOPPED,
        PLAYBACK_ERROR as EVENT_PLAYBACK_ERROR,
        PLAYLIST_CHANGED as EVENT_PLAYLIST_CHANGED,
        PROGRESS_TICK as EVENT_PROGRESS_TICK,
        QUEUE_CHANGED as EVENT_QUEUE_CHANGED,
    )
except ImportError:
    events_path = Path(__file__).resolve().parents[1] / 'websocket' / 'events.py'
    events_spec = importlib.util.spec_from_file_location('discogs_runtime_events', events_path)
    events_module = importlib.util.module_from_spec(events_spec)
    events_spec.loader.exec_module(events_module)
    EventHub = events_module.EventHub
    EVENT_PLAYBACK_PAUSED = events_module.PLAYBACK_PAUSED
    EVENT_PLAYBACK_STARTED = events_module.PLAYBACK_STARTED
    EVENT_PLAYBACK_STOPPED = events_module.PLAYBACK_STOPPED
    EVENT_PLAYBACK_ERROR = events_module.PLAYBACK_ERROR
    EVENT_PLAYLIST_CHANGED = events_module.PLAYLIST_CHANGED
    EVENT_PROGRESS_TICK = events_module.PROGRESS_TICK
    EVENT_QUEUE_CHANGED = events_module.QUEUE_CHANGED


HARDWARE_SYNC_LIVE = 'live'
HARDWARE_SYNC_RESTORED_UNVERIFIED = 'restored_unverified'


class PlaybackRuntime:
    def __init__(
        self,
        slink_client: SLinkClient,
        advance_lead_seconds: int = 3,
        event_hub: EventHub | None = None,
        changer_slots: int = 300,
        changer_load_base_seconds: float = 4,
        changer_load_seconds_per_slot: float = 0.08,
        changer_load_max_seconds: float = 35,
        playback_start_offset_seconds: float = 2,
        continuous_status_settle_seconds: float = 0.25,
        persistence_path: str | Path | None = None,
        adjacent_track_resolver: Callable[[Any, str], Any | None] | None = None,
        changer_initial_deck: Any = None,
        changer_initial_cd: Any = None,
    ):
        self.slink_client = slink_client
        self.advance_lead_seconds = advance_lead_seconds
        self.changer_slots = changer_slots
        self.changer_load_base_seconds = changer_load_base_seconds
        self.changer_load_seconds_per_slot = changer_load_seconds_per_slot
        self.changer_load_max_seconds = changer_load_max_seconds
        self.playback_start_offset_seconds = playback_start_offset_seconds
        self.playback_start_delay_enabled = True
        self.continuous_status_settle_seconds = continuous_status_settle_seconds
        self.persistence_path = Path(persistence_path) if persistence_path else None
        self.adjacent_track_resolver = adjacent_track_resolver
        self.event_hub = event_hub or EventHub()
        self.queue_manager = PlaybackQueue()
        self._last_requested_deck = changer_initial_deck
        self._last_requested_cd = changer_initial_cd
        self._continuous_status_enabled_decks = set()
        self._hardware_sync_state = HARDWARE_SYNC_LIVE
        self._hardware_state_source = 'startup'
        self._lock = threading.RLock()
        self._state = self._load_persisted_state() or PlaybackState.idle()
        self._scheduler = PlaybackScheduler(
            self._lock,
            self._is_playing_locked,
            self._scheduler_progress_tick_locked,
            self._should_advance_locked,
            self._advance_locked,
        )
        self._stop_event = self._scheduler.stop_event
        self._scheduler.start()

    def shutdown(self):
        self._scheduler.stop()

    def play_playlist(self, playlist: Mapping[str, Any]) -> dict[str, Any]:
        tracks = list(playlist.get('tracks', []))
        if not tracks:
            raise ValueError("Playlist has no tracks")

        with self._lock:
            self._state = PlaybackState.idle()
            self.queue_manager.replace_playlist(self._state, playlist)
            self._start_current_track_locked()
            self._publish_locked(EVENT_PLAYLIST_CHANGED)
            self._publish_locked(EVENT_QUEUE_CHANGED)
            self._publish_locked(EVENT_PLAYBACK_STARTED)
            return self.status_locked()

    def play_track(self, track: Any) -> dict[str, Any]:
        with self._lock:
            self._state = PlaybackState.idle()
            self.queue_manager.replace_track(self._state, track)
            self._start_current_track_locked()
            self._publish_locked(EVENT_QUEUE_CHANGED)
            self._publish_locked(EVENT_PLAYBACK_STARTED)
            return self.status_locked()

    def observe_track(self, track: Any) -> dict[str, Any]:
        with self._lock:
            self._mark_hardware_synced_locked('track_status')
            if self._is_observed_current_track_locked(track):
                if self._state.playback_state == PLAYBACK_PAUSED:
                    self.resume(send_hardware=False)
                elif self._state.playback_state != PLAYBACK_PLAYING:
                    self._state.current_track = track
                    self._state.duration = duration_to_seconds(track_value(track, 'duration') or '')
                    self._state.current_deck = track_value(track, 'deck_number')
                    self._state.current_cd = track_value(track, 'cd_position')
                    self._state.started_at = time.monotonic() + self._playback_start_delay_seconds()
                    self._state.playback_state = PLAYBACK_PLAYING
                    self._state.load_delay_seconds = 0
                    self._state.load_delay_remaining = 0
                    self._normalize_progress_locked()
                    self._state.mark_updated()
                    self._publish_locked(EVENT_PLAYBACK_STARTED)
                return self.status_locked()

            matching_index = self._queue_index_for_track_locked(track)
            if matching_index is None:
                self.queue_manager.replace_track(self._state, track)
            else:
                self._state.current_index = matching_index

            duration = duration_to_seconds(track_value(track, 'duration') or '')
            self._state.current_track = track
            self._state.duration = duration
            self._state.elapsed = 0
            self._state.remaining = duration
            self._state.progress = 0
            self._state.current_deck = track_value(track, 'deck_number')
            self._state.current_cd = track_value(track, 'cd_position')
            self._state.started_at = time.monotonic() + self._playback_start_delay_seconds()
            self._state.paused_elapsed = 0
            self._state.load_delay_seconds = 0
            self._state.load_delay_remaining = 0
            self._state.playback_state = PLAYBACK_PLAYING
            self._state.error = None
            self._last_requested_deck = self._state.current_deck
            self._last_requested_cd = self._state.current_cd
            self._state.mark_updated()
            self._publish_locked(EVENT_QUEUE_CHANGED)
            self._publish_locked(EVENT_PLAYBACK_STARTED)
            return self.status_locked()

    def pause(self, send_hardware: bool = True) -> dict[str, Any]:
        with self._lock:
            if send_hardware:
                self._send_transport_command_locked('pause')
            if self._state.playback_state == PLAYBACK_PLAYING:
                self._update_progress_locked()
                self._state.paused_elapsed = self._state.elapsed
                self._state.playback_state = PLAYBACK_PAUSED
                self._state.mark_updated()
                self._publish_locked(EVENT_PLAYBACK_PAUSED)
            return self.status_locked()

    def stop(self, send_hardware: bool = True) -> dict[str, Any]:
        with self._lock:
            if send_hardware:
                self._send_transport_command_locked('stop')
            if self._state.current_track:
                self._update_progress_locked()
                self._state.playback_state = PLAYBACK_STOPPED
                self._state.started_at = None
                self._state.elapsed = 0
                self._state.remaining = self._state.duration
                self._state.progress = 0
                self._state.paused_elapsed = 0
                self._state.load_delay_seconds = 0
                self._state.load_delay_remaining = 0
                self._state.mark_updated()
            else:
                self._state = PlaybackState.idle(PLAYBACK_STOPPED)
            self._publish_locked(EVENT_PLAYBACK_STOPPED)
            return self.status_locked()

    def next_track(self, send_hardware: bool = True) -> dict[str, Any]:
        with self._lock:
            if send_hardware:
                self._send_transport_command_locked('next_track')
            self._move_adjacent_locked('next')
            return self.status_locked()

    def previous_track(self, send_hardware: bool = True) -> dict[str, Any]:
        with self._lock:
            if send_hardware:
                self._send_previous_track_command_locked()
            self._move_adjacent_locked('previous')
            return self.status_locked()

    def resume(self, send_hardware: bool = True) -> dict[str, Any]:
        with self._lock:
            if self._state.playback_state != PLAYBACK_PAUSED or not self._state.current_track:
                return self.status_locked()

            if send_hardware:
                self._send_transport_command_locked('resume')
            self._mark_playing_locked(self._state.paused_elapsed)
            return self.status_locked()

    def handle_transport_status(self, status: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        normalized_status = (status or '').upper()
        if normalized_status == 'STOP':
            with self._lock:
                self._mark_hardware_synced_locked('stop')
            return self.stop(send_hardware=False)
        if normalized_status in {'PAUSE', 'PAUSE_TOGGLE'}:
            with self._lock:
                self._mark_hardware_synced_locked(normalized_status.lower())
            return self.pause(send_hardware=False)
        if normalized_status == 'EJECT':
            with self._lock:
                self._mark_hardware_synced_locked('eject')
            return self.stop(send_hardware=False)
        if normalized_status == 'PLAY':
            with self._lock:
                self._mark_hardware_synced_locked('play')
            return self._observe_playing_status()
        if normalized_status == 'NEXT_TRACK':
            with self._lock:
                self._mark_hardware_synced_locked('next_track')
            return self.next_track(send_hardware=False)
        if normalized_status == 'PREV_TRACK':
            with self._lock:
                self._mark_hardware_synced_locked('prev_track')
            return self.previous_track(send_hardware=False)
        if normalized_status == 'NEXT_TRACK_IN':
            with self._lock:
                self._mark_hardware_synced_locked('next_track_in')
            return self.sync_track_ending(payload or {})
        if normalized_status in {
            'CAROUSEL_MOVING',
            'READY',
            'DOOR_OPEN',
            'POWER_ON',
            'POWER_OFF',
            'DISPLAY_DISC',
            'LOADING_DISC',
            'DISC_LOADED',
            'MODEL_ID',
            'PLAYER_STATUS',
            'UNKNOWN_STATUS',
        }:
            return self.handle_hardware_status(normalized_status, payload or {})
        return self.status()

    def handle_hardware_status(self, status: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._mark_hardware_synced_locked(status.lower())
            self._state.last_hardware_event = status
            if status == 'CAROUSEL_MOVING':
                self._state.mechanical_state = 'carousel_moving'
                self._state.hardware_ready = False
            elif status == 'READY':
                self._state.mechanical_state = 'ready'
                self._state.hardware_ready = True
            elif status == 'DOOR_OPEN':
                self._state.door_open = True
                self._state.hardware_ready = False
                self._state.mechanical_state = 'door_open'
            elif status == 'POWER_ON':
                self._state.power_state = 'on'
            elif status == 'POWER_OFF':
                self._state.power_state = 'off'
                self._state.hardware_ready = False
                self._state.mechanical_state = 'powered_off'
                self.stop(send_hardware=False)
            elif status == 'DISPLAY_DISC':
                self._state.display_disc = self._disc_payload_value(payload)
            elif status == 'LOADING_DISC':
                self._state.display_disc = self._disc_payload_value(payload)
                self._state.mechanical_state = 'loading_disc'
                self._state.hardware_ready = False
            elif status == 'DISC_LOADED':
                self._state.loaded_disc = self._disc_payload_value(payload)
                self._state.mechanical_state = 'disc_loaded'
            elif status == 'MODEL_ID':
                self._state.model = payload.get('model') or payload.get('raw') or payload
            elif status == 'PLAYER_STATUS':
                self._state.player_status_raw = payload.get('raw') or payload
            elif status == 'UNKNOWN_STATUS':
                self._state.player_status_raw = payload.get('raw') or payload
            self._state.mark_updated()
            self._publish_locked(EVENT_PROGRESS_TICK)
            return self.status_locked()

    def request_resync(self) -> dict[str, Any]:
        with self._lock:
            self._hardware_sync_state = HARDWARE_SYNC_RESTORED_UNVERIFIED
            self._hardware_state_source = 'manual_resync'
            self._state.hardware_ready = False
            self._state.mechanical_state = 'resync_requested'
            self._state.mark_updated()
            self._send_enable_continuous_status_locked(self._current_deck_number_locked())
            self._publish_locked(EVENT_PROGRESS_TICK)
            return self.status_locked()

    def set_continuous_status_enabled(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            deck_number = self._current_deck_number_locked()
            if enabled:
                self._send_enable_continuous_status_locked(deck_number)
            else:
                self.slink_client.send_disable_continuous_status(deck_number)
                self._continuous_status_enabled_decks.discard(deck_number)
            self._state.mark_updated()
            self._publish_locked(EVENT_PROGRESS_TICK)
            return self.status_locked()

    def sync_track_ending(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            if self._state.playback_state != PLAYBACK_PLAYING or not self._state.duration:
                return self.status_locked()

            try:
                remaining = int(float(payload.get('duration', 30)))
            except (TypeError, ValueError):
                remaining = 30

            remaining = max(0, min(remaining, self._state.duration))
            elapsed = self._state.duration - remaining
            self._state.started_at = time.monotonic() - elapsed
            self._state.load_delay_remaining = 0
            self._state.elapsed = elapsed
            self._state.remaining = remaining
            self._state.progress = round((elapsed / self._state.duration) * 100, 2)
            self._state.mark_updated()
            self._publish_locked(EVENT_PROGRESS_TICK)
            return self.status_locked()

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._update_progress_locked()
            return self.status_locked()

    def progress(self) -> dict[str, Any]:
        status = self.status()
        return {
            'elapsed': status['elapsed'],
            'duration': status['duration'],
            'remaining': status['remaining'],
            'progress': status['progress'],
            'playback_state': status['playback_state'],
        }

    def set_playback_start_delay_enabled(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            old_delay = self._playback_start_delay_seconds()
            self.playback_start_delay_enabled = bool(enabled)
            new_delay = self._playback_start_delay_seconds()
            if self._state.playback_state == PLAYBACK_PLAYING and self._state.started_at is not None:
                self._state.started_at += new_delay - old_delay
            self._update_progress_locked()
            self._state.mark_updated()
            self._persist_locked()
            self._publish_locked(EVENT_PROGRESS_TICK)
            return self.status_locked()

    def queue(self) -> dict[str, Any]:
        status = self.status()
        return {
            'current_track': status['current_track'],
            'queue': status['queue'],
            'upcoming': status['upcoming'],
            'current_playlist': status['current_playlist'],
            'playback_state': status['playback_state'],
        }

    def status_locked(self) -> dict[str, Any]:
        return {
            **self._state.snapshot(),
            'playback_start_delay_seconds': self._playback_start_delay_seconds(),
            'playback_start_delay_enabled': self.playback_start_delay_enabled,
            'hardware_sync_state': self._hardware_sync_state,
            'hardware_state_verified': self._hardware_sync_state == HARDWARE_SYNC_LIVE,
            'hardware_state_source': self._hardware_state_source,
        }

    def _mark_hardware_synced_locked(self, source: str):
        self._hardware_sync_state = HARDWARE_SYNC_LIVE
        self._hardware_state_source = source

    def _payload_value(self, payload: Mapping[str, Any], name: str):
        value = payload.get(name)
        if value is None:
            return None
        try:
            return int(str(value), 16)
        except (TypeError, ValueError):
            return value

    def _disc_payload_value(self, payload: Mapping[str, Any]):
        return payload.get('decoded_disc') or self._payload_value(payload, 'disc')

    def _playback_start_delay_seconds(self) -> float:
        return self.playback_start_offset_seconds if self.playback_start_delay_enabled else 0

    def _observe_playing_status(self) -> dict[str, Any]:
        with self._lock:
            if self._state.playback_state == PLAYBACK_PREPARING:
                self._state.mark_updated()
                self._publish_locked(EVENT_PROGRESS_TICK)
                return self.status_locked()
            if self._state.current_track:
                resume_elapsed = self._state.paused_elapsed if self._state.playback_state == PLAYBACK_PAUSED else self._state.elapsed
                self._mark_playing_locked(resume_elapsed)
            return self.status_locked()

    def _mark_playing_locked(self, elapsed: int | float = 0):
        self._state.started_at = time.monotonic() - elapsed
        self._state.playback_state = PLAYBACK_PLAYING
        self._state.load_delay_seconds = 0
        self._state.load_delay_remaining = 0
        self._normalize_progress_locked()
        self._state.mark_updated()
        self._publish_locked(EVENT_PLAYBACK_STARTED)

    def _is_playing_locked(self) -> bool:
        return self._state.playback_state == PLAYBACK_PLAYING

    def _should_advance_locked(self) -> bool:
        return bool(self._state.duration and self._state.remaining <= self.advance_lead_seconds)

    def _scheduler_progress_tick_locked(self):
        self._update_progress_locked()
        self._publish_locked(EVENT_PROGRESS_TICK)

    def _start_current_track_locked(self, send_hardware: bool = True):
        track = self.queue_manager.current(self._state)
        if track is None:
            self._state = PlaybackState.idle(PLAYBACK_STOPPED)
            return

        self._state.playback_state = PLAYBACK_PREPARING
        self._state.mark_updated()
        try:
            if send_hardware:
                self._ensure_continuous_status_locked(track_value(track, 'deck_number'))
                self.slink_client.send_track(track)
            duration = duration_to_seconds(track_value(track, 'duration') or '')
        except Exception as exc:
            self._state.playback_state = PLAYBACK_ERROR
            self._state.error = str(exc)
            self._state.mark_updated()
            self._publish_locked(EVENT_PLAYBACK_ERROR)
            raise

        target_deck = track_value(track, 'deck_number')
        target_cd = track_value(track, 'cd_position')

        self._state.current_track = track
        self._state.duration = duration
        self._state.elapsed = 0
        self._state.remaining = duration
        self._state.progress = 0
        self._state.current_deck = target_deck
        self._state.current_cd = target_cd
        self._state.started_at = None
        self._state.paused_elapsed = 0
        self._state.load_delay_seconds = 0
        self._state.load_delay_remaining = 0
        self._state.playback_state = PLAYBACK_PREPARING
        self._state.error = None
        self._last_requested_deck = target_deck
        self._last_requested_cd = target_cd
        self._state.mark_updated()

    def _advance_locked(self, send_hardware: bool = True):
        if not self.queue_manager.advance(self._state):
            adjacent_track = self._resolve_adjacent_track_locked('next')
            if adjacent_track is not None:
                self._set_current_track_from_metadata_locked(adjacent_track)
                self._publish_locked(EVENT_QUEUE_CHANGED)
                self._publish_locked(EVENT_PLAYBACK_STARTED)
                return

            self._state.playback_state = PLAYBACK_STOPPED
            self._state.elapsed = self._state.duration
            self._state.remaining = 0
            self._state.progress = 100
            self._state.mark_updated()
            self._publish_locked(EVENT_PLAYBACK_STOPPED)
            return

        self._start_current_track_locked(send_hardware=send_hardware)
        self._publish_locked(EVENT_QUEUE_CHANGED)
        self._publish_locked(EVENT_PLAYBACK_STARTED)

    def _move_adjacent_locked(self, direction: str):
        if direction == 'next' and self.queue_manager.advance(self._state):
            self._start_current_track_locked(send_hardware=False)
            self._publish_locked(EVENT_QUEUE_CHANGED)
            self._publish_locked(EVENT_PLAYBACK_STARTED)
            return
        if direction == 'previous' and self.queue_manager.previous(self._state):
            self._start_current_track_locked(send_hardware=False)
            self._publish_locked(EVENT_QUEUE_CHANGED)
            self._publish_locked(EVENT_PLAYBACK_STARTED)
            return

        adjacent_track = self._resolve_adjacent_track_locked(direction)
        if adjacent_track is None:
            self._normalize_progress_locked()
            self._publish_locked(EVENT_QUEUE_CHANGED)
            return

        self._set_current_track_from_metadata_locked(adjacent_track)
        self._publish_locked(EVENT_QUEUE_CHANGED)
        if self._state.playback_state == PLAYBACK_PLAYING:
            self._publish_locked(EVENT_PLAYBACK_STARTED)

    def _resolve_adjacent_track_locked(self, direction: str):
        if self.adjacent_track_resolver is None or self._state.current_track is None:
            return None
        return self.adjacent_track_resolver(self._state.current_track, direction)

    def _adjacent_track_locked(self, direction: str):
        if direction == 'previous' and self._state.current_index > 0:
            return self._state.queue[self._state.current_index - 1]
        if direction == 'next' and self._state.current_index + 1 < len(self._state.queue):
            return self._state.queue[self._state.current_index + 1]
        return self._resolve_adjacent_track_locked(direction)

    def _set_current_track_from_metadata_locked(self, track: Any):
        previous_state = self._state.playback_state
        duration = duration_to_seconds(track_value(track, 'duration') or '')
        self.queue_manager.replace_track(self._state, track)
        self._state.current_track = track
        self._state.duration = duration
        self._state.elapsed = 0
        self._state.remaining = duration
        self._state.progress = 0
        self._state.current_deck = track_value(track, 'deck_number')
        self._state.current_cd = track_value(track, 'cd_position')
        self._state.paused_elapsed = 0
        self._state.load_delay_seconds = 0
        self._state.load_delay_remaining = 0
        if previous_state in {PLAYBACK_PLAYING, PLAYBACK_PREPARING}:
            self._state.started_at = time.monotonic() + self._playback_start_delay_seconds()
            self._state.playback_state = PLAYBACK_PLAYING
        else:
            self._state.started_at = None
            self._state.playback_state = previous_state
        self._last_requested_deck = self._state.current_deck
        self._last_requested_cd = self._state.current_cd
        self._state.error = None
        self._state.mark_updated()

    def _update_progress_locked(self):
        if self._state.playback_state != PLAYBACK_PLAYING or self._state.started_at is None:
            self._normalize_progress_locked()
            return

        now = time.monotonic()
        mechanical_ready_at = self._state.started_at - self._playback_start_delay_seconds()
        self._state.load_delay_remaining = max(round(mechanical_ready_at - now, 2), 0)
        elapsed = int(now - self._state.started_at)
        duration = self._state.duration
        self._state.elapsed = max(0, min(elapsed, duration))
        self._state.remaining = max(duration - self._state.elapsed, 0)
        self._state.progress = round((self._state.elapsed / duration) * 100, 2) if duration else 0
        self._state.mark_updated()

    def _normalize_progress_locked(self):
        self._state.elapsed = max(0, min(int(self._state.elapsed or 0), int(self._state.duration or 0)))
        self._state.remaining = max((self._state.duration or 0) - self._state.elapsed, 0)
        self._state.progress = round((self._state.elapsed / self._state.duration) * 100, 2) if self._state.duration else 0

    def _changer_load_delay_seconds(self, target_cd: Any) -> float:
        current_slot = self._changer_slot(self._last_requested_cd)
        target_slot = self._changer_slot(target_cd)
        if current_slot is None or target_slot is None or current_slot == target_slot:
            return 0

        distance = abs(target_slot - current_slot)
        if self.changer_slots > 0:
            distance = min(distance, self.changer_slots - distance % self.changer_slots)
        delay = self.changer_load_base_seconds + (distance * self.changer_load_seconds_per_slot)
        return round(min(delay, self.changer_load_max_seconds), 2)

    def _changer_slot(self, cd_position: Any) -> int | None:
        try:
            cd = int(cd_position)
        except (TypeError, ValueError):
            return None

        return cd

    def _queue_index_for_track_locked(self, track: Any) -> int | None:
        for index, queued_track in enumerate(self._state.queue):
            if self._same_track(queued_track, track):
                return index
        return None

    def _is_observed_current_track_locked(self, track: Any) -> bool:
        return self._same_track(self._state.current_track, track)

    def _same_track(self, left: Any, right: Any) -> bool:
        return bool(
            left
            and right
            and track_value(left, 'deck_number') == track_value(right, 'deck_number')
            and track_value(left, 'cd_position') == track_value(right, 'cd_position')
            and str(track_value(left, 'position')) == str(track_value(right, 'position'))
        )

    def _send_transport_command_locked(self, command_name: str):
        try:
            command = getattr(self.slink_client, f'send_{command_name}')
            command(self._current_deck_number_locked())
        except Exception as exc:
            self._state.playback_state = PLAYBACK_ERROR
            self._state.error = str(exc)
            self._state.mark_updated()
            self._publish_locked(EVENT_PLAYBACK_ERROR)
            raise

    def _send_previous_track_command_locked(self):
        try:
            previous_track = self._adjacent_track_locked('previous')
            if previous_track is not None:
                self.slink_client.send_track(previous_track)
                return
            self.slink_client.send_previous_track(self._current_deck_number_locked())
        except Exception as exc:
            self._state.playback_state = PLAYBACK_ERROR
            self._state.error = str(exc)
            self._state.mark_updated()
            self._publish_locked(EVENT_PLAYBACK_ERROR)
            raise

    def _current_deck_number_locked(self) -> int:
        try:
            return int(self._state.current_deck or 1)
        except (TypeError, ValueError):
            return 1

    def _ensure_continuous_status_locked(self, deck_number: Any):
        try:
            normalized_deck = int(deck_number or 1)
        except (TypeError, ValueError):
            normalized_deck = 1
        if normalized_deck in self._continuous_status_enabled_decks:
            return

        self._send_enable_continuous_status_locked(normalized_deck)

    def _send_enable_continuous_status_locked(self, deck_number: Any):
        try:
            normalized_deck = int(deck_number or 1)
        except (TypeError, ValueError):
            normalized_deck = 1
        self.slink_client.send_enable_continuous_status(normalized_deck)
        self._continuous_status_enabled_decks.add(normalized_deck)
        if getattr(self.slink_client, 'server_url', None):
            time.sleep(self.continuous_status_settle_seconds)

    def _publish_locked(self, event_type: str):
        if event_type != EVENT_PROGRESS_TICK:
            self._persist_locked()
        self.event_hub.publish(event_type, self.status_locked())

    def _persist_locked(self):
        if self.persistence_path is None:
            return

        payload = {
            'snapshot': self.status_locked(),
            'current_index': self._state.current_index,
            'saved_at': time.time(),
        }
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.persistence_path.with_suffix(self.persistence_path.suffix + '.tmp')
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        temp_path.replace(self.persistence_path)

    def _load_persisted_state(self) -> PlaybackState | None:
        if self.persistence_path is None or not self.persistence_path.exists():
            return None

        try:
            payload = json.loads(self.persistence_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return None

        snapshot = payload.get('snapshot', payload)
        self._load_persisted_preferences(snapshot)
        current_track = snapshot.get('current_track')
        queue = list(snapshot.get('queue') or ([] if current_track is None else [current_track]))
        if current_track is None and not queue:
            return None

        state = PlaybackState.idle(PLAYBACK_STOPPED)
        state.current_track = current_track
        state.current_playlist = snapshot.get('current_playlist')
        state.queue = queue
        state.current_index = int(payload.get('current_index', 0 if queue else -1))
        if state.current_index < 0 or state.current_index >= len(state.queue):
            state.current_index = 0 if state.queue else -1
        state.elapsed = int(snapshot.get('elapsed') or 0)
        state.duration = int(snapshot.get('duration') or 0)
        state.remaining = max(state.duration - state.elapsed, 0)
        state.progress = round((state.elapsed / state.duration) * 100, 2) if state.duration else 0
        state.current_deck = snapshot.get('current_deck')
        state.current_cd = snapshot.get('current_cd')
        state.load_delay_seconds = 0
        state.load_delay_remaining = 0
        state.mechanical_state = snapshot.get('mechanical_state') or 'unknown'
        state.hardware_ready = bool(snapshot.get('hardware_ready'))
        state.display_disc = snapshot.get('display_disc')
        state.loaded_disc = snapshot.get('loaded_disc')
        state.door_open = bool(snapshot.get('door_open'))
        state.power_state = snapshot.get('power_state') or 'unknown'
        state.model = snapshot.get('model')
        state.player_status_raw = snapshot.get('player_status_raw')
        state.last_hardware_event = snapshot.get('last_hardware_event')
        state.error = None
        state.mark_updated()
        self._hardware_sync_state = HARDWARE_SYNC_RESTORED_UNVERIFIED
        self._hardware_state_source = 'persisted_snapshot'
        return state

    def _load_persisted_preferences(self, snapshot: Mapping[str, Any]) -> None:
        if 'playback_start_delay_enabled' in snapshot:
            self.playback_start_delay_enabled = bool(snapshot.get('playback_start_delay_enabled'))