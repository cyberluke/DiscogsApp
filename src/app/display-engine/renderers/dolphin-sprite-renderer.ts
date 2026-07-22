import { Assets, Container, Rectangle, Sprite, Texture } from 'pixi.js';
import { GlowFilter } from 'pixi-filters';
import { VisualizationFrame } from '../frame.model';
import { DisplayTheme } from '../theme';
import { IRenderer } from './renderer';

interface SpriteManifest {
  frameWidth: number;
  frameHeight: number;
  frameCount: number;
  cols: number;
  rows: number;
  fps: number;
  phosphor: { r: number; g: number; b: number };
}

/**
 * DolphinSpriteRenderer — the HERO of the display.
 *
 * Plays a 1-bit Floyd–Steinberg dithered sprite animation of a leaping
 * dolphin, generated from AI video (happyhorse-1.1-t2v) + dithering pipeline.
 *
 * The sprite sheet is a grid of white-on-transparent frames. At runtime the
 * sprite is tinted with the theme's phosphor color so it reads as a lit OEL
 * element — the post-processing bloom then produces the characteristic
 * phosphor halo.
 *
 * Animation plays at a calm, hypnotic pace (slower than the source 12 FPS)
 * per the Pioneer OEL Design Language: "hypnotic, very slow deformations,
 * no sudden changes."
 */
export class DolphinSpriteRenderer implements IRenderer {
  readonly container = new Container();

  /** Last-drawn dolphin bounding box in internal pixels (debug overlay). */
  bounds = { x: 0, y: 0, w: 0, h: 0 };

  private sprite: Sprite | null = null;
  private textures: Texture[] = [];
  private manifest: SpriteManifest | null = null;
  private width = 320;
  private height = 128;
  private theme!: DisplayTheme;
  private ready = false;
  private glow?: GlowFilter;

  /** Calm playback: slower than source 12 FPS for a hypnotic feel. */
  private static readonly PLAYBACK_FPS = 8;
  /** Dominant scale: fills ~55% of display height, unmistakable centerpiece. */
  private static readonly BASE_SCALE = 1.75;

  /** Ghost sprites that form the phosphor persistence (afterglow) trail. */
  private ghosts: Sprite[] = [];
  /** Number of ghost frames in the persistence trail. */
  private static readonly GHOST_COUNT = 3;
  /** Animation-frame lag between consecutive ghosts. */
  private static readonly GHOST_LAG = 3;
  /** Alpha decay for each ghost (newest → oldest). Kept low to avoid fog. */
  private static readonly GHOST_ALPHA = [0.10, 0.06, 0.03];

  private frameIndex = 0;
  private frameTimer = 0;

  onInit(width: number, height: number, theme: DisplayTheme): void {
    this.width = width;
    this.height = height;
    this.theme = theme;
    void this.load();
  }

  onTheme(theme: DisplayTheme): void {
    this.theme = theme;
    if (this.sprite) {
      this.sprite.tint = theme.sceneBright;
    }
    for (const ghost of this.ghosts) {
      ghost.tint = theme.sceneBright;
    }
    if (this.glow) {
      this.glow.color = theme.sceneBright;
    }
  }

  render(frame: VisualizationFrame | null, dt: number, elapsed: number): void {
    if (!this.ready || !this.sprite || this.textures.length === 0) {
      return;
    }

    const bass = frame?.bass ?? 0;

    // Advance animation frame at the calm playback rate.
    this.frameTimer += dt;
    const frameDuration = 1 / DolphinSpriteRenderer.PLAYBACK_FPS;
    while (this.frameTimer >= frameDuration) {
      this.frameTimer -= frameDuration;
      this.frameIndex = (this.frameIndex + 1) % this.textures.length;
    }
    this.sprite.texture = this.textures[this.frameIndex];

    // Dominant, centered positioning with subtle organic life.
    const scale = DolphinSpriteRenderer.BASE_SCALE * (1 + bass * 0.04);
    this.sprite.scale.set(scale);
    this.sprite.x = this.width * 0.5;
    // Slightly above center + gentle hypnotic vertical bob.
    this.sprite.y = this.height * 0.48 + Math.sin(elapsed * 0.7) * 2.5;

    // Phosphor persistence trail: each ghost shows an older animation frame
    // at a decaying alpha, offset backward along the leap direction so the
    // afterglow reads as a clean directional trail, not a vertical fog smear.
    const n = this.textures.length;
    for (let gi = 0; gi < this.ghosts.length; gi++) {
      const ghost = this.ghosts[gi];
      const lagIndex =
        (this.frameIndex - (gi + 1) * DolphinSpriteRenderer.GHOST_LAG + n) % n;
      ghost.texture = this.textures[lagIndex];
      ghost.scale.set(scale);
      // Offset backward (dolphin faces right → trail goes left) and slightly
      // down along the leap arc, growing with ghost age.
      const offset = (gi + 1) * 5;
      ghost.x = this.sprite.x - offset;
      ghost.y = this.sprite.y + offset * 0.4;
    }

    // Update bounds for the debug overlay.
    const w = this.manifest!.frameWidth * scale;
    const h = this.manifest!.frameHeight * scale;
    this.bounds = {
      x: Math.round(this.sprite.x - w / 2),
      y: Math.round(this.sprite.y - h / 2),
      w: Math.round(w),
      h: Math.round(h)
    };
  }

  destroy(): void {
    this.glow?.destroy();
    this.container.destroy({ children: true });
    this.textures = [];
    this.ghosts = [];
    this.sprite = null;
  }

  private async load(): Promise<void> {
    try {
      const resp = await fetch('assets/dolphin-dithered/manifest.json');
      this.manifest = (await resp.json()) as SpriteManifest;

      const sheet = await Assets.load<Texture>(
        'assets/dolphin-dithered/sprite-sheet.png'
      );

      const { frameWidth, frameHeight, cols, frameCount } = this.manifest;
      for (let i = 0; i < frameCount; i++) {
        const col = i % cols;
        const row = Math.floor(i / cols);
        this.textures.push(
          new Texture({
            source: sheet.source,
            frame: new Rectangle(
              col * frameWidth,
              row * frameHeight,
              frameWidth,
              frameHeight
            )
          })
        );
      }

      // Persistence ghosts first (drawn beneath the main sprite).
      for (let gi = 0; gi < DolphinSpriteRenderer.GHOST_COUNT; gi++) {
        const ghost = new Sprite(this.textures[0]);
        ghost.anchor.set(0.5, 0.5);
        ghost.tint = this.theme.sceneBright;
        ghost.alpha = DolphinSpriteRenderer.GHOST_ALPHA[gi];
        this.container.addChild(ghost);
        this.ghosts.push(ghost);
      }

      this.sprite = new Sprite(this.textures[0]);
      this.sprite.anchor.set(0.5, 0.5);
      this.sprite.tint = this.theme.sceneBright;
      this.container.addChild(this.sprite);

      // Dedicated phosphor glow halo — sells the "lit OEL object" look.
      // A soft outer aura plus a faint inner fill keeps the dithered body
      // readable as a glowing form without blowing out to a white hotspot.
      this.glow = new GlowFilter({
        distance: 4,
        outerStrength: 0.5,
        innerStrength: 0.1,
        color: this.theme.sceneBright,
        quality: 0.2
      });
      this.container.filters = [this.glow];

      this.ready = true;
    } catch (err) {
      console.error('[DolphinSpriteRenderer] Failed to load sprite sheet:', err);
    }
  }
}
