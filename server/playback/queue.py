import random
from typing import Any, Mapping

try:
    from playback.state import PlaybackState, REPEAT_ALL, REPEAT_ONE
except ImportError:
    from server.playback.state import PlaybackState, REPEAT_ALL, REPEAT_ONE


class PlaybackQueue:
    """Index-based queue operations on PlaybackState.

    The queue is a flat list with a cursor (current_index). All mutation
    operations keep the cursor pointing at the same logical track whenever
    possible so that edits during playback do not jump playback position.
    """

    # ------------------------------------------------------------------
    # Replacement
    # ------------------------------------------------------------------
    def replace_playlist(self, state: PlaybackState, playlist: Mapping[str, Any]) -> None:
        state.current_playlist = playlist.get('name')
        state.queue = list(playlist.get('tracks', []))
        state.current_index = 0 if state.queue else -1
        state.current_track = None
        state.mark_updated()

    def replace_track(self, state: PlaybackState, track: Any) -> None:
        state.current_playlist = None
        state.queue = [track]
        state.current_index = 0
        state.current_track = None
        state.mark_updated()

    def replace_queue(self, state: PlaybackState, tracks: list[Any], start_index: int = 0) -> None:
        """Replace the entire queue with a new list of tracks."""
        state.queue = list(tracks)
        if state.queue:
            state.current_index = max(0, min(start_index, len(state.queue) - 1))
        else:
            state.current_index = -1
        state.current_track = None
        state.mark_updated()

    def clear(self, state: PlaybackState) -> None:
        state.queue = []
        state.current_index = -1
        state.current_track = None
        state.current_playlist = None
        state.mark_updated()

    # ------------------------------------------------------------------
    # Navigation (shuffle/repeat aware)
    # ------------------------------------------------------------------
    def current(self, state: PlaybackState) -> Any:
        if state.current_index < 0 or state.current_index >= len(state.queue):
            return None
        return state.queue[state.current_index]

    def advance(self, state: PlaybackState) -> bool:
        """Move to the next track. Honours repeat-all (wrap) and shuffle."""
        if not state.queue:
            return False

        if state.shuffle and len(state.queue) > 1:
            next_index = self._random_other_index(state)
            state.current_index = next_index
            state.mark_updated()
            return True

        next_index = state.current_index + 1
        if next_index >= len(state.queue):
            if state.repeat == REPEAT_ALL:
                next_index = 0
            else:
                return False

        state.current_index = next_index
        state.mark_updated()
        return True

    def previous(self, state: PlaybackState) -> bool:
        if not state.queue:
            return False

        previous_index = state.current_index - 1
        if previous_index < 0:
            if state.repeat == REPEAT_ALL:
                previous_index = len(state.queue) - 1
            else:
                return False

        state.current_index = previous_index
        state.mark_updated()
        return True

    def jump_to(self, state: PlaybackState, index: int) -> bool:
        if index < 0 or index >= len(state.queue):
            return False
        state.current_index = index
        state.mark_updated()
        return True

    # ------------------------------------------------------------------
    # Insertion
    # ------------------------------------------------------------------
    def insert_after_current(self, state: PlaybackState, track: Any) -> int:
        """Insert a track immediately after the currently playing track."""
        insert_at = state.current_index + 1 if state.current_index >= 0 else len(state.queue)
        insert_at = max(0, min(insert_at, len(state.queue)))
        state.queue.insert(insert_at, track)
        state.mark_updated()
        return insert_at

    def append(self, state: PlaybackState, track: Any) -> int:
        state.queue.append(track)
        if state.current_index < 0:
            state.current_index = 0
        state.mark_updated()
        return len(state.queue) - 1

    def append_many(self, state: PlaybackState, tracks: list[Any]) -> int:
        start = len(state.queue)
        state.queue.extend(tracks)
        if state.current_index < 0 and state.queue:
            state.current_index = 0
        state.mark_updated()
        return start

    def insert_at(self, state: PlaybackState, index: int, track: Any) -> int:
        index = max(0, min(index, len(state.queue)))
        state.queue.insert(index, track)
        # Keep cursor on the same track if we inserted before/at it.
        if index <= state.current_index:
            state.current_index += 1
        state.mark_updated()
        return index

    # ------------------------------------------------------------------
    # Removal
    # ------------------------------------------------------------------
    def remove_at(self, state: PlaybackState, index: int) -> Any | None:
        if index < 0 or index >= len(state.queue):
            return None
        removed = state.queue.pop(index)
        # Adjust cursor so it keeps pointing at the same track.
        if index < state.current_index:
            state.current_index -= 1
        elif index == state.current_index:
            # Removed the current track: clamp cursor to a valid position.
            if state.current_index >= len(state.queue):
                state.current_index = len(state.queue) - 1
        if not state.queue:
            state.current_index = -1
        state.mark_updated()
        return removed

    def clear_ahead(self, state: PlaybackState) -> int:
        """Remove all items after the current track."""
        if state.current_index < 0:
            removed = len(state.queue)
            state.queue = []
            state.current_index = -1
            state.mark_updated()
            return removed
        removed = len(state.queue) - (state.current_index + 1)
        del state.queue[state.current_index + 1:]
        state.mark_updated()
        return removed

    # ------------------------------------------------------------------
    # Reordering
    # ------------------------------------------------------------------
    def move(self, state: PlaybackState, from_index: int, to_index: int) -> bool:
        if from_index < 0 or from_index >= len(state.queue):
            return False
        to_index = max(0, min(to_index, len(state.queue) - 1))
        if from_index == to_index:
            return False

        current_track = self.current(state)
        item = state.queue.pop(from_index)
        state.queue.insert(to_index, item)
        # Restore cursor to the same logical track.
        if current_track is not None:
            try:
                state.current_index = state.queue.index(current_track)
            except ValueError:
                state.current_index = max(0, min(state.current_index, len(state.queue) - 1))
        state.mark_updated()
        return True

    def move_to_top(self, state: PlaybackState, index: int) -> bool:
        return self.move(state, index, 0)

    def move_to_bottom(self, state: PlaybackState, index: int) -> bool:
        return self.move(state, index, len(state.queue) - 1)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _random_other_index(self, state: PlaybackState) -> int:
        candidates = [i for i in range(len(state.queue)) if i != state.current_index]
        if not candidates:
            return state.current_index
        return random.choice(candidates)