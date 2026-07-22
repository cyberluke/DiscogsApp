import { Graphics } from 'pixi.js';
import { VisualizationFrame } from '../frame.model';
import { BaseRenderer } from './renderer';

/**
 * WaveRenderer — the living water surface of the OEL scene.
 *
 * The original waves were thin 1px lines that read as static. A Pioneer OEL
 * water scene has *wide, soft, rolling* bands with a bright crest and a deep
 * trough, gently modulated by the music (bass swells the amplitude, energy
 * adds shimmer). Waves are drawn as filled ribbons with a bright crest edge so
 * they feel volumetric and alive rather than wireframe.
 */
export class WaveRenderer extends BaseRenderer {
  /** Vertical position of the waterline (fraction of height). */
  private readonly waterY = 0.66;
  /** Number of thin wave lines receding into the distance. */
  private readonly rows = 2;
  /** Total vertical band the waves may occupy (fraction of height). ≤ 15%. */
  private readonly bandHeight = 0.10;

  /** Last-drawn wave band bounding box in internal pixels (for the debug overlay). */
  bounds = { x: 0, y: 0, w: 0, h: 0 };

  protected draw(g: Graphics, frame: VisualizationFrame | null, _dt: number, elapsed: number): void {
    const { width, height, theme } = this;
    const baseY = height * this.waterY;
    const bass = frame?.bass ?? 0;
    const energy = frame?.energy ?? 0;

    // Spread the rows across the band, front row at the waterline.
    const rowSpacing = (height * this.bandHeight) / this.rows;

    // Record the band the waves occupy (full width, from waterline to band bottom).
    this.bounds = { x: 0, y: baseY - 3, w: width, h: height * this.bandHeight + 6 };

    for (let row = 0; row < this.rows; row++) {
      const depth = row / (this.rows - 1); // 0 = front (bright), 1 = back (dim)
      const rowY = baseY + row * rowSpacing;
      // Small amplitude — these are elegant lines, not swells. Bass adds a touch.
      const amp = (1.2 + depth * 1.6) * (1 + bass * 0.8);
      const speed = 0.9 + depth * 0.5;
      const wavelength = 30 + depth * 24;
      const phase = elapsed * speed + row * 1.7;

      // Build a single thin polyline.
      const line: number[] = [];
      for (let x = 0; x <= width; x += 4) {
        const y =
          rowY +
          Math.sin((x / wavelength) * Math.PI * 2 + phase) * amp +
          Math.sin((x / (wavelength * 0.5)) * Math.PI * 2 - phase * 1.3) * amp * 0.3;
        line.push(x, y);
      }

      // Subordinate: dim, low-contrast lines that never compete with the dolphin.
      const color = theme.sceneBright;
      const alpha = (0.10 + energy * 0.06) * (1 - depth * 0.4);
      g.poly(line);
      g.stroke({ color, alpha, width: 1 });
    }
  }
}
