import json
import os
import tempfile
import unittest

from server.repository.local import LocalDataRepository
from server.services.ai import AzureOpenAIClient, MusicAnalysisParser, MusicAnalysisPrompt, MusicAnalysisService


class FakeAIClient:
    def __init__(self):
        self.calls = 0

    def analyze(self, system_prompt, user_prompt):
        self.calls += 1
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return json.dumps({
            'scene': 'German Eurodance',
            'summary': 'A specific club-pop crossover release with strong radio DNA. It fits the early 90s European dance boom and works for listeners who like polished hooks.',
            'energy': 88,
            'danceability': 92,
            'euphoria': 81,
            'nostalgia': 77,
            'commercial': 85,
            'club': 72,
            'radio': 90,
            'cheese': 41,
            'guilty_pleasure': False,
            'driving_music': True,
            'late_night': False,
            'festival': True,
            'mood': ['Driving', 'Party'],
            'recommended_after': ['Magic Affair', 'Intermission', 'Pharao'],
            'similar_artists': ['Captain Hollywood', 'Culture Beat', 'Masterboy'],
            'keywords': ['eurodance', 'radio edit'],
        })


class FakeChatCompletions:
    def create(self, **kwargs):
        self.kwargs = kwargs

        class Message:
            content = '{}'

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()


class FakeOpenAIClient:
    def __init__(self):
        self.chat = type('Chat', (), {'completions': FakeChatCompletions()})()


class MusicAnalysisServiceTest(unittest.TestCase):
    def test_enriches_once_and_returns_cached_ai_afterwards(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = self.make_repository(temp_dir)
            client = FakeAIClient()
            service = MusicAnalysisService(repository, client=client)

            first = service.enrich_release(100)
            second = service.enrich_release(100)
            saved_release = repository.get_release_by_id(100)

            self.assertEqual(client.calls, 1)
            self.assertEqual(first, second)
            self.assertEqual(saved_release['ai']['version'], 2)
            self.assertEqual(saved_release['ai']['scene'], 'German Eurodance')
            self.assertIn('Artist', client.user_prompt)
            self.assertNotIn('images', client.user_prompt.lower())

    def test_force_regenerates_ai(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = self.make_repository(temp_dir)
            client = FakeAIClient()
            service = MusicAnalysisService(repository, client=client)

            service.enrich_release(100)
            service.enrich_release(100, force=True)

            self.assertEqual(client.calls, 2)

    def test_cached_ai_is_synced_to_duplicate_release_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = self.make_repository(temp_dir, releases=[
                {**self.release(), 'id': 1, 'title': 'Title (CD 1)', 'ai': {'version': 2, 'scene': 'Cached Scene'}},
                {**self.release(), 'id': 2, 'title': 'Title (CD 2)'},
            ])
            client = FakeAIClient()
            service = MusicAnalysisService(repository, client=client)

            service.enrich_release(100)

            releases = repository.all_releases()
            self.assertEqual(client.calls, 0)
            self.assertEqual(releases[0]['ai']['scene'], 'Cached Scene')
            self.assertEqual(releases[1]['ai']['scene'], 'Cached Scene')

    def test_parser_clamps_scores_and_normalizes_lists(self):
        parsed = MusicAnalysisParser().parse({
            'scene': 'Euro House',
            'summary': 'Specific summary.',
            'energy': 150,
            'danceability': -10,
            'mood': ['Club', '', 'Night Drive'],
        })

        self.assertEqual(parsed['energy'], 100)
        self.assertEqual(parsed['danceability'], 0)
        self.assertEqual(parsed['mood'], ['Club', 'Night Drive'])
        self.assertFalse(parsed['guilty_pleasure'])

    def test_prompt_uses_discogs_context_without_images(self):
        release = self.release()
        _, user_prompt = MusicAnalysisPrompt().build(release)

        self.assertIn('Artist', user_prompt)
        self.assertIn('German Dance', user_prompt)
        self.assertNotIn('cover.jpg', user_prompt)

    def test_azure_client_uses_model_default_temperature(self):
        openai_client = FakeOpenAIClient()
        client = AzureOpenAIClient(endpoint='https://example.test/openai/v1', api_key='key', model='gpt-test')
        client._client = openai_client

        client.analyze('system', 'user')

        self.assertNotIn('temperature', openai_client.chat.completions.kwargs)
        self.assertEqual(openai_client.chat.completions.kwargs['response_format'], {'type': 'json_object'})

    def make_repository(self, temp_dir, releases=None):
        releases_path = os.path.join(temp_dir, 'releases.json')
        playlists_path = os.path.join(temp_dir, 'playlists.json')
        video_offsets_path = os.path.join(temp_dir, 'video_offsets.json')
        self.write_json(releases_path, releases or [self.release()])
        self.write_json(playlists_path, [])
        self.write_json(video_offsets_path, [])
        return LocalDataRepository(
            releases_path=releases_path,
            playlists_path=playlists_path,
            video_offsets_path=video_offsets_path,
        )

    def release(self):
        return {
            'id': 1,
            'release_id': 100,
            'artists_sort': 'Artist',
            'title': 'Title',
            'year': 1995,
            'country': 'Germany',
            'labels': [{'name': 'Dance Label'}],
            'companies': [{'name': 'Pressing Plant'}],
            'genres': ['Electronic'],
            'styles': ['German Dance'],
            'tracklist': [{'position': '1', 'title': 'Track', 'duration': '3:30'}],
            'notes': 'Club hit notes.',
            'community': {'rating': {'average': 4.2, 'count': 5}},
            'images': [{'uri': 'cover.jpg'}],
        }

    def write_json(self, path, payload):
        with open(path, 'w', encoding='utf-8') as file:
            json.dump({'data': payload}, file)


if __name__ == '__main__':
    unittest.main()