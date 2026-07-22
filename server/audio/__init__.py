"""Real-time audio analysis engine for the Pioneer Heritage Display.

This package performs all DSP (FFT, beat detection, BPM, energy bands)
on the backend. The frontend is a pure renderer and never touches audio.

The public entry point is :class:`server.audio.engine.AudioEngine`.
"""

from server.audio.engine import AudioEngine

__all__ = ["AudioEngine"]
