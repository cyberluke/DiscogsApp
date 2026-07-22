import { Graphics } from 'pixi.js';
import { DisplayTheme } from '../theme';
import { VisualizationFrame } from '../frame.model';
import { BaseLayer } from './base-layer';
import { LayerContext } from './layer';

/**
 * Deep vertical gradient background with a subtle bass-driven brightness pulse
 * and a very slow ambient drift, evoking the lit phosphor bed of an OEL
 * display. This is the slowest-moving layer in the motion hierarchy — it
 * breathes almost imperceptibly behind the scene and meters.
 */
export class BackgroundLayer extends BaseLayer {
  readonly id = 'background';
  readonly order = 0;

  private readonly gfx = new Graphics();
  private pulse = 0;
  private drift = 0;

  protected override onInit(_context: LayerContext): void {
    this.container.addChild(this.gfx);
  }

  protected onUpdate(frame: VisualizationFrame, dt: number): void {
    // Fast attack on bass energy, slow release for a breathing glow.
    const target = frame.bass;
    const rate = target > this.pulse ? 12 : 2.5;
    this.pulse += (target - this.pulse) * Math.min(1, rate * dt);

    // Extremely slow ambient drift for the motion hierarchy.
    this.drift += dt * 0.05;

    this.draw();
  }

  protected override onTheme(_theme: DisplayTheme): void {
    this.draw();
  }

  private draw(): void {
    const { width, height } = this.context;
    const g = this.gfx;
    g.clear();

    // Base fill.
    g.rect(0, 0, width, height).fill(this.theme.backgroundDeep);

    // Top gradient band brightened by the bass pulse and shifted by the drift.
    const glow = 0.06 + this.pulse * 0.12;
    const driftX = Math.sin(this.drift) * width * 0.06;
    g.rect(driftX - width * 0.1, 0, width * 1.2, height * 0.55)
      .fill({ color: this.theme.background, alpha: 0.5 + glow });

    // Faint horizon line near the lower third.
    g.rect(0, height * 0.62, width, 1)
      .fill({ color: this.theme.dim, alpha: 0.4 + this.pulse * 0.3 });
  }
}
