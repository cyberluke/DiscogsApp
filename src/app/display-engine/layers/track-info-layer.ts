import { Graphics } from 'pixi.js';
import { DisplayTheme } from '../theme';
import { VisualizationFrame } from '../frame.model';
import { BaseLayer } from './base-layer';
import { LayerContext } from './layer';
import { drawText, textWidth } from '../bitmap-font';

/** Scroll speed in internal pixels per second. */
const SCROLL_SPEED = 30;
/** Pause (seconds) at the start position before scrolling begins. */
const LEAD_IN_PAUSE = 0.8;
/** Font pixel-scale for both lines (1 = 3×5 bitmap glyphs). */
const FONT_PX = 1;

interface MarqueeLine {
  text: string;
  y: number;
  scrollX: number;
  pauseTimer: number;
  needsScroll: boolean;
  width: number;
}

/**
 * Track information across the top of the display, rendered in the bitmap
 * font like a hardware character readout. The artist sits on the first line,
 * the title on the second. Each line scrolls only when it is wider than the
 * available area; otherwise it sits left-aligned. The whole block occupies the
 * top ~15–20% of the display.
 */
export class TrackInfoLayer extends BaseLayer {
  readonly id = 'track-info';
  readonly order = 50;

  private readonly gfx = new Graphics();
  private readonly maskGfx = new Graphics();

  private artist: MarqueeLine = this.makeLine(4);
  private title: MarqueeLine = this.makeLine(12);

  private areaWidth = 0;
  private marginX = 0;

  private makeLine(y: number): MarqueeLine {
    return { text: '', y, scrollX: 0, pauseTimer: LEAD_IN_PAUSE, needsScroll: false, width: 0 };
  }

  protected override onInit(context: LayerContext): void {
    this.marginX = 10;
    this.areaWidth = context.width - this.marginX * 2;

    this.container.addChild(this.gfx);

    // Clip scrolling text to the track-info band so it never bleeds out.
    this.maskGfx
      .rect(this.marginX, 0, this.areaWidth, 22)
      .fill({ color: 0xffffff });
    this.container.addChild(this.maskGfx);
    this.container.mask = this.maskGfx;
  }

  protected onUpdate(frame: VisualizationFrame, dt: number): void {
    this.setLineText(this.artist, this.buildArtist(frame));
    this.setLineText(this.title, this.buildTitle(frame));

    this.advance(this.artist, dt);
    this.advance(this.title, dt);

    this.draw();
  }

  private setLineText(line: MarqueeLine, text: string): void {
    if (text !== line.text) {
      line.text = text;
      line.width = textWidth(text, FONT_PX);
      line.needsScroll = line.width > this.areaWidth;
      line.scrollX = 0;
      line.pauseTimer = LEAD_IN_PAUSE;
    }
  }

  private advance(line: MarqueeLine, dt: number): void {
    if (!line.needsScroll) {
      line.scrollX = 0;
      return;
    }
    if (line.pauseTimer > 0) {
      line.pauseTimer -= dt;
      return;
    }
    line.scrollX += SCROLL_SPEED * dt;
    const overflow = line.width - this.areaWidth;
    if (line.scrollX > overflow + 24) {
      line.scrollX = 0;
      line.pauseTimer = LEAD_IN_PAUSE;
    }
  }

  private draw(): void {
    const g = this.gfx;
    g.clear();
    drawText(g, this.artist.text, this.marginX - this.artist.scrollX, this.artist.y, FONT_PX, this.theme.textColor);
    drawText(g, this.title.text, this.marginX - this.title.scrollX, this.title.y, FONT_PX, this.theme.primary);
  }

  private buildArtist(frame: VisualizationFrame): string {
    const artist = (frame.track?.artist || '').trim().toUpperCase();
    return artist || 'NO DISC';
  }

  private buildTitle(frame: VisualizationFrame): string {
    return (frame.track?.title || '').trim().toUpperCase();
  }

  protected override onTheme(_theme: DisplayTheme): void {
    /* colors read live in draw() */
  }
}
