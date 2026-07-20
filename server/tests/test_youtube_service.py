import os
import tempfile
import unittest
from unittest.mock import patch

from server.services.youtube import YouTubeSearchService


class FakeRepository:
    def __init__(self):
        self.aliases = {}
        self.offsets = []

    def find_video_offset_by_alias(self, alias):
        return self.aliases.get(alias)

    def ensure_video_offset(self, title, artist):
        self.offsets.append((title, artist))
        return {'title': title, 'artist': artist, 'videos_offsets': [0, 12, 0]}


class YouTubeSearchServiceTest(unittest.TestCase):
    def test_find_best_video_searches_youtube_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeRepository()
            service = YouTubeSearchService(repository, api_key='test-key', cache_path=os.path.join(temp_dir, 'cache.json'))

            search_payload = {
                'items': [{
                    'id': {'videoId': 'timber123'},
                    'snippet': {
                        'title': 'Pitbull - Timber ft. Ke$ha (Official Video)',
                        'channelTitle': 'PitbullVEVO',
                        'thumbnails': {'high': {'url': 'thumb.jpg'}},
                    },
                }]
            }
            durations_payload = {'items': [{'id': 'timber123', 'contentDetails': {'duration': 'PT3M35S'}, 'status': {'embeddable': True, 'privacyStatus': 'public', 'uploadStatus': 'processed'}}]}

            with patch('server.services.youtube.service.requests.get') as get:
                get.side_effect = [FakeResponse(search_payload), FakeResponse(durations_payload)]

                result = service.find_best_video(artist='Pitbull Feat. Kesha', title='Timber')

            self.assertEqual(result['youtube_id'], 'timber123')
            self.assertEqual(result['thumbnail'], 'thumb.jpg')
            self.assertEqual(result['duration'], 'PT3M35S')
            self.assertTrue(result['playback_safe'])
            self.assertIn('youtube/v3/search', get.call_args_list[0].args[0])
            self.assertNotIn('videoSyndicated', get.call_args_list[0].kwargs['params'])

    def test_find_best_video_skips_non_embeddable_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeRepository()
            service = YouTubeSearchService(repository, api_key='test-key', cache_path=os.path.join(temp_dir, 'cache.json'))

            search_payload = {
                'items': [
                    {
                        'id': {'videoId': 'blocked123'},
                        'snippet': {
                            'title': 'Pitbull - Timber ft. Ke$ha (Official Video)',
                            'channelTitle': 'PitbullVEVO',
                            'thumbnails': {'high': {'url': 'blocked.jpg'}},
                        },
                    },
                    {
                        'id': {'videoId': 'embed123'},
                        'snippet': {
                            'title': 'Pitbull - Timber ft. Ke$ha',
                            'channelTitle': 'PitbullVEVO',
                            'thumbnails': {'high': {'url': 'embed.jpg'}},
                        },
                    },
                ]
            }
            details_payload = {'items': [
                {'id': 'blocked123', 'contentDetails': {'duration': 'PT3M35S'}, 'status': {'embeddable': False, 'privacyStatus': 'public', 'uploadStatus': 'processed'}},
                {'id': 'embed123', 'contentDetails': {'duration': 'PT3M37S'}, 'status': {'embeddable': True, 'privacyStatus': 'public', 'uploadStatus': 'processed'}},
            ]}

            with patch('server.services.youtube.service.requests.get') as get:
                get.side_effect = [FakeResponse(search_payload), FakeResponse(details_payload)]

                result = service.find_best_video(artist='Pitbull Feat. Kesha', title='Timber')

            self.assertEqual(result['youtube_id'], 'embed123')
            self.assertTrue(result['embeddable'])

    def test_find_best_video_skips_private_or_unprocessed_results(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeRepository()
            service = YouTubeSearchService(repository, api_key='test-key', cache_path=os.path.join(temp_dir, 'cache.json'))

            search_payload = {
                'items': [
                    {
                        'id': {'videoId': 'private123'},
                        'snippet': {
                            'title': 'Pitbull - Timber ft. Ke$ha (Official Video)',
                            'channelTitle': 'PitbullVEVO',
                        },
                    },
                    {
                        'id': {'videoId': 'safe123'},
                        'snippet': {
                            'title': 'Pitbull - Timber ft. Ke$ha (Official Video)',
                            'channelTitle': 'PitbullVEVO',
                        },
                    },
                ]
            }
            details_payload = {'items': [
                {'id': 'private123', 'contentDetails': {'duration': 'PT3M35S'}, 'status': {'embeddable': True, 'privacyStatus': 'private', 'uploadStatus': 'processed'}},
                {'id': 'safe123', 'contentDetails': {'duration': 'PT3M37S'}, 'status': {'embeddable': True, 'privacyStatus': 'public', 'uploadStatus': 'processed'}},
            ]}

            with patch('server.services.youtube.service.requests.get') as get:
                get.side_effect = [FakeResponse(search_payload), FakeResponse(details_payload)]

                result = service.find_best_video(artist='Pitbull Feat. Kesha', title='Timber')

            self.assertEqual(result['youtube_id'], 'safe123')
            self.assertTrue(result['playback_safe'])

    def test_find_best_video_rejects_untrusted_syndicated_clips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeRepository()
            service = YouTubeSearchService(repository, api_key='test-key', cache_path=os.path.join(temp_dir, 'cache.json'))

            search_payload = {
                'items': [{
                    'id': {'videoId': 'fanlive123'},
                    'snippet': {
                        'title': 'PITBULL & KESHA - TIMBER | BST HYDE PARK | 10.07.26',
                        'channelTitle': 'K-pop Korner',
                    },
                }]
            }
            details_payload = {'items': [
                {'id': 'fanlive123', 'contentDetails': {'duration': 'PT3M35S'}, 'status': {'embeddable': True, 'privacyStatus': 'public', 'uploadStatus': 'processed'}},
            ]}

            with patch('server.services.youtube.service.requests.get') as get:
                get.side_effect = [FakeResponse(search_payload), FakeResponse(details_payload)]

                result = service.find_best_video(artist='Pitbull Feat. Kesha', title='Timber')

            self.assertIsNone(result)

    def test_finds_best_video_using_existing_title_word_heuristic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeRepository()
            videos = [{
                'musicvideoid': 42,
                'title': 'Protect Your Mind',
                'artist': ['DJ Sakin & Friends'],
                'file': 'plugin://plugin.video.youtube/play/?video_id=abc123XYZ',
                'thumbnail': 'thumb.jpg',
                'runtime': 220,
            }]
            service = YouTubeSearchService(repository, cache_path=os.path.join(temp_dir, 'cache.json'))

            result = service.find_best_kodi_music_video(
                artist='DJ Sakin & Friends',
                title='Protect Your Mind Braveheart',
                music_videos=videos,
            )

            self.assertEqual(result['provider_id'], 42)
            self.assertEqual(result['youtube_id'], 'abc123XYZ')
            self.assertEqual(result['thumbnail'], 'thumb.jpg')
            self.assertEqual(result['duration'], 220)
            self.assertEqual(result['offset_seconds'], 12)

    def test_caches_by_artist_and_title(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeRepository()
            service = YouTubeSearchService(repository, cache_path=os.path.join(temp_dir, 'cache.json'))
            service.set_kodi_music_videos([{
                'musicvideoid': 7,
                'title': 'Floorfiller',
                'artist': ['A-Teens'],
                'file': 'https://youtu.be/floor123',
            }])

            self.assertIsNotNone(service.find_best_kodi_music_video(artist='A-Teens', title='Floorfiller'))
            self.assertIsNotNone(service.find_best_kodi_music_video(artist='A-Teens', title='Floorfiller'))
            self.assertEqual(repository.offsets, [('Floorfiller', ['A-Teens'])])

    def test_alias_override_reuses_existing_video_offset_aliases(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = FakeRepository()
            repository.aliases['una noche más'] = {'title': 'Waiting for Tonight', 'artist': ['Jennifer Lopez']}
            videos = [{
                'musicvideoid': 9,
                'title': 'Waiting for Tonight',
                'artist': ['Jennifer Lopez'],
                'file': 'https://www.youtube.com/watch?v=wait999',
            }]
            service = YouTubeSearchService(repository, cache_path=os.path.join(temp_dir, 'cache.json'))

            result = service.find_best_kodi_music_video(
                artist='Jennifer Lopez',
                title='una noche más',
                music_videos=videos,
            )

            self.assertEqual(result['provider_id'], 9)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


if __name__ == '__main__':
    unittest.main()
