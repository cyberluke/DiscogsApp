from typing import Any, Mapping

try:
    from playback.state import PlaybackState
except ImportError:
    from server.playback.state import PlaybackState


class PlaybackQueue:
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

    def current(self, state: PlaybackState) -> Any:
        if state.current_index < 0 or state.current_index >= len(state.queue):
            return None
        return state.queue[state.current_index]

    def advance(self, state: PlaybackState) -> bool:
        next_index = state.current_index + 1
        if next_index >= len(state.queue):
            return False

        state.current_index = next_index
        state.mark_updated()
        return True

    def previous(self, state: PlaybackState) -> bool:
        previous_index = state.current_index - 1
        if previous_index < 0:
            return False

        state.current_index = previous_index
        state.mark_updated()
        return True