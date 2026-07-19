import unittest

from server.recommendation.engine import RecommendationEngine


class RecommendationEngineTest(unittest.TestCase):
    def setUp(self):
        self.engine = RecommendationEngine([
            {
                'id': 1,
                'title': 'Dubnobasswithmyheadman',
                'artists_sort': 'Underworld',
                'year': 1994,
                'genres': ['Electronic'],
                'styles': ['Progressive House'],
                'labels': [{'name': 'Junior Boy\'s Own'}],
                'deck_number': 1,
                'cd_position': 10,
                'images': [],
                'tracklist': [{'title': 'Cowgirl', '_score': 1}],
            },
            {
                'id': 2,
                'title': 'Second Toughest In The Infants',
                'artists_sort': 'Underworld',
                'year': 1996,
                'genres': ['Electronic'],
                'styles': ['Techno'],
                'labels': [{'name': 'Junior Boy\'s Own'}],
                'deck_number': 2,
                'cd_position': 12,
                'images': [],
                'tracklist': [{'title': 'Pearls Girl'}],
            },
            {
                'id': 3,
                'title': 'Dummy',
                'artists_sort': 'Portishead',
                'year': 1994,
                'genres': ['Electronic'],
                'styles': ['Trip Hop'],
                'labels': [{'name': 'Go! Beat'}],
                'deck_number': 1,
                'cd_position': 20,
                'images': [],
                'tracklist': [{'title': 'Sour Times'}],
            },
        ])

    def test_searches_case_insensitive_artist_and_style_indexes(self):
        results = self.engine.search({'artist': 'underworld', 'style': 'techno'})

        self.assertEqual([result['title'] for result in results], ['Second Toughest In The Infants'])

    def test_filters_by_deck_cd_position_and_favourites(self):
        results = self.engine.search({'deck': 1, 'cd_position': 10, 'favourites': 'true'})

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['title'], 'Dubnobasswithmyheadman')

    def test_respects_limit(self):
        results = self.engine.search({'genre': 'Electronic', 'limit': 2})

        self.assertEqual(len(results), 2)

    def test_q_searches_artist_album_and_track_startup_indexes(self):
        album_results = self.engine.search({'q': 'dummy'})
        track_results = self.engine.search({'q': 'pearls'})
        artist_results = self.engine.search({'q': 'underworld', 'limit': 5})

        self.assertEqual([result['title'] for result in album_results], ['Dummy'])
        self.assertEqual([result['title'] for result in track_results], ['Second Toughest In The Infants'])
        self.assertEqual(
            [result['title'] for result in artist_results],
            ['Dubnobasswithmyheadman', 'Second Toughest In The Infants'],
        )


if __name__ == '__main__':
    unittest.main()