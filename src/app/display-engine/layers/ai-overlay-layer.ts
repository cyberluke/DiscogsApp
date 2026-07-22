import { Graphics } from 'pixi.js';
import { DisplayTheme } from '../theme';
import { VisualizationFrame } from '../frame.model';
import { BaseLayer } from './base-layer';
import { LayerContext } from './layer';
import { drawText, textWidth } from '../bitmap-font';

/**
 * The "AI DJ" overlay: information the original hardware could never display,
 * rendered as a compact bitmap-text block in the bottom-right. No circular
 * widgets, no dashboard cards — just dense firmware-style readouts: BPM, key,
 * phrase position, mix countdown, and transition score. Kept under ~15% of the
 * display width so it never crowds the scene.
 */
export class AiOverlayLayer extends BaseLayer {
  readonly id = 'ai-overlay';
  readonly order = 60;

  private readonly gfx = new Graphics();

  private right = 0;
  private top = 0;
  private rowPitch = 8;

  protected override onInit(context: LayerContext): void {
    this.container.addChild(this.gfx);
    this.right = context.width - 10;
    this.top = context.height - 27;
  }

  protected onUpdate(frame: VisualizationFrame, _dt: number): void {
    const g = this.gfx;
    g.clear();

    const rows = this.buildRows(frame);
    for (let i = 0; i < rows.length; i++) {
      const text = rows[i];
      const width = textWidth(text, 1);
      // Subordinate: dim telemetry so the eye travels dolphin -> track -> waves.
      drawText(g, text, this.right - width, this.top + i * this.rowPitch, 1, this.theme.accent, 0.4);
    }
  }

  private buildRows(frame: VisualizationFrame): string[] {
    const bpm = frame.bpm > 0 ? `${Math.round(frame.bpm)}BPM` : '--BPM';
    const key = frame.key ?? '--';

    const phraseBeat = Math.round(frame.phraseProgress);
    const phrase = `PHR ${phraseBeat}/${frame.phraseLength}`;

    const seconds = frame.nextTransition?.seconds;
    const mix =
      seconds != null && seconds >= 0
        ? `MIX ${this.formatSeconds(seconds)}`
        : 'MIX --:--';

    const score = Math.round((frame.nextTransition?.score ?? 0) * 100);
    const ai = `AI ${score}%`;

    return [`${bpm} ${key}`, phrase, `${mix} ${ai}`];
  }

  private formatSeconds(total: number): string {
    const m = Math.floor(total / 60);
    const s = Math.ceil(total % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  protected override onTheme(_theme: DisplayTheme): void {
    /* colors read live in onUpdate() */
  }
}
