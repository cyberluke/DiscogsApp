import { Graphics } from 'pixi.js';
import { SPECTRUM_BANDS, VisualizationFrame } from '../frame.model';
import { BaseRenderer } from './renderer';

/**
 * SpectrumRenderer — the *supporting* element of the OEL scene.
 *
 * The original spectrum dominated the frame; on a Pioneer OEL unit the theme
 * leads and the spectrum is a compact, dimmer accent along the bottom. This
 * renderer draws fewer, shorter bands at reduced alpha so the eye is drawn to
 * the dolphin first and the spectrum second. Classic peak-hold caps are kept.
 */
export class SpectrumRenderer extends BaseRenderer {
  private readonly bands = 12;
  private readonly segments = 5;
  private readonly peakHold = 0.6;
  private readonly peakFall = 0.35;

  private smoothed = new Float32Array(this.bands);
  private peakValue = new Float32Array(this.bands);
  private peakHoldTimer = new Float32Array(this.bands);

  /** Last-drawn spectrum bounding box in internal pixels (for the debug overlay). */
  bounds = { x: 0, y: 0, w: 0, h: 0 };

  protected draw(g: Graphics, frame: VisualizationFrame | null, dt: number, _elapsed: number): void {
    const { width, height, theme } = this;

    // Compact, subordinate layout hugging the bottom edge. Deliberately short
    // and low-contrast so the dolphin leads and the spectrum is an accent.
    const marginX = width * 0.08;
    const bottom = height * 0.97;
    const barHeight = height * 0.13; // short — secondary
    const gap = 2;
    const bandWidth = (width - marginX * 2 - gap * (this.bands - 1)) / this.bands;
    const segHeight = (barHeight - (this.segments - 1)) / this.segments;

    // Record the spectrum band (for the debug overlay).
    this.bounds = { x: marginX, y: bottom - barHeight, w: width - marginX * 2, h: barHeight };

    const fft = frame?.fft;
    const binsPer = fft ? Math.floor(SPECTRUM_BANDS / this.bands) : 0;

    for (let b = 0; b < this.bands; b++) {
      let level = 0;
      if (fft && binsPer > 0) {
        let sum = 0;
        for (let i = 0; i < binsPer; i++) {
          sum += fft[b * binsPer + i];
        }
        level = sum / binsPer;
      }

      // Fast attack / slow release smoothing.
      const prev = this.smoothed[b];
      const target = level;
      const coeff = target > prev ? 0.6 : 0.18;
      const value = prev + (target - prev) * coeff;
      this.smoothed[b] = value;

      // Peak hold.
      if (value >= this.peakValue[b]) {
        this.peakValue[b] = value;
        this.peakHoldTimer[b] = this.peakHold;
      } else {
        this.peakHoldTimer[b] -= dt;
        if (this.peakHoldTimer[b] <= 0) {
          this.peakValue[b] = Math.max(value, this.peakValue[b] - this.peakFall * dt);
        }
      }

      const x = marginX + b * (bandWidth + gap);
      const litSegments = Math.round(value * this.segments);

      // Dim, low-contrast segments so the spectrum stays subordinate.
      for (let s = 0; s < this.segments; s++) {
        const y = bottom - (s + 1) * (segHeight + 1);
        const lit = s < litSegments;
        const color = s >= this.segments - 2 ? theme.sceneBright : theme.primary;
        g.rect(x, y, bandWidth, segHeight);
        g.fill({ color, alpha: lit ? 0.18 : 0.03 });
      }

      // Peak cap.
      const peakSeg = Math.round(this.peakValue[b] * this.segments);
      if (peakSeg > 0) {
        const py = bottom - peakSeg * (segHeight + 1);
        g.rect(x, py, bandWidth, segHeight);
        g.fill({ color: theme.core, alpha: 0.3 });
      }
    }
  }
}
