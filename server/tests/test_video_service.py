import tempfile
import unittest
from pathlib import Path

from server.services.video import VideoAudioAnalyzer, VideoCache, VideoLibraryService, VideoOffsetStore, VideoSyncService
from server.services.video.service import VideoCandidate


class FakeResolver:
    def __init__(self, candidate=None):
        self.candidate = candidate

    def resolve(self, artist, title, duration=None):
        return self.candidate


class FakeAcquisitionProvider:
    def download(self, candidate, output_template):
        path = Path(str(output_template).replace('%(ext)s', 'mp4'))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'fake video')
        return path


class FakePlaybackRuntime:
    def __init__(self, status):
        self._status = status

    def status(self):
        return self._status


class FakeAudioAnalyzer:
    def __init__(self, offset):
        self.offset = offset

    def intro_silence_offset(self, path):
        return self.offset


class VideoLibraryServiceTest(unittest.TestCase):
    def test_resolve_prefers_existing_local_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'pitbull timber official.mp4'
            path.write_bytes(b'fake video')
            cache = VideoCache([temp_dir])
            service = VideoLibraryService(cache, resolvers=[FakeResolver()])

            result = service.resolve(artist='Pitbull', title='Timber')

            self.assertEqual(result['video']['provider'], 'local')
            self.assertEqual(result['video']['url'], '/video/local/pitbull timber official.mp4')
            self.assertFalse(result['can_download'])

    def test_resolve_offers_download_when_local_file_is_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = VideoCandidate(
                provider='youtube',
                provider_id='abc123',
                title='Pitbull - Timber',
                channel='PitbullVEVO',
                source_url='https://www.youtube.com/watch?v=abc123',
                artist='Pitbull',
                track='Timber',
            )
            cache = VideoCache([temp_dir])
            service = VideoLibraryService(cache, resolvers=[FakeResolver(candidate)], acquisition_provider=FakeAcquisitionProvider())

            result = service.resolve(artist='Pitbull', title='Timber')

            self.assertIsNone(result['video'])
            self.assertEqual(result['candidate']['provider'], 'youtube')
            self.assertTrue(result['can_download'])

    def test_download_creates_local_video_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate = VideoCandidate(
                provider='youtube',
                provider_id='abc123',
                title='Pitbull - Timber',
                channel='PitbullVEVO',
                source_url='https://www.youtube.com/watch?v=abc123',
                artist='Pitbull',
                track='Timber',
            )
            cache = VideoCache([temp_dir])
            service = VideoLibraryService(cache, resolvers=[FakeResolver(candidate)], acquisition_provider=FakeAcquisitionProvider())

            result = service.download(artist='Pitbull', title='Timber')

            self.assertEqual(result['video']['provider'], 'local')
            self.assertTrue(result['video']['url'].startswith('/video/local/'))
            self.assertFalse(result['can_download'])

    def test_sync_state_uses_playback_timing_without_downloading(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'pitbull timber official.mp4'
            path.write_bytes(b'fake video')
            cache = VideoCache([temp_dir])
            library = VideoLibraryService(cache, resolvers=[])
            runtime = FakePlaybackRuntime({
                'current_track': {'artist': 'Pitbull', 'title': 'Timber'},
                'elapsed': 42,
                'playback_state': 'playing',
            })
            sync = VideoSyncService(library, runtime)

            result = sync.current_state()

            self.assertEqual(result['seek_seconds'], 42)
            self.assertTrue(result['should_play'])
            self.assertEqual(result['video']['provider'], 'local')

    def test_sync_state_uses_persisted_manual_video_offset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'a teens floorfiller official.mp4'
            path.write_bytes(b'fake video')
            cache = VideoCache([temp_dir], audio_analyzer=FakeAudioAnalyzer(9))
            library = VideoLibraryService(cache, resolvers=[])
            runtime = FakePlaybackRuntime({
                'current_track': {'artist': 'A-Teens', 'title': 'Floorfiller'},
                'elapsed': 23,
                'playback_state': 'playing',
            })
            sync = VideoSyncService(library, runtime, VideoOffsetStore(Path(temp_dir) / 'video_offsets.json'))

            saved = sync.save_current_offset_preference(-1, False)
            result = sync.current_state()

            self.assertEqual(saved['video']['manual_offset_seconds'], -1)
            self.assertFalse(saved['video']['use_detected_offset'])
            self.assertEqual(saved['video']['effective_offset_seconds'], -1)
            self.assertEqual(result['seek_seconds'], 22)

    def test_local_video_result_uses_detected_intro_silence_offset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'a teens floorfiller official.mp4'
            path.write_bytes(b'fake video')
            cache = VideoCache([temp_dir], audio_analyzer=FakeAudioAnalyzer(2))

            result = cache.locate('A-Teens', 'Floorfiller')

            self.assertEqual(result['offset_seconds'], 2)
            self.assertEqual(result['offset_parts'], [0, 0, 2])
            self.assertEqual(result['offset_source'], 'audio_intro_detect')

    def test_audio_analyzer_parses_only_intro_silence(self):
        analyzer = VideoAudioAnalyzer()

        intro_output = '''
[silencedetect @ 000001] silence_start: 0
[silencedetect @ 000001] silence_end: 2.14 | silence_duration: 2.14
'''
        middle_output = '''
[silencedetect @ 000001] silence_start: 42.7
[silencedetect @ 000001] silence_end: 44.2 | silence_duration: 1.5
'''

        self.assertEqual(analyzer._parse_intro_silence(intro_output), 2)
        self.assertEqual(analyzer._parse_intro_silence(middle_output), 0)

    def test_audio_analyzer_detects_sustained_main_program_after_noisy_intro(self):
        analyzer = VideoAudioAnalyzer()
        envelope = [0, 0, 0, 0]
        envelope.extend([1800, 2600, 2300, 2400] * 8)
        envelope.extend([4300, 4100, 5200, 3900, 4500, 4200, 5100, 3800, 4400, 4100, 5000, 3900])
        envelope.extend([4500] * 40)

        offset = analyzer._detect_main_program_offset(envelope)

        self.assertGreaterEqual(offset, 8)
        self.assertLessEqual(offset, 9)


if __name__ == '__main__':
    unittest.main()