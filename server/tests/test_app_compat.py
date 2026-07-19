import unittest

import server.app as app_module


class FakeRuntime:
    def __init__(self):
        self.transport_statuses = []
        self.observed_tracks = []

    def play_playlist(self, playlist):
        return {'playback_state': 'playing', 'current_playlist': playlist.get('name')}

    def play_track(self, track):
        return {'playback_state': 'playing', 'current_track': track}

    def handle_transport_status(self, status, payload=None):
        self.transport_statuses.append((status, payload))
        return {'playback_state': status.lower()}

    def observe_track(self, track):
        self.observed_tracks.append(track)
        return {'playback_state': 'playing', 'current_track': track}

    def status(self):
        return {'playback_state': 'idle'}


class FailingRuntime(FakeRuntime):
    def play_track(self, track):
        raise RuntimeError('S-Link offline')

    def status(self):
        return {'playback_state': 'error', 'error': 'S-Link offline'}


class AppCompatibilityTest(unittest.TestCase):
    def setUp(self):
        self.original_runtime = app_module.playback_runtime
        app_module.playback_runtime = FakeRuntime()
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.playback_runtime = self.original_runtime

    def test_legacy_playlist_and_track_wrappers_delegate_to_runtime(self):
        playlist_response = self.client.post('/playlist', json={'name': 'Mix', 'tracks': [{'title': 'Song'}]})
        track_response = self.client.post('/track', json={'title': 'Song'})

        self.assertEqual(playlist_response.status_code, 200)
        self.assertEqual(playlist_response.get_json()['playback']['current_playlist'], 'Mix')
        self.assertEqual(track_response.status_code, 200)
        self.assertEqual(track_response.get_json()['playback']['current_track']['title'], 'Song')

    def test_legacy_track_wrapper_returns_stable_error(self):
        app_module.playback_runtime = FailingRuntime()

        response = self.client.post('/track', json={'title': 'Song'})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['error'], 'S-Link offline')
        self.assertEqual(response.get_json()['playback']['playback_state'], 'error')

    def test_legacy_wrappers_return_stable_error_for_malformed_json(self):
        playlist_response = self.client.post('/playlist', data='{bad', content_type='application/json')
        track_response = self.client.post('/track', data='{bad', content_type='application/json')

        self.assertEqual(playlist_response.status_code, 400)
        self.assertEqual(track_response.status_code, 400)
        self.assertEqual(playlist_response.get_json()['error'], 'Malformed JSON request body')
        self.assertEqual(track_response.get_json()['playback']['playback_state'], 'idle')

    def test_webhook_transport_statuses_update_runtime_when_kodi_is_disabled(self):
        runtime = FakeRuntime()
        app_module.playback_runtime = runtime
        original_use_kodi = app_module.USE_KODI
        app_module.USE_KODI = False
        self.addCleanup(lambda: setattr(app_module, 'USE_KODI', original_use_kodi))

        response = app_module.process_webhook({'status': 'PAUSE'})

        self.assertEqual(response, ('OK', 200))
        self.assertEqual(runtime.transport_statuses, [('PAUSE', {'status': 'PAUSE'})])

    def test_webhook_play_status_updates_runtime_from_hardware_track_status(self):
        runtime = FakeRuntime()
        app_module.playback_runtime = runtime
        original_repository = app_module.data_repository
        original_use_kodi = app_module.USE_KODI
        app_module.USE_KODI = False
        self.addCleanup(lambda: setattr(app_module, 'data_repository', original_repository))
        self.addCleanup(lambda: setattr(app_module, 'USE_KODI', original_use_kodi))

        class FakeRepository:
            def find_releases_by_deck_cd(self, deck_number, cd_position):
                self.query = (deck_number, cd_position)
                return [{
                    'release_id': 123,
                    'title': 'Album',
                    'artists_sort': 'Artist',
                    'images': [{'type': 'primary', 'uri': 'https://example.test/cover.jpg'}],
                    'tracklist': [
                        {'position': '1', 'title': 'First', 'duration': '0:30'},
                        {'position': '2', 'title': 'Second', 'duration': '0:31'},
                    ],
                }]

        repository = FakeRepository()
        app_module.data_repository = repository

        response = app_module.process_webhook({'status': 'PLAY', 'device': '98', 'cd': '01', 'track': '02', 'duration': '0'})

        self.assertEqual(response, ('OK', 200))
        self.assertEqual(repository.query, (1, 1))
        self.assertEqual(runtime.observed_tracks[0]['title'], 'Second')
        self.assertEqual(runtime.observed_tracks[0]['cd_position'], 1)
        self.assertEqual(runtime.observed_tracks[0]['deck_number'], 1)
        self.assertEqual(runtime.observed_tracks[0]['artwork_url'], 'https://example.test/cover.jpg')

    def test_adjacent_release_track_resolver_adds_display_metadata(self):
        original_repository = app_module.data_repository
        self.addCleanup(lambda: setattr(app_module, 'data_repository', original_repository))

        class FakeRepository:
            def find_releases_by_deck_cd(self, deck_number, cd_position):
                return [{
                    'release_id': 123,
                    'title': 'Album',
                    'artists_sort': 'Artist',
                    'images': [{'type': 'primary', 'uri': 'https://example.test/cover.jpg'}],
                    'tracklist': [
                        {'position': '1', 'title': 'First', 'duration': '0:30'},
                        {'position': '2', 'title': 'Second', 'duration': '0:31'},
                    ],
                }]

        app_module.data_repository = FakeRepository()

        adjacent = app_module.resolve_adjacent_release_track({'deck_number': 1, 'cd_position': 1, 'position': '1'}, 'next')

        self.assertEqual(adjacent['title'], 'Second')
        self.assertEqual(adjacent['full_name'], 'Artist - Second')
        self.assertEqual(adjacent['artwork_url'], 'https://example.test/cover.jpg')


if __name__ == '__main__':
    unittest.main()