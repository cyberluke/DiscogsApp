"""Tests for the Pioneer Heritage Display audio analysis engine."""

import math
import unittest

import numpy as np

from server.audio.analyzer import SpectrumAnalyzer, RingBuffer
from server.audio.beat import BeatDetector
from server.audio.frames import FrameBuilder
from server.audio.engine import AudioEngine


SAMPLE_RATE = 44100


def _sine(freq: float, seconds: float, amplitude: float = 0.8) -> np.ndarray:
    """Mono sine wave as interleaved stereo float32."""
    n = int(seconds * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    mono = (amplitude * np.sin(2 * math.pi * freq * t)).astype(np.float32)
    return np.column_stack((mono, mono))


class RingBufferTest(unittest.TestCase):
    def test_latest_returns_written_frames(self):
        buf = RingBuffer(capacity=8, channels=2)
        frames = np.arange(12, dtype=np.float32).reshape(6, 2)
        buf.write(frames)
        latest = buf.latest(4)
        np.testing.assert_array_equal(latest, frames[-4:])

    def test_wraparound(self):
        buf = RingBuffer(capacity=4, channels=1)
        buf.write(np.array([[1], [2], [3]], dtype=np.float32))
        buf.write(np.array([[4], [5], [6]], dtype=np.float32))
        latest = buf.latest(4)
        np.testing.assert_array_equal(latest.flatten(), [3, 4, 5, 6])


class SpectrumAnalyzerTest(unittest.TestCase):
    def test_fft_peak_at_expected_band_for_440hz(self):
        analyzer = SpectrumAnalyzer(sample_rate=SAMPLE_RATE, fft_size=2048, num_bands=128)
        analyzer.push(_sine(440.0, 0.1))
        features = analyzer.analyze()
        fft = features["fft"]
        peak_band = int(np.argmax(fft))
        # 440 Hz in a log-spaced 128-band analyzer (20 Hz–20 kHz) maps to
        # band ≈ 128 * log10(440/20) / log10(20000/20) ≈ 57.
        self.assertGreater(fft[peak_band], 0.0)
        self.assertAlmostEqual(peak_band, 57, delta=3)

    def test_silence_produces_near_zero(self):
        analyzer = SpectrumAnalyzer(sample_rate=SAMPLE_RATE, fft_size=2048, num_bands=128)
        analyzer.push(np.zeros((2048, 2), dtype=np.float32))
        features = analyzer.analyze()
        self.assertLess(float(np.max(features["fft"])), 0.05)
        self.assertAlmostEqual(features["energy"], 0.0, places=2)

    def test_vu_levels_scale_with_amplitude(self):
        analyzer = SpectrumAnalyzer(sample_rate=SAMPLE_RATE, fft_size=2048, num_bands=128)
        analyzer.push(_sine(1000.0, 0.1, amplitude=0.9))
        loud = analyzer.analyze()
        analyzer.reset()
        analyzer.push(_sine(1000.0, 0.1, amplitude=0.1))
        quiet = analyzer.analyze()
        self.assertGreater(loud["vu_left"], quiet["vu_left"])

    def test_bass_energy_higher_for_low_frequency(self):
        analyzer = SpectrumAnalyzer(sample_rate=SAMPLE_RATE, fft_size=2048, num_bands=128)
        analyzer.push(_sine(80.0, 0.1))
        bass_heavy = analyzer.analyze()
        analyzer.reset()
        analyzer.push(_sine(8000.0, 0.1))
        treble_heavy = analyzer.analyze()
        self.assertGreater(bass_heavy["bass"], treble_heavy["bass"])
        self.assertGreater(treble_heavy["treble"], bass_heavy["treble"])


class BeatDetectorTest(unittest.TestCase):
    def test_bpm_estimation_near_120(self):
        detector = BeatDetector(sample_rate=SAMPLE_RATE, frame_rate=60.0)
        # Simulate a 120 BPM kick: onset every 0.5 s => every 30 frames.
        beat_frames = 0
        for frame in range(60 * 12):  # 12 seconds
            onset = 1.0 if frame % 30 == 0 else 0.0
            result = detector.update(onset, energy=onset)
            if result["beat"]:
                beat_frames += 1
        self.assertAlmostEqual(detector.bpm, 120.0, delta=15.0)
        self.assertGreater(beat_frames, 10)

    def test_phrase_progress_wraps(self):
        detector = BeatDetector(phrase_length=4)
        progresses = []
        for frame in range(60 * 6):
            onset = 1.0 if frame % 30 == 0 else 0.0
            result = detector.update(onset, energy=onset)
            if result["beat"]:
                progresses.append(result["phraseProgress"])
        # With phrase length 4, progress values stay in [0, 3].
        self.assertTrue(all(0 <= p < 4 for p in progresses))


class FrameBuilderTest(unittest.TestCase):
    def test_frame_schema(self):
        analyzer = SpectrumAnalyzer(sample_rate=SAMPLE_RATE, fft_size=2048, num_bands=128)
        analyzer.push(_sine(440.0, 0.1))
        detector = BeatDetector()
        status = {
            "current_track": {"artist": "Cappella", "title": "U & Me"},
            "remaining": 120,
        }
        builder = FrameBuilder(analyzer, detector, lambda: status)
        frame = builder.build()

        self.assertEqual(len(frame["fft"]), 128)
        self.assertIn("vuLeft", frame)
        self.assertIn("vuRight", frame)
        self.assertIn("bass", frame)
        self.assertIn("beat", frame)
        self.assertIn("bpm", frame)
        self.assertEqual(frame["track"]["artist"], "Cappella")
        self.assertEqual(frame["track"]["title"], "U & Me")
        self.assertIn("seconds", frame["nextTransition"])
        self.assertIn("score", frame["nextTransition"])

    def test_frame_handles_missing_track(self):
        analyzer = SpectrumAnalyzer()
        detector = BeatDetector()
        builder = FrameBuilder(analyzer, detector, lambda: {})
        frame = builder.build()
        self.assertEqual(frame["track"]["artist"], "")
        self.assertEqual(frame["track"]["title"], "")
        self.assertIsNone(frame["nextTransition"]["seconds"])


class AudioEngineTest(unittest.TestCase):
    def test_engine_publishes_frames_to_subscriber(self):
        engine = AudioEngine(
            status_provider=lambda: {"current_track": None, "remaining": None},
            capture_audio_provider=lambda: None,
            device_discoverer=None,
            frame_rate=60.0,
        )
        # Feed synthetic audio directly into the analyzer (bypass device).
        engine.analyzer.push(_sine(440.0, 0.1))

        received = []
        engine.subscribe(lambda frame: received.append(frame))

        # Run the loop briefly by calling the internal loop logic manually.
        for _ in range(5):
            frame = engine.frame_builder.build()
            engine._publish(frame)

        self.assertEqual(len(received), 5)
        self.assertEqual(len(received[0]["fft"]), 128)

    def test_unsubscribe_stops_delivery(self):
        engine = AudioEngine(status_provider=lambda: {}, frame_rate=60.0)
        received = []
        unsubscribe = engine.subscribe(lambda frame: received.append(frame))
        engine._publish({"fft": []})
        unsubscribe()
        engine._publish({"fft": []})
        self.assertEqual(len(received), 1)


if __name__ == "__main__":
    unittest.main()
