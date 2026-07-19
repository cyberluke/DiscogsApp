import unittest

from flask import Flask

from server.api.ai import create_ai_api


class FakeRepository:
    def __init__(self):
        self.release = {'release_id': 10, 'title': 'Release', 'ai': {'version': 1, 'scene': 'Euro House'}}

    def get_release_by_id(self, release_id):
        return self.release if release_id == 10 else None


class FakeMusicAnalysisService:
    def __init__(self):
        self.force = None

    def get_release_ai(self, release_id):
        release = FakeRepository().get_release_by_id(release_id)
        return release.get('ai') if release else None

    def enrich_release(self, release_id, force=False):
        self.force = force
        if release_id != 10:
            return None
        return {'version': 1, 'scene': 'Euro House'}

    def enrich_all(self, force=False, limit=None):
        return {'enriched': 1, 'skipped': 0, 'missing': 0, 'errors': [], 'force': force, 'limit': limit}


class AIAPIITest(unittest.TestCase):
    def setUp(self):
        self.repository = FakeRepository()
        self.service = FakeMusicAnalysisService()
        app = Flask(__name__)
        app.register_blueprint(create_ai_api(self.repository, self.service))
        self.client = app.test_client()

    def test_release_and_cached_ai_routes(self):
        self.assertEqual(self.client.get('/api/releases/10').get_json()['title'], 'Release')
        self.assertEqual(self.client.get('/api/releases/10/ai').get_json()['scene'], 'Euro House')
        self.assertEqual(self.client.get('/api/releases/999').status_code, 404)

    def test_enrich_release_route_supports_force(self):
        response = self.client.post('/api/ai/enrich/10?force=true')

        self.assertEqual(response.get_json()['scene'], 'Euro House')
        self.assertTrue(self.service.force)

    def test_enrich_all_route_supports_limit(self):
        response = self.client.post('/api/ai/enrich-all?limit=5')

        self.assertEqual(response.get_json()['limit'], 5)


if __name__ == '__main__':
    unittest.main()