import { Graphics } from 'pixi.js';

/**
 * dolphin-sprite.ts — an authentic 1-bit dithered dolphin sprite.
 *
 * The late-1990s Pioneer OEL dolphin was NOT a flat vector fill. It was a
 * monochrome sprite whose volume came from a vertical shade stack rendered as
 * spatial dither on a binary (on/off) phosphor panel:
 *
 *     1. a 1–2 px near-white specular rim along the back,
 *     2. a high-density (~80%) light field on the upper flank,
 *     3. an irregular error-diffusion mid-tone (~45%) on the lower flank,
 *     4. a solid-black ventral crescent (counter-shading), and
 *     5. a thin bright ventral highlight line.
 *
 * This module rasterises that exact construction procedurally from a landmark
 * table (extracted from a reference panel photo) so the sprite is crisp at the
 * display's native 320×128 resolution and reads as a lit phosphor creature
 * rather than a CAD polygon.
 *
 * The sprite is generated ONCE per theme (it is static — motion is applied by
 * transforming the container), so per-frame cost is a single drawImage.
 */

/** A single point in the sprite's local pixel space. */
interface Pt {
  x: number;
  y: number;
}

/** The dolphin's anatomical landmarks in local sprite pixels. */
export interface DolphinLandmarks {
  /** Tail peduncle (where the body meets the fluke). */
  peduncle: Pt;
  /** Apex of the back / base of the dorsal fin. */
  backApex: Pt;
  /** Top of the melon (forehead). */
  melonTop: Pt;
  /** Tip of the rostrum (beak). */
  rostrumTip: Pt;
  /** Mouth notch (separates melon from beak). */
  mouthNotch: Pt;
  /** Lowest point of the belly. */
  bellyLow: Pt;
  /** Rear-lower point where the belly tapers to the peduncle. */
  bellyRear: Pt;
  /** Dorsal fin apex + trailing base. */
  dorsalApex: Pt;
  dorsalTrail: Pt;
  /** Upper tail-fluke lobe tip. */
  flukeUp: Pt;
  /** Lower tail-fluke lobe tip. */
  flukeLow: Pt;
  /** Pectoral fin: front corner, rear tip, lower point. */
  pecFront: Pt;
  pecRear: Pt;
  pecLow: Pt;
  /** Eye position. */
  eye: Pt;
}

/** Default landmarks sized for a ~118×76 px sprite (nose points +X). */
export const DEFAULT_LANDMARKS: DolphinLandmarks = {
  peduncle: { x: 20, y: 40 },
  backApex: { x: 54, y: 5 },
  melonTop: { x: 98, y: 21 },
  rostrumTip: { x: 116, y: 54 },
  mouthNotch: { x: 96, y: 45 },
  bellyLow: { x: 60, y: 41 },
  bellyRear: { x: 30, y: 42 },
  dorsalApex: { x: 56, y: 0 },
  dorsalTrail: { x: 68, y: 8 },
  flukeUp: { x: 2, y: 56 },
  flukeLow: { x: 14, y: 66 },
  pecFront: { x: 58, y: 36 },
  pecRear: { x: 78, y: 43 },
  pecLow: { x: 66, y: 48 },
  eye: { x: 94, y: 39 }
};

export interface DolphinSpriteOptions {
  /** Near-white specular rim color. */
  core: number;
  /** Bright phosphor color (rim / highlights). */
  sceneBright: number;
  /** Mid phosphor color (upper-flank fill). */
  sceneMid: number;
  /** Deep background color (belly crescent + eye). */
  backgroundDeep: number;
  landmarks?: DolphinLandmarks;
}

/** Bounding box of the generated sprite in local pixels. */
export interface SpriteBounds {
  width: number;
  height: number;
}

/** Evaluate a cubic bezier at parameter t. */
function cubic(
  p0: Pt,
  c1: Pt,
  c2: Pt,
  p3: Pt,
  t: number
): Pt {
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const c = 3 * u * t * t;
  const d = t * t * t;
  return {
    x: a * p0.x + b * c1.x + c * c2.x + d * p3.x,
    y: a * p0.y + b * c1.y + c * c2.y + d * p3.y
  };
}

/** Sample a cubic bezier into a dense polyline. */
function sampleBezier(p0: Pt, c1: Pt, c2: Pt, p3: Pt, steps = 48): Pt[] {
  const out: Pt[] = [];
  for (let i = 0; i <= steps; i++) {
    out.push(cubic(p0, c1, c2, p3, i / steps));
  }
  return out;
}

/**
 * The dithered dolphin sprite.
 *
 * Owns an offscreen canvas holding the pre-rendered sprite plus the landmark
 * data needed to position it in the scene.
 */
export class DolphinSprite {
  readonly canvas: HTMLCanvasElement;
  readonly bounds: SpriteBounds;
  private readonly lm: DolphinLandmarks;

  constructor(opts: DolphinSpriteOptions) {
    this.lm = opts.landmarks ?? DEFAULT_LANDMARKS;

    // Generous canvas so fins/flukes never clip.
    const W = 124;
    const H = 80;
    const canvas = document.createElement('canvas');
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext('2d');
    if (!ctx) {
      throw new Error('DolphinSprite: 2d context unavailable');
    }

    this.render(ctx, opts);
    this.canvas = canvas;
    this.bounds = { width: W, height: H };
  }

  /** Sprite-local point of the body's visual center (for scene placement). */
  get center(): Pt {
    return { x: 58, y: 30 };
  }

  /** Sprite-local point of the rostrum tip (for splash placement). */
  get nose(): Pt {
    return this.lm.rostrumTip;
  }

  private render(ctx: CanvasRenderingContext2D, opts: DolphinSpriteOptions): void {
    const lm = this.lm;

    // ---- Contour curves ----------------------------------------------------
    // Dorsal: peduncle → back apex → melon → rostrum tip (convex-up arch).
    const dorsal = [
      ...sampleBezier(
        lm.peduncle,
        { x: 30, y: 14 },
        { x: 42, y: 4 },
        lm.backApex
      ),
      ...sampleBezier(
        lm.backApex,
        { x: 70, y: 6 },
        { x: 88, y: 12 },
        lm.melonTop
      ),
      ...sampleBezier(
        lm.melonTop,
        { x: 108, y: 28 },
        { x: 112, y: 40 },
        lm.rostrumTip
      )
    ];

    // Ventral: rostrum tip → belly low → belly rear → peduncle (shallower arch).
    const ventral = [
      ...sampleBezier(
        lm.rostrumTip,
        { x: 100, y: 58 },
        { x: 84, y: 48 },
        lm.bellyLow
      ),
      ...sampleBezier(
        lm.bellyLow,
        { x: 44, y: 44 },
        { x: 34, y: 44 },
        lm.bellyRear
      ),
      ...sampleBezier(
        lm.bellyRear,
        { x: 26, y: 42 },
        { x: 22, y: 41 },
        lm.peduncle
      )
    ];

    // ---- Body silhouette (closed path) -------------------------------------
    const bodyPath = new Path2D();
    bodyPath.moveTo(dorsal[0].x, dorsal[0].y);
    for (const p of dorsal) bodyPath.lineTo(p.x, p.y);
    for (const p of ventral) bodyPath.lineTo(p.x, p.y);
    bodyPath.closePath();

    // Fill the body with the 3-band volumetric dither stack.
    this.fillDithered(ctx, bodyPath, dorsal, opts);

    // ---- Black belly crescent (counter-shading) ----------------------------
    const bellyPath = new Path2D();
    bellyPath.moveTo(lm.rostrumTip.x, lm.rostrumTip.y);
    for (const p of ventral) bellyPath.lineTo(p.x, p.y);
    // Close back along a shallow "shadow line" just below the mid-body.
    bellyPath.bezierCurveTo(40, 34, 78, 36, lm.rostrumTip.x, lm.rostrumTip.y);
    bellyPath.closePath();
    ctx.fillStyle = toCss(opts.backgroundDeep);
    ctx.fill(bellyPath);

    // ---- Ventral highlight line (thin bright stroke along the belly) -------
    ctx.strokeStyle = toCss(opts.sceneBright);
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.85;
    ctx.beginPath();
    ctx.moveTo(lm.bellyRear.x, lm.bellyRear.y);
    ctx.bezierCurveTo(44, 43, 78, 46, lm.rostrumTip.x - 2, lm.rostrumTip.y - 1);
    ctx.stroke();
    ctx.globalAlpha = 1;

    // ---- Dorsal fin (bright leading edge + dithered fill) ------------------
    const finPath = new Path2D();
    finPath.moveTo(50, 8);
    finPath.bezierCurveTo(52, 3, 54, 1, lm.dorsalApex.x, lm.dorsalApex.y);
    finPath.bezierCurveTo(60, 2, 64, 5, lm.dorsalTrail.x, lm.dorsalTrail.y);
    finPath.bezierCurveTo(62, 8, 56, 9, 50, 8);
    finPath.closePath();
    ctx.fillStyle = toCss(opts.sceneMid);
    ctx.fill(finPath);
    ctx.strokeStyle = toCss(opts.sceneBright);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(50, 8);
    ctx.bezierCurveTo(52, 3, 54, 1, lm.dorsalApex.x, lm.dorsalApex.y);
    ctx.stroke();

    // ---- Tail fluke: two rim-only arcs (interior stays black) --------------
    ctx.strokeStyle = toCss(opts.sceneBright);
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.9;
    // Upper lobe.
    ctx.beginPath();
    ctx.moveTo(lm.peduncle.x, lm.peduncle.y - 2);
    ctx.bezierCurveTo(12, 46, 5, 50, lm.flukeUp.x, lm.flukeUp.y);
    ctx.stroke();
    // Lower lobe (slightly fainter, broken).
    ctx.globalAlpha = 0.6;
    ctx.beginPath();
    ctx.moveTo(lm.peduncle.x, lm.peduncle.y + 2);
    ctx.bezierCurveTo(12, 56, 12, 62, lm.flukeLow.x, lm.flukeLow.y);
    ctx.stroke();
    ctx.globalAlpha = 1;

    // ---- Pectoral fin: the brightest solid mass ----------------------------
    const pecPath = new Path2D();
    pecPath.moveTo(lm.pecFront.x, lm.pecFront.y);
    pecPath.bezierCurveTo(64, 40, 74, 42, lm.pecRear.x, lm.pecRear.y);
    pecPath.bezierCurveTo(74, 46, 70, 48, lm.pecLow.x, lm.pecLow.y);
    pecPath.bezierCurveTo(62, 44, 59, 40, lm.pecFront.x, lm.pecFront.y);
    pecPath.closePath();
    ctx.fillStyle = toCss(opts.core);
    ctx.fill(pecPath);

    // ---- Specular rim along the dorsal contour (the "wet" highlight) -------
    ctx.strokeStyle = toCss(opts.core);
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    ctx.moveTo(dorsal[0].x, dorsal[0].y);
    for (const p of dorsal) ctx.lineTo(p.x, p.y);
    ctx.stroke();

    // ---- Eye: a single dark pixel ------------------------------------------
    ctx.fillStyle = toCss(opts.backgroundDeep);
    ctx.fillRect(Math.round(lm.eye.x), Math.round(lm.eye.y), 2, 2);

    // ---- Mouth groove: dark line separating melon from beak ----------------
    ctx.strokeStyle = toCss(opts.backgroundDeep);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(lm.mouthNotch.x, lm.mouthNotch.y);
    ctx.lineTo(lm.rostrumTip.x - 1, lm.rostrumTip.y - 1);
    ctx.stroke();
  }

  /**
   * Fill the body with the volumetric dither stack. For each pixel inside the
   * silhouette we compute a shade level from its vertical position between the
   * dorsal rim and the belly, then decide on/off with an error-diffusion-style
   * irregular pattern (no visible grid, no banding).
   */
  private fillDithered(
    ctx: CanvasRenderingContext2D,
    bodyPath: Path2D,
    dorsal: Pt[],
    opts: DolphinSpriteOptions
  ): void {
    const { width: W, height: H } = this.bounds;

    // Build an ImageData buffer and decide each pixel individually.
    const img = ctx.createImageData(W, H);
    const data = img.data;

    // Pre-compute the dorsal Y at each column (top envelope) for shade mapping.
    const dorsalY = new Float32Array(W).fill(Infinity);
    for (const p of dorsal) {
      const xi = Math.round(p.x);
      if (xi >= 0 && xi < W) dorsalY[xi] = Math.min(dorsalY[xi], p.y);
    }
    // Fill gaps with nearest-neighbour so every column has a value.
    let last = 20;
    for (let x = 0; x < W; x++) {
      if (dorsalY[x] === Infinity) dorsalY[x] = last;
      else last = dorsalY[x];
    }

    const core = rgb(opts.core);
    const bright = rgb(opts.sceneBright);
    const mid = rgb(opts.sceneMid);

    for (let y = 0; y < H; y++) {
      for (let x = 0; x < W; x++) {
        if (!ctx.isPointInPath(bodyPath, x + 0.5, y + 0.5)) continue;

        // Vertical position relative to the dorsal envelope (0 = at rim).
        const depth = y - dorsalY[x];

        // Shade level 0..1 (0 = bright rim, 1 = dark belly).
        const shade = Math.min(1, Math.max(0, depth / 34));

        // Irregular error-diffusion-style threshold (no grid artifacts).
        const n = noise(x, y);
        const on = n < 1 - shade * 0.9;

        if (!on) continue;

        // Choose the color for this lit pixel by depth.
        let c: [number, number, number];
        if (depth <= 2) c = core; // specular rim
        else if (shade < 0.45) c = bright; // upper flank
        else c = mid; // lower flank (dithered)

        const i = (y * W + x) * 4;
        data[i] = c[0];
        data[i + 1] = c[1];
        data[i + 2] = c[2];
        data[i + 3] = 255;
      }
    }

    ctx.putImageData(img, 0, 0);
  }
}

/**
 * A cheap, grid-free pseudo-random field in [0,1). Combines two incommensurate
 * sine lattices so the dither looks like irregular error-diffusion rather than
 * a regular Bayer matrix (which would show visible cross-hatch banding).
 */
function noise(x: number, y: number): number {
  const a = Math.sin(x * 12.9898 + y * 78.233) * 43758.5453;
  const b = Math.sin(x * 4.898 + y * 7.23 + 1.7) * 23421.631;
  const v = (a - Math.floor(a)) * 0.62 + (b - Math.floor(b)) * 0.38;
  return v - Math.floor(v);
}

/** Convert a 24-bit color to an rgb() CSS string. */
function toCss(color: number): string {
  const [r, g, b] = rgb(color);
  return `rgb(${r},${g},${b})`;
}

/** Split a 24-bit color into [r, g, b]. */
function rgb(color: number): [number, number, number] {
  return [(color >> 16) & 0xff, (color >> 8) & 0xff, color & 0xff];
}
