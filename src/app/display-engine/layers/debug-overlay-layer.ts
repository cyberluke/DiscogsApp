import { Graphics } from 'pixi.js';
import { BaseLayer } from './base-layer';
import { LayerContext } from './layer';
import { drawText } from '../bitmap-font';

/** A named bounding box to draw + report. */
export interface DebugBox {
  label: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Visual-weight metrics for a single element. */
export interface VisualWeight {
  label: string;
  /** Average luminance (0–255) of pixels inside the bounding box. */
  luminance: number;
  /** Number of lit pixels (luminance > threshold) inside the box. */
  occupiedPixels: number;
  /** Contrast vs. background (avg box luminance − avg background luminance). */
  contrast: number;
  /** Glow intensity: avg luminance in a 4px ring around the box. */
  glow: number;
  /** Composite visual-weight score (0–100). */
  score: number;
}

/** Live metrics the component feeds into the overlay each frame. */
export interface DebugMetrics {
  fps: number;
  bloom: number;
  persistence: number;
  boxes: DebugBox[];
  /** Per-element visual-weight metrics (computed from canvas pixels). */
  weights: VisualWeight[];
}

/**
 * DebugOverlayLayer — a toggleable diagnostic readout (press `D`).
 *
 * Draws the bounding boxes of the dolphin, waves and spectrum, plus a compact
 * metrics readout (FPS, bloom strength, persistence, and the % of display
 * height each element occupies). It exists so the composition can be tuned
 * against objective numbers instead of subjective impression — e.g.
 *
 *   DOLPHIN 42%  WAVE 15%  FFT 13%  BLOOM 0.45  PERS 0.50  60FPS
 *
 * Rendered last (highest order) so it always sits on top.
 */
export class DebugOverlayLayer extends BaseLayer {
  readonly id = 'debug-overlay';
  readonly order = 100;

  private readonly gfx = new Graphics();
  private visible = false;
  private metrics: DebugMetrics = { fps: 0, bloom: 0, persistence: 0, boxes: [], weights: [] };

  protected override onInit(context: LayerContext): void {
    this.container.addChild(this.gfx);
    this.container.visible = false;
    this.container.zIndex = 999;
    void context;
  }

  /** Toggle visibility (bound to the `D` key by the component). */
  toggle(): void {
    this.visible = !this.visible;
    this.container.visible = this.visible;
  }

  get isVisible(): boolean {
    return this.visible;
  }

  /** Feed fresh metrics for the current frame. */
  setMetrics(metrics: DebugMetrics): void {
    this.metrics = metrics;
  }

  protected override onUpdate(_frame: import('../frame.model').VisualizationFrame, _dt: number): void {
    if (!this.visible) {
      return;
    }
    this.draw();
  }

  private draw(): void {
    const g = this.gfx;
    const { height } = this.context;
    g.clear();

    // Bounding boxes + height-% labels.
    for (const box of this.metrics.boxes) {
      const pct = Math.round((box.h / height) * 100);
      g.rect(box.x, box.y, box.w, box.h);
      g.stroke({ color: 0xff4040, alpha: 0.9, width: 1 });
      drawText(g, `${box.label} ${pct}%`, box.x + 1, Math.max(1, box.y - 7), 1, 0xff4040, 0.95);
    }

    // Metrics readout along the very top.
    const m = this.metrics;
    const line =
      `${Math.round(m.fps)}FPS ` +
      `BLOOM ${m.bloom.toFixed(2)} ` +
      `PERS ${m.persistence.toFixed(2)}`;
    drawText(g, line, 4, 2, 1, 0x40ff80, 0.95);

    // Visual-weight readout (second line).
    if (m.weights.length > 0) {
      const wLine = m.weights
        .map((w) => `${w.label}:${w.score}`)
        .join(' ');
      drawText(g, wLine, 4, 10, 1, 0xffff40, 0.9);
    }
  }
}
