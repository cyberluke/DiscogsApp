"""Spotify Web API client for audio feature retrieval."""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE = 'https://api.spotify.com/v1'

# Spotify key notation: 0=C, 1=C#, 2=D, ... 11=B
KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


class SpotifyClient:
    """Handles Spotify OAuth2 client-credentials flow and API calls."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    def _ensure_token(self) -> None:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return
        resp = requests.post(TOKEN_URL, data={
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        self._access_token = payload['access_token']
        self._token_expires_at = time.time() + payload.get('expires_in', 3600)

    def _headers(self) -> dict[str, str]:
        self._ensure_token()
        return {'Authorization': f'Bearer {self._access_token}'}

    def search_track(self, artist: str, title: str) -> dict[str, Any] | None:
        """Search Spotify for a track, return the best match or None."""
        query = f'artist:{artist} track:{title}'
        resp = requests.get(f'{API_BASE}/search', params={
            'q': query,
            'type': 'track',
            'limit': 5,
        }, headers=self._headers(), timeout=15)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get('Retry-After', 5))
            logger.warning('Spotify rate limited, waiting %ds', retry_after)
            time.sleep(retry_after)
            resp = requests.get(f'{API_BASE}/search', params={
                'q': query,
                'type': 'track',
                'limit': 5,
            }, headers=self._headers(), timeout=15)
        if resp.status_code != 200:
            logger.warning('Spotify search failed %d: %s', resp.status_code, resp.text[:200])
            return None
        items = resp.json().get('tracks', {}).get('items', [])
        if not items:
            return None
        return items[0]

    def get_audio_features(self, track_id: str) -> dict[str, Any] | None:
        """Get audio features for a Spotify track ID."""
        resp = requests.get(f'{API_BASE}/audio-features/{track_id}',
                            headers=self._headers(), timeout=15)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get('Retry-After', 5))
            logger.warning('Spotify rate limited, waiting %ds', retry_after)
            time.sleep(retry_after)
            resp = requests.get(f'{API_BASE}/audio-features/{track_id}',
                                headers=self._headers(), timeout=15)
        if resp.status_code != 200:
            logger.warning('Spotify audio-features failed %d for %s', resp.status_code, track_id)
            return None
        return resp.json()

    @staticmethod
    def key_name(key: int, mode: int) -> str:
        """Convert Spotify key/mode to human-readable notation like 'F# minor'."""
        if key < 0 or key > 11:
            return 'Unknown'
        name = KEY_NAMES[key]
        mode_label = 'major' if mode == 1 else 'minor'
        return f'{name} {mode_label}'
