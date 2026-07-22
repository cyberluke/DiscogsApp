/**
 * Theme engine for the Pioneer Heritage Display Engine.
 *
 * Every theme is a *monochrome phosphor* palette: all lit colors derive from a
 * single phosphor hue, exactly like a real Organic EL panel. There is no RGB
 * rainbow — only one color at several brightnesses, with glow produced by
 * post-processing bloom rather than gradients.
 *
 * Colors are 24-bit RGB integers (PixiJS convention).
 */

export interface DisplayTheme {
  readonly id: string;
  readonly name: string;

  /** The single phosphor color everything derives from. */
  readonly phosphor: number;

  /** Deep background fill behind everything. */
  readonly background: number;
  /** Secondary background gradient stop (subtle vertical falloff). */
  readonly backgroundDeep: number;

  /** Primary phosphor color for spectrum bars and headline text. */
  readonly primary: number;
  /** Brighter highlight used for peaks and beat flashes. */
  readonly highlight: number;
  /** Dim color for idle/low-energy segments. */
  readonly dim: number;

  /** VU meter gradient: low → mid → high energy. */
  readonly vuLow: number;
  readonly vuMid: number;
  readonly vuHigh: number;

  /** Track-info marquee text color. */
  readonly textColor: number;
  /** AI overlay accent color (the "impossible on hardware" data). */
  readonly accent: number;

  /** Hardware indicator colors (ST stereo, AF, TP). */
  readonly indicatorOn: number;
  readonly indicatorOff: number;

  /** Animated-theme scene colors (derived from the phosphor). */
  readonly sceneBright: number;
  readonly sceneMid: number;
  readonly sceneDim: number;

  /**
   * Layered-phosphor colors. A real OEL element is not a single flat color:
   * it has a near-white hot core, a saturated mid glow and a deep afterglow.
   * Renderers stack these to build the characteristic "lit" look.
   */
  readonly core: number;
  readonly afterglow: number;

  /** Dot-matrix type sizes (internal pixels). */
  readonly fontLarge: number;
  readonly fontMedium: number;
  readonly fontSmall: number;

  /** Glow/bloom intensity multiplier applied by the filter pipeline. */
  readonly glowStrength: number;
  /** CRT scanline / aperture-grille opacity (0 disables the CRT layer). */
  readonly scanlineOpacity: number;
  /** Vignette strength (darkening toward the panel edges). */
  readonly vignette: number;
}

/** Brighten a 24-bit color toward white by `t` (0..1). */
function lighten(color: number, t: number): number {
  const r = (color >> 16) & 0xff;
  const g = (color >> 8) & 0xff;
  const b = color & 0xff;
  const lr = Math.round(r + (255 - r) * t);
  const lg = Math.round(g + (255 - g) * t);
  const lb = Math.round(b + (255 - b) * t);
  return (lr << 16) | (lg << 8) | lb;
}

/** Darken a 24-bit color toward black by `t` (0..1). */
function darken(color: number, t: number): number {
  const r = (color >> 16) & 0xff;
  const g = (color >> 8) & 0xff;
  const b = color & 0xff;
  return (
    (Math.round(r * (1 - t)) << 16) |
    (Math.round(g * (1 - t)) << 8) |
    Math.round(b * (1 - t))
  );
}

/** Build a full monochrome palette from a single phosphor color. */
function monochrome(id: string, name: string, phosphor: number): DisplayTheme {
  return {
    id,
    name,
    phosphor,

    background: darken(phosphor, 0.94),
    backgroundDeep: darken(phosphor, 0.97),

    primary: phosphor,
    highlight: lighten(phosphor, 0.55),
    dim: darken(phosphor, 0.62),

    vuLow: darken(phosphor, 0.35),
    vuMid: phosphor,
    vuHigh: lighten(phosphor, 0.6),

    textColor: lighten(phosphor, 0.35),
    accent: lighten(phosphor, 0.7),

    indicatorOn: lighten(phosphor, 0.45),
    indicatorOff: darken(phosphor, 0.7),

    sceneBright: lighten(phosphor, 0.5),
    sceneMid: phosphor,
    sceneDim: darken(phosphor, 0.55),

    // Layered-phosphor colors: near-white hot core, deep afterglow tail.
    core: lighten(phosphor, 0.85),
    afterglow: darken(phosphor, 0.4),

    fontLarge: 2,
    fontMedium: 1,
    fontSmall: 1,

    glowStrength: 1.0,
    scanlineOpacity: 0.16,
    vignette: 0.35
  };
}

export const CLASSIC_BLUE_THEME = monochrome('classic-blue', 'Classic Blue', 0x2fd4ff);
export const CLASSIC_GREEN_THEME = monochrome('classic-green', 'Classic Green', 0x35ff8f);
export const AMBER_THEME = monochrome('amber', 'Amber', 0xffb347);
export const WHITE_THEME = monochrome('white', 'White', 0xdfe9f5);

/** Registry of available themes, keyed by id. */
export const THEMES: Record<string, DisplayTheme> = {
  [CLASSIC_BLUE_THEME.id]: CLASSIC_BLUE_THEME,
  [CLASSIC_GREEN_THEME.id]: CLASSIC_GREEN_THEME,
  [AMBER_THEME.id]: AMBER_THEME,
  [WHITE_THEME.id]: WHITE_THEME
};

export const DEFAULT_THEME_ID = CLASSIC_BLUE_THEME.id;

export function resolveTheme(id: string | null | undefined): DisplayTheme {
  return (id && THEMES[id]) || THEMES[DEFAULT_THEME_ID];
}
