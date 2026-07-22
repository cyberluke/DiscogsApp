import { Graphics } from 'pixi.js';

/**
 * A scalable 3×5 pixel bitmap font in the style of a hardware OEL character
 * display. Every glyph is a 5-row × 3-column bitmap ('#' = lit pixel). The
 * renderer draws each lit pixel as a filled square at an integer scale, so the
 * type always reads as firmware — never as a browser font.
 *
 * This is the only type system the display uses.
 */

export const GLYPH_WIDTH = 3;
export const GLYPH_HEIGHT = 5;
/** Inter-character spacing in font pixels. */
export const GLYPH_GAP = 1;

const GLYPHS: Record<string, string[]> = {
  '0': ['.#.', '#.#', '#.#', '#.#', '.#.'],
  '1': ['.#.', '##.', '.#.', '.#.', '###'],
  '2': ['##.', '..#', '.#.', '#..', '###'],
  '3': ['##.', '..#', '.#.', '..#', '##.'],
  '4': ['#.#', '#.#', '###', '..#', '..#'],
  '5': ['###', '#..', '##.', '..#', '##.'],
  '6': ['.##', '#..', '##.', '#.#', '.#.'],
  '7': ['###', '..#', '..#', '..#', '..#'],
  '8': ['.#.', '#.#', '.#.', '#.#', '.#.'],
  '9': ['.#.', '#.#', '.##', '..#', '.#.'],

  A: ['.#.', '#.#', '###', '#.#', '#.#'],
  B: ['##.', '#.#', '##.', '#.#', '##.'],
  C: ['.##', '#..', '#..', '#..', '.##'],
  D: ['##.', '#.#', '#.#', '#.#', '##.'],
  E: ['###', '#..', '##.', '#..', '###'],
  F: ['###', '#..', '##.', '#..', '#..'],
  G: ['.##', '#..', '#.#', '#.#', '.##'],
  H: ['#.#', '#.#', '###', '#.#', '#.#'],
  I: ['###', '.#.', '.#.', '.#.', '###'],
  J: ['..#', '..#', '..#', '#.#', '.#.'],
  K: ['#.#', '#.#', '##.', '#.#', '#.#'],
  L: ['#..', '#..', '#..', '#..', '###'],
  M: ['#.#', '###', '#.#', '#.#', '#.#'],
  N: ['##.', '#.#', '#.#', '#.#', '#.#'],
  O: ['.#.', '#.#', '#.#', '#.#', '.#.'],
  P: ['##.', '#.#', '##.', '#..', '#..'],
  Q: ['.#.', '#.#', '#.#', '#.#', '.#.'],
  R: ['##.', '#.#', '##.', '#.#', '#.#'],
  S: ['.##', '#..', '.#.', '..#', '##.'],
  T: ['###', '.#.', '.#.', '.#.', '.#.'],
  U: ['#.#', '#.#', '#.#', '#.#', '.#.'],
  V: ['#.#', '#.#', '#.#', '#.#', '.#.'],
  W: ['#.#', '#.#', '#.#', '###', '.#.'],
  X: ['#.#', '#.#', '.#.', '#.#', '#.#'],
  Y: ['#.#', '#.#', '.#.', '.#.', '.#.'],
  Z: ['###', '..#', '.#.', '#..', '###'],

  ' ': ['...', '...', '...', '...', '...'],
  '-': ['...', '...', '###', '...', '...'],
  _: ['...', '...', '...', '...', '###'],
  '.': ['...', '...', '...', '...', '.#.'],
  ',': ['...', '...', '...', '.#.', '#..'],
  ':': ['...', '.#.', '...', '.#.', '...'],
  '/': ['..#', '..#', '.#.', '#..', '#..'],
  '%': ['#.#', '..#', '.#.', '#..', '#.#'],
  '(': ['.#.', '#..', '#..', '#..', '.#.'],
  ')': ['#..', '.#.', '.#.', '.#.', '#..'],
  '&': ['.#.', '#.#', '.#.', '#.#', '.#.'],
  "'": ['.#.', '.#.', '...', '...', '...'],
  '!': ['.#.', '.#.', '.#.', '...', '.#.'],
  '+': ['...', '.#.', '###', '.#.', '...'],
  '=': ['...', '###', '...', '###', '...'],
  '<': ['..#', '.#.', '#..', '.#.', '..#'],
  '>': ['#..', '.#.', '..#', '.#.', '#..'],
  '#': ['#.#', '###', '#.#', '###', '#.#'],
  '·': ['...', '...', '.#.', '...', '...'],
  '•': ['...', '.#.', '###', '.#.', '...']
};

/** Fallback glyph for characters without a bitmap (renders as a block). */
const MISSING: string[] = ['###', '###', '###', '###', '###'];

/** Resolve a character to its bitmap, normalising case. */
function glyphFor(ch: string): string[] {
  return GLYPHS[ch] ?? GLYPHS[ch.toUpperCase()] ?? MISSING;
}

/** Width in display pixels of a single character at scale `px`. */
export function charWidth(px: number): number {
  return (GLYPH_WIDTH + GLYPH_GAP) * px;
}

/** Total width in display pixels of a string at scale `px`. */
export function textWidth(text: string, px: number): number {
  if (!text.length) {
    return 0;
  }
  return text.length * charWidth(px) - GLYPH_GAP * px;
}

/**
 * Draw a single character. Returns the advance (in display pixels) to the next
 * character origin.
 */
export function drawChar(
  g: Graphics,
  ch: string,
  x: number,
  y: number,
  px: number,
  color: number,
  alpha: number
): number {
  const glyph = glyphFor(ch);
  for (let row = 0; row < GLYPH_HEIGHT; row++) {
    const line = glyph[row];
    for (let col = 0; col < GLYPH_WIDTH; col++) {
      if (line[col] === '#') {
        g.rect(x + col * px, y + row * px, px, px).fill({ color, alpha });
      }
    }
  }
  return charWidth(px);
}

/**
 * Draw a string of bitmap text. `px` is the integer pixel scale (1 = 3×5,
 * 2 = 6×10, …). Returns the total advance width.
 */
export function drawText(
  g: Graphics,
  text: string,
  x: number,
  y: number,
  px: number,
  color: number,
  alpha = 1
): number {
  let cursor = x;
  for (const ch of text) {
    cursor += drawChar(g, ch, cursor, y, px, color, alpha);
  }
  return cursor - x;
}
