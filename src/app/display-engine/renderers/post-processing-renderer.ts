import { Container } from 'pixi.js';
import { CRTFilter, GlowFilter } from 'pixi-filters';
import { DisplayTheme } from '../theme';

/**
 * PostProcessingRenderer — the final "glass" of the OEL unit.
 *
 * Two effects:
 *
 *   1. Scene glow — a subtle phosphor halo applied to the WHOLE scene so every
 *      element (dolphin, waves, FFT, text) reads as a lit OEL object. Kept
 *      tight (distance 3) and weak (outerStrength 0.25) so edges stay crisp.
 *
 *   2. Trail bloom — a stronger glow applied ONLY to the phosphor trail
 *      (the `glowWrap` container from the PersistencePass). This is the soft
 *      light that bleeds *behind* moving objects.
 *
 *   3. CRT character — vignette + film noise only. NO scanlines (they create
 *      horizontal striping artifacts on a 128px display).
 */
export class PostProcessingRenderer {
  /** Resting bloom strength for the trail — deliberately low. */
  static readonly RESTING_BLOOM = 0.45;
  /** Scene glow strength — subtle phosphor halo on everything. */
  static readonly SCENE_GLOW = 0.25;

  private readonly trailBloom: GlowFilter;
  private readonly sceneGlow: GlowFilter;
  private readonly crt: CRTFilter;

  /**
   * @param scene    the whole scene container (receives scene glow + CRT)
   * @param glowWrap the trail-only container (receives the trail bloom)
   */
  constructor(scene: Container, glowWrap: Container, theme: DisplayTheme) {
    // Trail bloom — stronger, behind moving objects.
    this.trailBloom = new GlowFilter({
      distance: 5,
      outerStrength: PostProcessingRenderer.RESTING_BLOOM,
      innerStrength: 0.12,
      color: theme.primary,
      quality: 0.2
    });

    // Scene glow — subtle phosphor halo on everything (the OEL "lit" look).
    this.sceneGlow = new GlowFilter({
      distance: 3,
      outerStrength: PostProcessingRenderer.SCENE_GLOW,
      innerStrength: 0.08,
      color: theme.primary,
      quality: 0.15
    });

    // CRT — vignette + noise only. NO scanlines (they stripe the dolphin).
    this.crt = new CRTFilter({
      vignetting: 0.14,
      vignettingAlpha: 0.55,
      noise: 0.04,
      lineWidth: 0,
      lineContrast: 0,
      verticalLine: false
    });

    glowWrap.filters = [this.trailBloom];
    scene.filters = [this.sceneGlow, this.crt];
    this.applyTheme(theme);
  }

  /** Current bloom strength (read by the debug overlay). */
  get bloomStrength(): number {
    return this.trailBloom.outerStrength;
  }

  applyTheme(theme: DisplayTheme): void {
    this.trailBloom.color = theme.primary;
    this.trailBloom.outerStrength = PostProcessingRenderer.RESTING_BLOOM * theme.glowStrength;
    this.sceneGlow.color = theme.primary;
    this.sceneGlow.outerStrength = PostProcessingRenderer.SCENE_GLOW * theme.glowStrength;
    this.crt.vignetting = theme.vignette;
  }

  /** Momentarily boost the bloom on a beat (additive "pump"). */
  pulse(amount: number): void {
    this.trailBloom.outerStrength = Math.min(1.0, PostProcessingRenderer.RESTING_BLOOM + amount * 0.4);
    this.sceneGlow.outerStrength = Math.min(0.6, PostProcessingRenderer.SCENE_GLOW + amount * 0.15);
  }

  /** Relax the bloom back to its resting value. */
  relax(dt: number, theme: DisplayTheme): void {
    const resting = PostProcessingRenderer.RESTING_BLOOM * theme.glowStrength;
    this.trailBloom.outerStrength += (resting - this.trailBloom.outerStrength) * Math.min(1, dt * 4);
    const sceneResting = PostProcessingRenderer.SCENE_GLOW * theme.glowStrength;
    this.sceneGlow.outerStrength += (sceneResting - this.sceneGlow.outerStrength) * Math.min(1, dt * 4);
  }

  destroy(): void {
    this.trailBloom.destroy();
    this.sceneGlow.destroy();
    this.crt.destroy();
  }
}
