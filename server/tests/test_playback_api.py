import unittest

from flask import Flask

from server.api.playback import create_playback_api


class FakeRuntime:
    def __init__(self):
        self.played_playlist = None
        self.played_track = None

    def play_playlist(self, playlist):
        self.played_playlist = playlist
        return {'playback_state': 'playing', 'current_playlist': playlist.get('name')}

    def play_track(self, track):
        self.played_track = track
        return {'playback_state': 'playing', 'current_track': track}

    def stop(self):
        return {'playback_state': 'stopped'}

    def pause(self):
        return {'playback_state': 'paused'}

    def resume(self):
        return {'playback_state': 'playing'}

    def next_track(self):
        return {'playback_state': 'playing', 'current_track': {'title': 'Next'}}

    def previous_track(self):
        return {'playback_state': 'playing', 'current_track': {'title': 'Previous'}}

    def status(self):
        return {'playback_state': 'idle'}

    def progress(self):
        return {'elapsed': 0, 'duration': 0, 'remaining': 0, 'progress': 0, 'playback_state': 'idle'}

    def queue(self):
        return {'queue': [], 'upcoming': [], 'current_track': None, 'current_playlist': None, 'playback_state': 'idle'}


class FakeRecommendations:
    def search(self, query):
        return [{'title': query.get('artist', 'Any')}]


class FailingRuntime(FakeRuntime):
    def __init__(self):
        super().__init__()
        self.error_status = {'playback_state': 'error', 'error': 'S-Link offline'}

    def play_track(self, track):
        raise RuntimeError('S-Link offline')

    def status(self):
        return self.error_status


class PlaybackApiTest(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime()
        self.recommendations = FakeRecommendations()
        app = Flask(__name__)
        app.register_blueprint(create_playback_api(self.runtime, self.recommendations))
        self.client = app.test_client()

    def test_playback_status_progress_and_queue_routes(self):
        self.assertEqual(self.client.get('/playback/status').get_json()['playback_state'], 'idle')
        self.assertEqual(self.client.get('/playback/progress').get_json()['progress'], 0)
        self.assertEqual(self.client.get('/queue').get_json()['queue'], [])

    def test_playlist_and_track_commands_delegate_to_runtime(self):
        playlist_response = self.client.post('/playlist/play', json={'name': 'Mix', 'tracks': []})
        track_response = self.client.post('/track/play', json={'title': 'Song'})

        self.assertEqual(playlist_response.get_json()['current_playlist'], 'Mix')
        self.assertEqual(track_response.get_json()['current_track']['title'], 'Song')
        self.assertEqual(self.runtime.played_playlist['name'], 'Mix')
        self.assertEqual(self.runtime.played_track['title'], 'Song')

    def test_pause_stop_and_recommendations_routes(self):
        self.assertEqual(self.client.post('/playlist/pause').get_json()['playback_state'], 'paused')
        self.assertEqual(self.client.post('/playlist/resume').get_json()['playback_state'], 'playing')
        self.assertEqual(self.client.post('/playlist/stop').get_json()['playback_state'], 'stopped')

        recommendations = self.client.get('/recommendations?artist=Underworld').get_json()
        self.assertEqual(recommendations['count'], 1)
        self.assertEqual(recommendations['results'][0]['title'], 'Underworld')

    def test_next_and_previous_routes_delegate_to_runtime(self):
        self.assertEqual(self.client.post('/playlist/next').get_json()['current_track']['title'], 'Next')
        self.assertEqual(self.client.post('/playlist/previous').get_json()['current_track']['title'], 'Previous')

    def test_track_play_returns_stable_error_response(self):
        app = Flask(__name__)
        app.register_blueprint(create_playback_api(FailingRuntime(), self.recommendations))
        client = app.test_client()

        response = client.post('/track/play', json={'title': 'Song'})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json()['error'], 'S-Link offline')
        self.assertEqual(response.get_json()['playback']['playback_state'], 'error')

    def test_command_routes_return_stable_error_for_malformed_json(self):
        playlist_response = self.client.post('/playlist/play', data='{bad', content_type='application/json')
        track_response = self.client.post('/track/play', data='{bad', content_type='application/json')

        self.assertEqual(playlist_response.status_code, 400)
        self.assertEqual(track_response.status_code, 400)
        self.assertEqual(playlist_response.get_json()['error'], 'Malformed JSON request body')
        self.assertEqual(track_response.get_json()['playback']['playback_state'], 'idle')


if __name__ == '__main__':
    unittest.main()