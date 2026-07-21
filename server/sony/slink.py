import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import ip_network
from typing import Any, Mapping
import logging
from urllib.parse import urljoin, urlparse

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
LOGGER = logging.getLogger(__name__)


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
        self.server_url = None if not server_url or str(server_url).lower() == 'auto' else server_url
        self.auto_discover = not self.server_url

    def send(self, slink_data: str):
        self._ensure_server_url()

        headers = {'Content-Type': 'text/plain'}
        LOGGER.info("Sending S-Link command to %s: %s", self.server_url, slink_data.strip())
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

    def adapter_get(self, path: str):
        self._ensure_server_url()
        response = requests.get(urljoin(self.server_url.rstrip('/') + '/', path.lstrip('/')), timeout=3)
        response.raise_for_status()
        return response.json()

    def adapter_post(self, path: str, payload: Mapping[str, Any] | None = None):
        self._ensure_server_url()
        response = requests.post(urljoin(self.server_url.rstrip('/') + '/', path.lstrip('/')), json=payload or {}, timeout=3)
        response.raise_for_status()
        return response.json()

    def configure_webhook_target(self, port: int = 5000, path: str = '/webhook', host: str | None = None, scheme: str = 'http'):
        self._ensure_server_url()

        webhook_host = host or self._local_ip_for_server()
        webhook_url = f'{scheme}://{webhook_host}:{port}{path}'
        endpoint = urljoin(self.server_url.rstrip('/') + '/', 'webhook-target')
        LOGGER.info("Configuring S-Link webhook target %s -> %s", endpoint, webhook_url)
        response = requests.post(endpoint, json={'webhook_url': webhook_url}, timeout=3)
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError('ESP32 webhook-target endpoint did not return JSON; flash updated firmware first') from exc
        if payload.get('webhook_url') != webhook_url:
            raise RuntimeError(f"ESP32 webhook target confirmation mismatch: {payload}")
        return response

    def discover(self) -> str:
        candidates = self._candidate_adapter_urls()
        LOGGER.info("Discovering ESP32 S-Link adapter across %d candidates", len(candidates))
        with ThreadPoolExecutor(max_workers=32) as executor:
            futures = {executor.submit(self._probe_adapter, url): url for url in candidates}
            for future in as_completed(futures):
                payload = future.result()
                if payload:
                    self.server_url = futures[future]
                    LOGGER.info("Discovered ESP32 S-Link adapter at %s: %s", self.server_url, payload)
                    return self.server_url
        raise RuntimeError("Could not discover ESP32 S-Link adapter on local networks")

    def _ensure_server_url(self) -> None:
        if not self.server_url:
            self.discover()

    def _probe_adapter(self, url: str) -> Mapping[str, Any] | None:
        try:
            response = requests.get(urljoin(url.rstrip('/') + '/', 'status'), timeout=2)
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return None
        if payload.get('device') == 'sony_slink_esp32':
            return payload
        return None

    def _candidate_adapter_urls(self) -> list[str]:
        addresses = set()
        for host in ('192.168.137.1', '192.168.1.1', '8.8.8.8'):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe_socket:
                    probe_socket.connect((host, 80))
                    addresses.add(probe_socket.getsockname()[0])
            except OSError:
                pass
        try:
            for address in socket.gethostbyname_ex(socket.gethostname())[2]:
                if not address.startswith('127.'):
                    addresses.add(address)
        except OSError:
            pass

        candidates = []
        for address in sorted(addresses):
            try:
                network = ip_network(f'{address}/24', strict=False)
            except ValueError:
                continue
            candidates.extend(f'http://{host}:8080' for host in network.hosts())
        unique_candidates = sorted(set(candidates), key=lambda url: (not url.startswith('http://192.168.137.'), url))
        return unique_candidates

    def _local_ip_for_server(self) -> str:
        parsed = urlparse(self.server_url or '')
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        if not host:
            raise ValueError("SONY_SLINK_SERVER host is not configured")

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe_socket:
            probe_socket.connect((host, port))
            return probe_socket.getsockname()[0]

    def _send_request_with_retries(self, url: str, data: str, headers: dict[str, str], max_retries: int = 20):
        retries = 0
        while retries < max_retries:
            try:
                response = requests.post(url, data=data, headers=headers, timeout=3)
                response.raise_for_status()
                return response
            except (requests.RequestException, OSError) as exc:
                retries += 1
                wait_time = 0.1
                print(f"Connection error: {exc}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)

        raise RuntimeError("Failed to send request after multiple retries.")