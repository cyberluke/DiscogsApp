import { Container, Graphics } from 'pixi.js';
import { VisualizationFrame } from '../frame.model';
import { DisplayTheme } from '../theme';

/**
 * Contract for a modular renderer in the Pioneer OEL pipeline.
 *
 * Unlike the old `Layer` abstraction, renderers are *passive drawing modules*:
 * they own a `Container` and redraw it every animation frame at full display
 * rate. There is no internal frame throttling — motion is driven purely by
 * wall-clock time (`elapsed`) plus the (already interpolated) audio frame, so
 * the scene animates at the monitor's refresh rate (~60 fps) without stutter.
 */
export interface IRenderer {
  readonly container: Container;
  onInit?(width: number, height: number, theme: DisplayTheme): void;
  /**
   * Redraw for the current frame into the renderer's own graphics surface.
   * @param frame  latest interpolated visualization frame (may be null before
   *               the socket delivers data — render an idle pose)
   * @param dt     seconds since the previous frame
   * @param elapsed total seconds since the renderer was created (drives motion)
   */
  render(frame: VisualizationFrame | null, dt: number, elapsed: number): void;
  onTheme(theme: DisplayTheme): void;
  destroy(): void;
}

/**
 * Shared base: owns the container + a single reusable Graphics surface that is
 * cleared and redrawn each frame.
 */
export abstract class BaseRenderer implements IRenderer {
  readonly container = new Container();
  protected readonly g = new Graphics();
  protected width = 320;
  protected height = 128;
  protected theme!: DisplayTheme;

  constructor() {
    this.container.addChild(this.g);
  }

  onInit(width: number, height: number, theme: DisplayTheme): void {
    this.width = width;
    this.height = height;
    this.theme = theme;
    this.onTheme(theme);
  }

  onTheme(theme: DisplayTheme): void {
    this.theme = theme;
  }

  render(frame: VisualizationFrame | null, dt: number, elapsed: number): void {
    this.g.clear();
    this.draw(this.g, frame, dt, elapsed);
  }

  protected abstract draw(
    g: Graphics,
    frame: VisualizationFrame | null,
    dt: number,
    elapsed: number
  ): void;

  destroy(): void {
    this.container.destroy({ children: true });
  }
}
