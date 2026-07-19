import json
import os
import tempfile
import unittest

from server.repository.local import LocalDataRepository


class LocalDataRepositoryTest(unittest.TestCase):
    def test_loads_json_stores_and_image_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            releases_path = os.path.join(temp_dir, 'releases.json')
            playlists_path = os.path.join(temp_dir, 'playlists.json')
            video_offsets_path = os.path.join(temp_dir, 'video_offsets.json')
            images_dir = os.path.join(temp_dir, 'images')
            default_image_path = os.path.join(temp_dir, 'assets', 'default.png')

            self.write_json(releases_path, [{'id': 1, 'release_id': 10, 'title': 'Release'}])
            self.write_json(playlists_path, [{'id': 1, 'name': 'Playlist', 'tracks': []}])
            self.write_json(video_offsets_path, [])

            repository = LocalDataRepository(
                releases_path=releases_path,
                playlists_path=playlists_path,
                video_offsets_path=video_offsets_path,
                images_dir=images_dir,
                default_image_path=default_image_path,
            )

            self.assertEqual(repository.all_releases()[0]['title'], 'Release')
            self.assertEqual(repository.all_playlists()[0]['name'], 'Playlist')
            self.assertEqual(repository.find_release_by_id(10)[0]['title'], 'Release')
            self.assertEqual(repository.image_path('cover.jpeg'), os.path.join(images_dir, 'cover.jpeg'))

            repository.ensure_images_dir()
            self.assertTrue(os.path.isdir(repository.absolute_images_dir()))
            self.assertEqual(repository.absolute_default_image_path(), os.path.abspath(default_image_path))
            self.assertEqual(repository.default_assets_dir(), os.path.join(temp_dir, 'assets'))

    def test_save_release_ai_updates_all_rows_with_same_release_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            releases_path = os.path.join(temp_dir, 'releases.json')
            playlists_path = os.path.join(temp_dir, 'playlists.json')
            video_offsets_path = os.path.join(temp_dir, 'video_offsets.json')
            self.write_json(releases_path, [
                {'id': 1, 'release_id': 10, 'title': 'Release (CD 1)'},
                {'id': 2, 'release_id': 10, 'title': 'Release (CD 2)'},
            ])
            self.write_json(playlists_path, [])
            self.write_json(video_offsets_path, [])
            repository = LocalDataRepository(
                releases_path=releases_path,
                playlists_path=playlists_path,
                video_offsets_path=video_offsets_path,
            )

            repository.save_release_ai(10, {'version': 1, 'scene': 'Eurodance'})

            releases = repository.all_releases()
            self.assertEqual(releases[0]['ai']['scene'], 'Eurodance')
            self.assertEqual(releases[1]['ai']['scene'], 'Eurodance')

    def write_json(self, path, payload):
        with open(path, 'w', encoding='utf-8') as file:
            json.dump({'data': payload}, file)


if __name__ == '__main__':
    unittest.main()