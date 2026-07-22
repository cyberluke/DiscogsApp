import { Container } from 'pixi.js';
import { DisplayTheme } from '../theme';
import { VisualizationFrame } from '../frame.model';
import { ILayer, LayerContext } from './layer';

/**
 * Convenience base class implementing the common {@link ILayer} plumbing:
 * a dedicated container, enabled flag, and theme reference. Concrete layers
 * override `onUpdate` and `onTheme`.
 */
export abstract class BaseLayer implements ILayer {
  abstract readonly id: string;
  abstract readonly order: number;

  protected readonly container = new Container();
  protected context!: LayerContext;
  protected theme!: DisplayTheme;
  protected enabled = true;

  init(context: LayerContext): void {
    this.context = context;
    this.theme = context.theme;
    context.root.addChild(this.container);
    this.container.visible = this.enabled;
    this.onInit(context);
    this.onTheme(this.theme);
  }

  update(frame: VisualizationFrame, dt: number): void {
    if (!this.enabled) {
      return;
    }
    this.onUpdate(frame, dt);
  }

  applyTheme(theme: DisplayTheme): void {
    this.theme = theme;
    this.onTheme(theme);
  }

  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    this.container.visible = enabled;
  }

  destroy(): void {
    this.onDestroy();
    this.container.destroy({ children: true });
  }

  protected onInit(_context: LayerContext): void {
    /* optional override */
  }

  protected abstract onUpdate(frame: VisualizationFrame, dt: number): void;

  protected onTheme(_theme: DisplayTheme): void {
    /* optional override */
  }

  protected onDestroy(): void {
    /* optional override */
  }
}
