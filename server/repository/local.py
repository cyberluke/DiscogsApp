import json
import os
from typing import Any

from pysondb import db


class LocalDataRepository:
    def __init__(
        self,
        releases_path: str = 'discogs_data_all.json',
        playlists_path: str = 'playlists.json',
        video_offsets_path: str = 'video_offsets.json',
        images_dir: str = 'downloaded_images',
        default_image_path: str = os.path.join('src', 'assets', 'default.png'),
    ):
        self.releases = db.getDb(releases_path)
        self.playlists = db.getDb(playlists_path)
        self.video_offsets = db.getDb(video_offsets_path)
        self.images_dir = images_dir
        self.default_image_path = default_image_path

    def all_releases(self) -> list[dict[str, Any]]:
        return self.releases.getAll()

    def all_playlists(self) -> list[dict[str, Any]]:
        return self.playlists.getAll()

    def save_playlist(self, playlist: dict[str, Any]) -> None:
        playlist_name = playlist.get('name')
        existing = self.playlists.getByQuery({'name': playlist_name}) if playlist_name else []
        if existing:
            self.playlists.updateByQuery({'name': playlist_name}, playlist)
            return
        self.playlists.add(playlist)

    def find_release_by_id(self, release_id: int) -> list[dict[str, Any]]:
        return self.releases.getByQuery({'release_id': release_id})

    def get_release_by_id(self, release_id: int) -> dict[str, Any] | None:
        releases = self.find_release_by_id(release_id)
        return releases[0] if releases else None

    def save_release_ai(self, release_id: int, ai_metadata: dict[str, Any]) -> dict[str, Any] | None:
        with self.releases.lock:
            with open(self.releases.filename, 'r+', encoding='utf-8') as db_file:
                db_data = json.load(db_file)
                updated_release = None
                for release in db_data.get('data') or []:
                    if release.get('release_id') == release_id:
                        release['ai'] = ai_metadata
                        if updated_release is None:
                            updated_release = release
                if updated_release is None:
                    return None
                db_file.seek(0)
                db_file.truncate()
                json.dump(db_data, db_file, indent=3, ensure_ascii=False)
                return updated_release

    def find_releases_by_deck_cd(self, deck_number: int, cd_position: int) -> list[dict[str, Any]]:
        return self.releases.getByQuery({'cd_position': cd_position, 'deck_number': deck_number})

    def favourite_tracks_playlist(self) -> dict[str, Any]:
        high_score_tracks = []
        for release in self.all_releases():
            for track in release.get('tracklist') or []:
                if track.get('_score', 0) < 1:
                    continue
                artist_name = release.get('artists_sort', 'Unknown Artist')
                if artist_name == 'Various' and track.get('artists'):
                    artist_name = track['artists'][0].get('name', 'Unknown Artist')
                favourite_track = dict(track)
                favourite_track['release_id'] = release.get('release_id')
                favourite_track['deck_number'] = release.get('deck_number')
                favourite_track['cd_position'] = release.get('cd_position')
                favourite_track['full_name'] = artist_name + ' - ' + track.get('title', '')
                favourite_track['artist'] = artist_name
                favourite_track['album_title'] = release.get('title')
                high_score_tracks.append(favourite_track)

        return {'name': 'Favourite Tracks', 'tracks': high_score_tracks}

    def add_track_to_favourites(self, release_id: int, track_position: str) -> dict[str, Any] | None:
        releases = self.find_release_by_id(release_id)
        if not releases:
            return None

        release = releases[0]
        track = next((item for item in release.get('tracklist') or [] if item.get('position') == track_position), None)
        if track is None:
            return None

        track['_score'] = 1
        self.releases.updateById(release['id'], release)
        return release

    def image_path(self, image_name: str) -> str:
        return os.path.join(self.images_dir, image_name)

    def find_video_offset(self, query: dict[str, Any]) -> dict[str, Any] | None:
        result = self.video_offsets.getBy(query)
        if isinstance(result, list):
            return result[0] if result else None
        return result

    def ensure_video_offset(self, title: str, artist: str) -> dict[str, Any]:
        existing = self.find_video_offset({'title': title, 'artist': artist})
        if existing:
            return existing

        self.video_offsets.add({
            'title': title,
            'artist': artist,
            'videos_offsets': [0, 0, 0],
            'alias': '',
        })
        return self.find_video_offset({'title': title, 'artist': artist})

    def find_video_offset_by_alias(self, alias: str) -> dict[str, Any] | None:
        return self.find_video_offset({'alias': alias})

    def ensure_images_dir(self) -> None:
        os.makedirs(self.images_dir, exist_ok=True)

    def absolute_images_dir(self) -> str:
        return os.path.abspath(self.images_dir)

    def absolute_default_image_path(self) -> str:
        return os.path.abspath(self.default_image_path)

    def default_assets_dir(self) -> str:
        return os.path.dirname(self.default_image_path)