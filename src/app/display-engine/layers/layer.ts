import { Container } from 'pixi.js';
import { DisplayTheme } from '../theme';
import { VisualizationFrame } from '../frame.model';

/**
 * Fixed internal render resolution of the display. This is a *virtual hardware
 * display* — everything is positioned in these fixed coordinates, exactly like
 * firmware. The component integer-scales this canvas to fit its container with
 * nearest-neighbour filtering to preserve the crisp, pixelated character of a
 * late-1990s Organic EL head unit.
 */
export const DISPLAY_WIDTH = 320;
export const DISPLAY_HEIGHT = 128;

/**
 * Shared context handed to every layer. Layers render into `root` (or a child
 * container they create) and read the current interpolated frame each tick.
 */
export interface LayerContext {
  /** Root container for the whole scene. */
  readonly root: Container;
  /** Current theme. May change at runtime via `applyTheme`. */
  theme: DisplayTheme;
  /** Logical display width in internal pixels. */
  readonly width: number;
  /** Logical display height in internal pixels. */
  readonly height: number;
}

/**
 * A single visual element of the display. Layers are updated every frame with
 * the latest interpolated {@link VisualizationFrame} plus a delta time.
 *
 * Lifecycle: `init` → many `update` calls → `destroy`.
 */
export interface ILayer {
  /** Stable identifier used for ordering and toggling. */
  readonly id: string;
  /** Relative render order; lower draws first (behind). */
  readonly order: number;

  /** Build the layer's display objects and attach them to the context. */
  init(context: LayerContext): void;
  /** Advance the layer by `dt` seconds using the current frame. */
  update(frame: VisualizationFrame, dt: number): void;
  /** Re-apply colors after a theme change. */
  applyTheme(theme: DisplayTheme): void;
  /** Enable/disable rendering without destroying the layer. */
  setEnabled(enabled: boolean): void;
  /** Release GPU resources. */
  destroy(): void;
}
