import json
import unittest

from flask import Flask

from server.api.chat import create_chat_api


class FakeRepository:
    def __init__(self):
        self.releases = [
            {
                'id': 1,
                'release_id': 100,
                'title': 'Current Euro Hit',
                'artists_sort': 'Captain Hollywood',
                'year': 1994,
                'country': 'Germany',
                'genres': ['Electronic'],
                'styles': ['Eurodance'],
                'labels': [{'name': 'Dance Pool'}],
                'deck_number': 1,
                'cd_position': 10,
                'images': [],
                'tracklist': [{'position': '1', 'title': 'Current Track', 'duration': '3:30'}],
                'ai': {'version': 1, 'energy': 80, 'cheese': 40, 'commercial': 75, 'keywords': ['eurodance']},
            },
            {
                'id': 2,
                'release_id': 200,
                'title': 'German Trance Memory',
                'artists_sort': 'DJ Sakin',
                'year': 1998,
                'country': 'Germany',
                'genres': ['Electronic'],
                'styles': ['Trance'],
                'labels': [{'name': 'Club Tools'}],
                'deck_number': 1,
                'cd_position': 11,
                'images': [],
                'tracklist': [{'position': '1', 'title': 'Protect Your Mind', 'duration': '3:40'}],
                'ai': {
                    'version': 1,
                    'summary': 'A German trance crossover with melodic lift and late 90s club memory.',
                    'energy': 88,
                    'danceability': 84,
                    'euphoria': 90,
                    'nostalgia': 82,
                    'cheese': 25,
                    'commercial': 45,
                    'keywords': ['trance', 'melodic'],
                    'mood': ['night driving'],
                    'driving_music': True,
                },
            },
        ]
        self.playlists = [
            {
                'name': 'Test Session',
                'tracks': [
                    {
                        'release_id': 100,
                        'position': '1',
                        'title': 'Current Track',
                        'artist': 'Captain Hollywood',
                        'full_name': 'Captain Hollywood - Current Track',
                        'deck_number': 1,
                        'cd_position': 10,
                    },
                    {
                        'release_id': 200,
                        'position': '1',
                        'title': 'Protect Your Mind',
                        'artist': 'DJ Sakin',
                        'full_name': 'DJ Sakin - Protect Your Mind',
                        'deck_number': 1,
                        'cd_position': 11,
                    },
                ],
            }
        ]

    def all_releases(self):
        return self.releases

    def get_release_by_id(self, release_id):
        return next((release for release in self.releases if release['release_id'] == release_id), None)

    def all_playlists(self):
        return self.playlists

    def save_playlist(self, playlist):
        self.playlists.append(playlist)


class FakePlaybackRuntime:
    def __init__(self):
        self.played = None
        self.played_playlist = None
        self.command = None

    def status(self):
        return {
            'current_track': {
                'release_id': 100,
                'position': '1',
                'title': 'Current Track',
                'artist': 'Captain Hollywood',
                'full_name': 'Captain Hollywood - Current Track',
                'duration': '3:30',
                'deck_number': 1,
                'cd_position': 10,
            },
            'current_playlist': 'Test Session',
            'queue': [],
            'upcoming': [],
            'elapsed': 30,
            'duration': 210,
            'remaining': 180,
            'progress': 14,
            'current_deck': 1,
            'current_cd': 10,
            'playback_state': 'playing',
            'last_update_timestamp': 0,
            'load_delay_seconds': 0,
            'load_delay_remaining': 0,
            'error': None,
        }

    def play_track(self, track):
        self.played = track
        status = self.status()
        status['current_track'] = track
        return status

    def play_playlist(self, playlist):
        self.played_playlist = playlist
        status = self.status()
        status['current_playlist'] = playlist.get('name')
        return status

    def pause(self):
        self.command = 'pause'
        return {'playback_state': 'paused'}

    def resume(self):
        self.command = 'resume'
        return {'playback_state': 'playing'}

    def stop(self):
        self.command = 'stop'
        return {'playback_state': 'stopped'}

    def next_track(self):
        self.command = 'next'
        return {'playback_state': 'playing'}

    def previous_track(self):
        self.command = 'previous'
        return {'playback_state': 'playing'}


class FakeAIClient:
    def __init__(self):
        self.calls = 0
        self.user_prompt = ''

    def analyze(self, system_prompt, user_prompt):
        self.calls += 1
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return json.dumps({
            'response': 'I would move from Captain Hollywood into DJ Sakin because it keeps the Euro dance lift but leans more trance and less cheesy.',
            'suggested_tracks': [
                {
                    'candidate_id': '200:1',
                    'reason': 'It keeps the 90s German club feeling while moving toward melodic trance.',
                    'confidence': 91,
                    'musical_dna': {
                        'shared': ['German 90s dance', 'melodic lift'],
                        'differs': ['less cheesy', 'more trance'],
                    },
                }
            ],
        })


class LargeFakeRepository(FakeRepository):
    def __init__(self):
        super().__init__()
        for index in range(3, 143):
            style = 'Trance' if index % 3 == 0 else 'Eurodance' if index % 3 == 1 else 'House'
            self.releases.append({
                'id': index,
                'release_id': index * 100,
                'title': f'Candidate Release {index}',
                'artists_sort': f'Artist {index}',
                'year': 1990 + (index % 18),
                'country': 'Germany' if index % 2 == 0 else 'Netherlands',
                'genres': ['Electronic'],
                'styles': [style],
                'labels': [{'name': 'Test Label'}],
                'deck_number': 1,
                'cd_position': index,
                'images': [{'uri': 'https://example.invalid/image.jpg'}],
                'identifiers': [{'type': 'Barcode', 'value': '123'}],
                'community': {'rating': {'count': index % 8, 'average': 4.0}},
                'tracklist': [{'position': '1', 'title': f'Candidate Track {index}', 'duration': '3:30'}],
                'ai': {
                    'version': 1,
                    'scene': f'German {style}',
                    'summary': f'A compact AI summary for {style}.',
                    'energy': 55 + (index % 40),
                    'danceability': 60 + (index % 35),
                    'euphoria': 50 + (index % 45),
                    'cheese': index % 70,
                    'commercial': index % 90,
                    'club': 50 + (index % 45),
                    'radio': index % 80,
                    'keywords': [style.lower(), 'melodic'],
                    'mood': ['night driving'] if index % 4 == 0 else ['club'],
                    'similar_artists': ['Captain Hollywood'] if index % 5 == 0 else [],
                    'driving_music': index % 4 == 0,
                    'festival': index % 6 == 0,
                },
            })


class ChatAPITest(unittest.TestCase):
    def setUp(self):
        self.repository = FakeRepository()
        self.runtime = FakePlaybackRuntime()
        self.ai_client = FakeAIClient()
        app = Flask(__name__)
        app.register_blueprint(create_chat_api(self.repository, self.runtime, ai_client=self.ai_client))
        self.client = app.test_client()

    def test_context_includes_collection_stats_and_now_playing(self):
        response = self.client.get('/api/chat/context')

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['current_track']['title'], 'Current Track')
        self.assertEqual(payload['collection']['release_count'], 2)
        self.assertEqual(payload['collection']['ai_enriched_release_count'], 2)
        self.assertEqual(payload['saved_playlists'][0]['name'], 'Test Session')

    def test_chat_returns_local_recommendations_with_actions(self):
        response = self.client.post('/api/chat', json={'message': 'More trance and less cheesy'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('DJ Sakin', payload['response'])
        self.assertEqual(payload['suggested_tracks'][0]['track']['release_id'], 200)
        self.assertEqual(payload['suggested_tracks'][0]['confidence'], 91)
        self.assertEqual(payload['suggested_tracks'][0]['actions'][0]['type'], 'play')
        self.assertEqual(self.ai_client.calls, 1)
        self.assertIn('candidate_tracks', self.ai_client.user_prompt)

    def test_chat_sends_large_compact_candidate_pool_to_ai(self):
        repository = LargeFakeRepository()
        runtime = FakePlaybackRuntime()
        ai_client = FakeAIClient()
        app = Flask(__name__)
        app.register_blueprint(create_chat_api(repository, runtime, ai_client=ai_client))
        client = app.test_client()

        response = client.post('/api/chat', json={'message': 'Night driving trance'})

        self.assertEqual(response.status_code, 200)
        prompt = json.loads(ai_client.user_prompt)
        candidates = prompt['candidate_tracks']
        self.assertEqual(prompt['candidate_count'], 100)
        self.assertEqual(len(candidates), 100)
        self.assertGreaterEqual(len({candidate['localGroup'] for candidate in candidates}), 2)
        self.assertIn('scene', candidates[0])
        self.assertIn('summary', candidates[0])
        self.assertIn('styles', candidates[0])
        self.assertIn('primaryStyle', candidates[0])
        self.assertNotIn('images', candidates[0])
        self.assertNotIn('identifiers', candidates[0])
        self.assertNotIn('release', candidates[0])

    def test_chat_prompt_preserves_precise_dance_taxonomy(self):
        response = self.client.post('/api/chat', json={'message': 'More Eurodance'})

        self.assertEqual(response.status_code, 200)
        prompt = json.loads(self.ai_client.user_prompt)
        self.assertTrue(any('do not flatten precise styles into Eurodance' in rule for rule in prompt['rules']))
        self.assertIn('primaryStyle', prompt['candidate_tracks'][0])
        self.assertIn('styles', prompt['candidate_tracks'][0])

    def test_play_endpoint_starts_recommended_track(self):
        track = {'title': 'Protect Your Mind', 'artist': 'DJ Sakin', 'deck_number': 1, 'cd_position': 11, 'position': '1'}
        response = self.client.post('/api/play', json={'track': track})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.runtime.played['title'], 'Protect Your Mind')

    def test_chat_analyzes_existing_playlist_by_name(self):
        response = self.client.post('/api/chat', json={'message': 'Test Session'})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn('Playlist Test Session has 2 tracks', payload['response'])
        self.assertEqual(payload['playlist_analysis']['top_styles'][0]['name'], 'Eurodance')
        self.assertEqual(self.ai_client.calls, 0)

    def test_chat_starts_existing_playlist_by_name(self):
        response = self.client.post('/api/chat', json={'message': 'pusti Test Session'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.runtime.played_playlist['name'], 'Test Session')
        self.assertEqual(response.get_json()['playback']['current_playlist'], 'Test Session')

    def test_chat_creates_playlist_from_local_candidates(self):
        response = self.client.post('/api/chat', json={'message': 'vytvor playlist Night Drive', 'limit': 3})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['playlist']['name'], 'Night Drive')
        self.assertEqual(self.repository.playlists[-1]['name'], 'Night Drive')
        self.assertGreaterEqual(len(payload['playlist']['tracks']), 1)
        self.assertEqual(self.ai_client.calls, 0)

    def test_chat_creates_playlist_from_recent_recommendations_when_user_says_from_that(self):
        recent_recommendations = [
            {
                'track': {
                    'release_id': 200,
                    'position': '1',
                    'title': 'Protect Your Mind',
                    'artist': 'DJ Sakin',
                    'full_name': 'DJ Sakin - Protect Your Mind',
                    'deck_number': 1,
                    'cd_position': 11,
                },
                'release': {'release_id': 200, 'title': 'German Trance Memory', 'artists_sort': 'DJ Sakin'},
                'reason': 'Recent chat recommendation',
                'confidence': 91,
                'musical_dna': {'shared': ['trance'], 'differs': ['less cheesy']},
                'actions': [{'type': 'play', 'label': 'Play'}],
            }
        ]

        response = self.client.post('/api/chat', json={
            'message': 'vytvor z toho playlist After Hours',
            'recent_recommendations': recent_recommendations,
            'limit': 5,
        })

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['playlist']['name'], 'After Hours')
        self.assertEqual(payload['playlist']['tracks'][0]['title'], 'Protect Your Mind')
        self.assertEqual(self.repository.playlists[-1]['tracks'][0]['title'], 'Protect Your Mind')
        self.assertEqual(self.ai_client.calls, 0)

    def test_chat_controls_cd_transport(self):
        response = self.client.post('/api/chat', json={'message': 'pause'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.runtime.command, 'pause')
        self.assertEqual(response.get_json()['playback']['playback_state'], 'paused')

    def test_recommendation_aliases_use_same_pipeline(self):
        current_response = self.client.get('/api/recommend/current?limit=1')
        recommend_response = self.client.post('/api/recommend', json={'message': 'More trance'})

        self.assertEqual(current_response.status_code, 200)
        self.assertEqual(recommend_response.status_code, 200)
        self.assertEqual(recommend_response.get_json()['suggested_tracks'][0]['track']['release_id'], 200)


if __name__ == '__main__':
    unittest.main()
