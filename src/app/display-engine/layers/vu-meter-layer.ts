import { Graphics } from 'pixi.js';
import { DisplayTheme } from '../theme';
import { VisualizationFrame } from '../frame.model';
import { BaseLayer } from './base-layer';
import { LayerContext } from './layer';
import { drawText } from '../bitmap-font';

const SEGMENTS = 16;
const PEAK_FALL_PER_SEC = 1.4; // full-scale fractions per second
const PEAK_HOLD_SECONDS = 0.5;
/** Level above which the overload flash fires. */
const OVERLOAD_LEVEL = 0.92;
/** Seconds the overload flash stays lit. */
const OVERLOAD_FLASH_SECONDS = 0.18;

interface MeterState {
  level: number;
  peak: number;
  holdTimer: number;
  overloadTimer: number;
}

/**
 * Stereo VU meters in the bottom-left, rendered as horizontal segmented bars
 * with bitmap L/R labels, falling peak markers, and an overload flash when a
 * channel clips — the classic head-unit level display.
 */
export class VuMeterLayer extends BaseLayer {
  readonly id = 'vu';
  readonly order = 40;

  private readonly gfx = new Graphics();

  private left: MeterState = { level: 0, peak: 0, holdTimer: 0, overloadTimer: 0 };
  private right: MeterState = { level: 0, peak: 0, holdTimer: 0, overloadTimer: 0 };

  private x = 0;
  private yL = 0;
  private yR = 0;
  private meterHeight = 0;
  private segWidth = 0;

  protected override onInit(context: LayerContext): void {
    this.container.addChild(this.gfx);

    // Bottom-left block: bitmap L/R labels + segmented bars.
    this.x = 16; // leave room for the label at x=10
    this.yL = context.height - 25;
    this.yR = context.height - 14;
    this.meterHeight = 7;
    this.segWidth = 6;
  }

  protected onUpdate(frame: VisualizationFrame, dt: number): void {
    this.updateMeter(this.left, frame.vuLeft, dt);
    this.updateMeter(this.right, frame.vuRight, dt);

    const g = this.gfx;
    g.clear();

    drawText(g, 'L', 10, this.yL + 1, 1, this.theme.textColor);
    drawText(g, 'R', 10, this.yR + 1, 1, this.theme.textColor);

    this.drawMeter(this.yL, this.left);
    this.drawMeter(this.yR, this.right);
  }

  private updateMeter(state: MeterState, level: number, dt: number): void {
    // Smooth decay for a hardware feel.
    state.level =
      level > state.level
        ? state.level * 0.3 + level * 0.7
        : state.level * 0.85 + level * 0.15;

    if (level >= state.peak) {
      state.peak = level;
      state.holdTimer = PEAK_HOLD_SECONDS;
    } else if (state.holdTimer > 0) {
      state.holdTimer -= dt;
    } else {
      state.peak = Math.max(level, state.peak - PEAK_FALL_PER_SEC * dt);
    }

    if (level >= OVERLOAD_LEVEL) {
      state.overloadTimer = OVERLOAD_FLASH_SECONDS;
    } else if (state.overloadTimer > 0) {
      state.overloadTimer -= dt;
    }
  }

  private drawMeter(top: number, state: MeterState): void {
    const g = this.gfx;
    const lit = Math.round(state.level * SEGMENTS);
    const peakSeg = Math.round(state.peak * SEGMENTS);
    const overloading = state.overloadTimer > 0;

    for (let s = 0; s < SEGMENTS; s++) {
      const x = this.x + s * (this.segWidth + 1);
      const ratio = s / SEGMENTS;

      if (s < lit) {
        // Overload flashes the whole lit run to the brightest phosphor.
        const color = overloading && ratio > 0.7 ? this.theme.highlight : this.colorForRatio(ratio);
        g.rect(x, top, this.segWidth, this.meterHeight)
          .fill({ color, alpha: 0.5 });
      } else if (s === peakSeg - 1 && state.peak > 0.03) {
        g.rect(x, top, this.segWidth, this.meterHeight)
          .fill({ color: this.theme.highlight, alpha: 0.5 });
      } else {
        g.rect(x, top, this.segWidth, this.meterHeight)
          .fill({ color: this.theme.dim, alpha: 0.08 });
      }
    }
  }

  private colorForRatio(ratio: number): number {
    if (ratio > 0.8) {
      return this.theme.vuHigh;
    }
    if (ratio > 0.5) {
      return this.theme.vuMid;
    }
    return this.theme.vuLow;
  }

  protected override onTheme(_theme: DisplayTheme): void {
    /* colors read live in drawMeter() */
  }
}
