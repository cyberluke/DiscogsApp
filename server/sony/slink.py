import re
import time
from typing import Any, Mapping

import requests


CD_PLAYER_DECK_1 = 90
CD_PLAYER_DECK_2 = 92
CD_OPERATION_RESUME = 0
CD_OPERATION_STOP = 1
CD_OPERATION_PAUSE = 2
CD_OPERATION_NEXT_TRACK = 8
CD_OPERATION_PREVIOUS_TRACK = 9
CD_OPERATION_ENABLE_CONTINUOUS_STATUS = 25
CD_OPERATION_DISABLE_CONTINUOUS_STATUS = 26
CD_OPERATION_PLAY = 50
DEFAULT_TRACK_DURATION = "3:20"


def duration_to_seconds(duration: str) -> int:
    if not duration:
        duration = DEFAULT_TRACK_DURATION

    try:
        parts = [int(part) for part in str(duration).split(':')]
    except ValueError as exc:
        raise ValueError(f"Unsupported duration format: {duration}") from exc
    if len(parts) == 2:
        minutes, seconds = parts
        return minutes * 60 + seconds
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds

    raise ValueError(f"Unsupported duration format: {duration}")


def format_with_padding(value: Any, pad_length: int = 2) -> str:
    if isinstance(value, int):
        return f"{value:0{pad_length}d}"
    if isinstance(value, str) and value.isdigit():
        return f"{int(value):0{pad_length}d}"
    if isinstance(value, str) and len(value) == 1:
        return '0' + value
    return str(value)


def process_position(position: Any) -> str:
    position_text = str(position)
    if '-' in position_text:
        position_text = position_text.split('-')[1]

    return re.sub(r'\D', '', position_text)


def get_track_value(track: Any, name: str, default: Any = None) -> Any:
    if isinstance(track, Mapping):
        return track.get(name, default)
    return getattr(track, name, default)


def build_track_command(track: Any, include_duration: bool = False) -> str:
    cd_player_id = CD_PLAYER_DECK_2 if get_track_value(track, 'deck_number') == 2 else CD_PLAYER_DECK_1
    cd_position = int(get_track_value(track, 'cd_position'))
    track_position = process_position(get_track_value(track, 'position'))

    if cd_position < 100:
        command = f"{cd_player_id}{CD_OPERATION_PLAY}"
        command += format_with_padding(cd_position)
        command += format_with_padding(track_position)
    elif cd_position <= 200:
        command = f"{cd_player_id}{CD_OPERATION_PLAY}"
        encoded_cd_position = hex(0x9A + (cd_position - 100))[2:]
        command += format_with_padding(encoded_cd_position)
        command += format_with_padding(track_position)
    else:
        command = f"{cd_player_id + 3}{CD_OPERATION_PLAY}"
        encoded_cd_position = hex(cd_position - 200)[2:]
        command += format_with_padding(encoded_cd_position)
        command += format_with_padding(track_position)

    if include_duration:
        duration = get_track_value(track, 'duration') or DEFAULT_TRACK_DURATION
        command += ':' + str(duration_to_seconds(duration))

    return command + "\r\n"


def build_playlist_command(playlist: Mapping[str, Any]) -> str:
    slink_data = "PLAYLIST\r\n"
    for track in playlist.get('tracks', []):
        slink_data += build_track_command(track, include_duration=True)
    return slink_data


def build_transport_command(operation: int, deck_number: int = 1) -> str:
    cd_player_id = CD_PLAYER_DECK_2 if deck_number == 2 else CD_PLAYER_DECK_1
    return f"{cd_player_id}{operation:02d}\r\n"


class SLinkClient:
    def __init__(self, server_url: str | None):
        self.server_url = server_url

    def send(self, slink_data: str):
        if not self.server_url:
            raise ValueError("SONY_SLINK_SERVER is not configured")

        headers = {'Content-Type': 'text/plain'}
        return self._send_request_with_retries(self.server_url, slink_data, headers)

    def send_track(self, track: Any):
        return self.send(build_track_command(track))

    def send_playlist(self, playlist: Mapping[str, Any]):
        return self.send(build_playlist_command(playlist))

    def send_resume(self, deck_number: int = 1):
        return self.send(build_transport_command(CD_OPERATION_RESUME, deck_number))

    def send_stop(self, deck_number: int = 1):
        return self.send(build_transport_command(CD_OPERATION_STOP, deck_number))

    def send_pause(self, deck_number: int = 1):
        return self.send(build_transport_command(CD_OPERATION_PAUSE, deck_number))

    def send_next_track(self, deck_number: int = 1):
        return self.send(build_transport_command(CD_OPERATION_NEXT_TRACK, deck_number))

    def send_previous_track(self, deck_number: int = 1):
        return self.send(build_transport_command(CD_OPERATION_PREVIOUS_TRACK, deck_number))

    def send_enable_continuous_status(self, deck_number: int = 1):
        return self.send(build_transport_command(CD_OPERATION_ENABLE_CONTINUOUS_STATUS, deck_number))

    def send_disable_continuous_status(self, deck_number: int = 1):
        return self.send(build_transport_command(CD_OPERATION_DISABLE_CONTINUOUS_STATUS, deck_number))

    def _send_request_with_retries(self, url: str, data: str, headers: dict[str, str], max_retries: int = 20):
        retries = 0
        while retries < max_retries:
            try:
                response = requests.post(url, data=data, headers=headers)
                response.raise_for_status()
                return response
            except (requests.RequestException, OSError) as exc:
                retries += 1
                wait_time = 0.1
                print(f"Connection error: {exc}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

        raise RuntimeError("Failed to send request after multiple retries.")