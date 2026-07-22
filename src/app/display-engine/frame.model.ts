/**
 * Frame model for the Pioneer Heritage Display Engine.
 *
 * These interfaces mirror the payload produced by the backend
 * `server/audio/frames.py` FrameBuilder and delivered over the
 * `/visualization/frames` WebSocket. The backend owns all DSP; the frontend
 * is a pure renderer that interpolates between received frames.
 */

export interface FrameTrackInfo {
  artist: string;
  title: string;
}

export interface FrameTransition {
  /** Seconds until the next detected transition (or null when unknown). */
  seconds: number | null;
  /** Confidence/score of the upcoming transition (0..1). */
  score: number;
}

export interface VisualizationFrame {
  /** Backend monotonic timestamp (seconds) when the frame was built. */
  timestamp: number;

  /** 128 log-spaced spectrum bands (20 Hz – 20 kHz), smoothed, 0..1. */
  fft: number[];
  /** 128 falling peak-hold values aligned with `fft`, 0..1. */
  peaks: number[];

  /** Stereo VU (RMS) levels, 0..1. */
  vuLeft: number;
  vuRight: number;
  /** Stereo peak-hold levels, 0..1. */
  peakLeft: number;
  peakRight: number;

  /** Band energy summaries, 0..1. */
  bass: number;
  mid: number;
  treble: number;
  /** Overall loudness energy, 0..1. */
  energy: number;
  /** Stereo width, 0 (mono) .. 1 (wide). */
  width: number;

  /** True on the frame where a beat onset was detected. */
  beat: boolean;
  /** Estimated tempo in beats per minute. */
  bpm: number;
  /** Camelot wheel key (e.g. "8A"), or null when unknown. */
  key: string | null;
  /** Progress through the current musical phrase, 0..1. */
  phraseProgress: number;
  /** Length of a phrase in beats (default 32). */
  phraseLength: number;

  track: FrameTrackInfo;
  nextTransition: FrameTransition;
}

/** Number of spectrum bands delivered per frame. */
export const SPECTRUM_BANDS = 128;
