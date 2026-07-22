import { Graphics } from 'pixi.js';
import { VisualizationFrame } from '../frame.model';
import { BaseRenderer } from './renderer';

/**
 * ThemeRenderer — the HERO of the display.
 *
 * On a real Pioneer OEL head-unit the animated theme (the leaping dolphin) was
 * the dominant visual element, with the spectrum playing a supporting role.
 * This renderer draws a large, gracefully arcing dolphin (~60% of the active
 * render height) layered with the phosphor core/glow/afterglow colors so it
 * reads as a lit object rather than a flat silhouette.
 *
 * Motion is driven purely by wall-clock time (`elapsed`) — there is NO frame
 * throttling — so the leap is perfectly smooth at the display refresh rate.
 * Motion blur / afterglow is provided by the persistence pass, not here.
 */
export class ThemeRenderer extends BaseRenderer {
  /** Last-drawn dolphin bounding box in internal pixels (for the debug overlay). */
  bounds = { x: 0, y: 0, w: 0, h: 0 };

  protected draw(g: Graphics, frame: VisualizationFrame | null, _dt: number, elapsed: number): void {
    const { width, height } = this;
    const bass = frame?.bass ?? 0;
    const energy = frame?.energy ?? 0;

    // --- Dolphin geometry -------------------------------------------------
    // ABSOLUTE CENTERPIECE: large leaping arc filling the central display.
    const cx = width * 0.5;
    const waterY = height * 0.72;
    const bodyLen = width * 0.44; // less horizontal travel → stays centered
    const arcHeight = height * 0.42; // fits inside frame at peak

    // Continuous leap cycle: the dolphin rises, arcs and dives, then repeats.
    const cycle = 3.6; // seconds per leap
    const t = (elapsed % cycle) / cycle; // 0..1
    // Horizontal travel across the arc.
    const x = cx - bodyLen * 0.5 + t * bodyLen;
    // Parabolic arc: high in the middle, at the waterline at the ends.
    const arc = Math.sin(t * Math.PI);
    const y = waterY - arc * arcHeight;
    // Body angle follows the arc tangent. Add a minimum tilt so the dolphin
    // is NEVER fully horizontal — it always looks like it's leaping/diving.
    const rawAngle = Math.cos(t * Math.PI) * 1.1;
    const minTilt = 0.25; // radians — never flat
    const angle = rawAngle >= 0
      ? Math.max(rawAngle, minTilt)
      : Math.min(rawAngle, -minTilt);
    // Breathing scale from the bass — subtle life.
    const scale = 1 + bass * 0.06;

    this.drawDolphin(g, x, y, angle, scale, energy);
  }

  private drawDolphin(
    g: Graphics,
    x: number,
    y: number,
    angle: number,
    scale: number,
    _energy: number
  ): void {
    const { theme } = this;
    // Body half-length (nose at +L, tail at -L) and max half-height.
    // Large and dominant — the dolphin IS the display.
    const L = 58 * scale;
    const belly = 18 * scale;
    const rot = -angle;
    const cos = Math.cos(rot);
    const sin = Math.sin(rot);

    // Transform a local point into scene space.
    const xf = (px: number, py: number): [number, number] => [
      x + px * cos - py * sin,
      y + px * sin + py * cos
    ];

    // Axis-aligned bounding box of the local extent, rotated into scene space.
    const lx0 = -L * 1.4, lx1 = L * 1.05;
    const ly0 = -belly * 2.0, ly1 = belly * 1.2;
    const corners: Array<[number, number]> = [
      [lx0, ly0], [lx1, ly0], [lx0, ly1], [lx1, ly1]
    ];
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (const [px, py] of corners) {
      const [wx, wy] = xf(px, py);
      minX = Math.min(minX, wx); minY = Math.min(minY, wy);
      maxX = Math.max(maxX, wx); maxY = Math.max(maxY, wy);
    }
    this.bounds = { x: minX, y: minY, w: maxX - minX, h: maxY - minY };

    // --- BODY: smooth bezier silhouette (organic, NOT a CAD polygon) ---------
    // Traced clockwise from the nose tip: over the back, down to the tail,
    // then back along the belly to the beak.
    const [nx, ny] = xf(L, 0);
    g.moveTo(nx, ny);
    // Nose → forehead → melon (rounded head)
    let [cx1, cy1] = xf(L * 0.92, -belly * 0.25);
    let [cx2, cy2] = xf(L * 0.72, -belly * 0.6);
    let [ex, ey] = xf(L * 0.5, -belly * 0.85);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    // Melon → back (ahead of dorsal)
    [cx1, cy1] = xf(L * 0.3, -belly * 1.05);
    [cx2, cy2] = xf(L * 0.05, -belly * 1.0);
    [ex, ey] = xf(-L * 0.15, -belly * 0.88);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    // Back → peduncle (taper toward tail)
    [cx1, cy1] = xf(-L * 0.4, -belly * 0.7);
    [cx2, cy2] = xf(-L * 0.65, -belly * 0.4);
    [ex, ey] = xf(-L * 0.82, -belly * 0.1);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    // Peduncle → tail notch (top)
    [cx1, cy1] = xf(-L * 0.9, -belly * 0.02);
    [cx2, cy2] = xf(-L * 0.95, belly * 0.02);
    [ex, ey] = xf(-L * 0.82, belly * 0.1);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    // Peduncle → rear belly
    [cx1, cy1] = xf(-L * 0.65, belly * 0.4);
    [cx2, cy2] = xf(-L * 0.4, belly * 0.65);
    [ex, ey] = xf(-L * 0.15, belly * 0.78);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    // Belly → mid belly → front belly
    [cx1, cy1] = xf(L * 0.1, belly * 0.88);
    [cx2, cy2] = xf(L * 0.4, belly * 0.72);
    [ex, ey] = xf(L * 0.65, belly * 0.45);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    // Front belly → under head → nose
    [cx1, cy1] = xf(L * 0.82, belly * 0.25);
    [cx2, cy2] = xf(L * 0.95, belly * 0.08);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, nx, ny);
    g.closePath();
    // INTERIOR-DIM fill: a real OEL object is dimmer inside, bright at the
    // edge. The rim light (below) + scene-glow bloom produce the "lit" halo.
    g.fill({ color: theme.sceneMid, alpha: 0.5 });

    // --- DORSAL FIN: curved, organic (NOT a hard triangle) -------------------
    const [d0x, d0y] = xf(L * 0.2, -belly * 0.95);
    g.moveTo(d0x, d0y);
    [cx1, cy1] = xf(L * 0.15, -belly * 1.5);
    [cx2, cy2] = xf(L * 0.0, -belly * 1.95);
    [ex, ey] = xf(-L * 0.12, -belly * 1.7);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    [cx1, cy1] = xf(-L * 0.2, -belly * 1.4);
    [cx2, cy2] = xf(-L * 0.22, -belly * 1.1);
    [ex, ey] = xf(-L * 0.2, -belly * 0.85);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    g.closePath();
    g.fill({ color: theme.sceneMid, alpha: 0.55 });

    // --- TAIL FLUKE: two curved lobes with a notch ---------------------------
    // Upper lobe
    const [t0x, t0y] = xf(-L * 0.8, -belly * 0.08);
    g.moveTo(t0x, t0y);
    [cx1, cy1] = xf(-L * 1.1, -belly * 0.5);
    [cx2, cy2] = xf(-L * 1.35, -belly * 0.85);
    [ex, ey] = xf(-L * 1.3, -belly * 0.6);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    [cx1, cy1] = xf(-L * 1.15, -belly * 0.3);
    [cx2, cy2] = xf(-L * 1.0, -belly * 0.05);
    [ex, ey] = xf(-L * 0.95, belly * 0.0);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    g.closePath();
    g.fill({ color: theme.sceneMid, alpha: 0.5 });
    // Lower lobe
    const [t1x, t1y] = xf(-L * 0.8, belly * 0.08);
    g.moveTo(t1x, t1y);
    [cx1, cy1] = xf(-L * 1.1, belly * 0.45);
    [cx2, cy2] = xf(-L * 1.32, belly * 0.75);
    [ex, ey] = xf(-L * 1.28, belly * 0.55);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    [cx1, cy1] = xf(-L * 1.12, belly * 0.25);
    [cx2, cy2] = xf(-L * 0.98, belly * 0.05);
    [ex, ey] = xf(-L * 0.95, belly * 0.0);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    g.closePath();
    g.fill({ color: theme.sceneMid, alpha: 0.5 });

    // --- PECTORAL FIN: a distinct curved flipper under the body --------------
    const [p0x, p0y] = xf(L * 0.35, belly * 0.5);
    g.moveTo(p0x, p0y);
    [cx1, cy1] = xf(L * 0.2, belly * 0.9);
    [cx2, cy2] = xf(L * 0.0, belly * 1.2);
    [ex, ey] = xf(L * 0.05, belly * 1.05);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    [cx1, cy1] = xf(L * 0.12, belly * 0.8);
    [cx2, cy2] = xf(L * 0.25, belly * 0.6);
    [ex, ey] = xf(L * 0.3, belly * 0.52);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    g.closePath();
    g.fill({ color: theme.sceneMid, alpha: 0.5 });

    // --- RIM LIGHT: bright edge along the back (reads as "lit phosphor") -----
    const [r0x, r0y] = xf(L * 0.95, -belly * 0.1);
    g.moveTo(r0x, r0y);
    [cx1, cy1] = xf(L * 0.7, -belly * 0.55);
    [cx2, cy2] = xf(L * 0.4, -belly * 0.85);
    [ex, ey] = xf(L * 0.1, -belly * 0.98);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    [cx1, cy1] = xf(-L * 0.15, -belly * 0.92);
    [cx2, cy2] = xf(-L * 0.45, -belly * 0.7);
    [ex, ey] = xf(-L * 0.7, -belly * 0.35);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    // Bright edge — this is what makes it read as a lit phosphor creature.
    g.stroke({ color: theme.core, alpha: 1.0, width: 2.2 });

    // Belly rim light (softer, along the underside).
    const [b0x, b0y] = xf(L * 0.9, belly * 0.12);
    g.moveTo(b0x, b0y);
    [cx1, cy1] = xf(L * 0.6, belly * 0.5);
    [cx2, cy2] = xf(L * 0.2, belly * 0.8);
    [ex, ey] = xf(-L * 0.2, belly * 0.82);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    [cx1, cy1] = xf(-L * 0.5, belly * 0.7);
    [cx2, cy2] = xf(-L * 0.7, belly * 0.45);
    [ex, ey] = xf(-L * 0.8, belly * 0.15);
    g.bezierCurveTo(cx1, cy1, cx2, cy2, ex, ey);
    g.stroke({ color: theme.sceneBright, alpha: 0.7, width: 1.6 });

    // --- EYE: a dark point near the head for character -----------------------
    const [eyx, eyy] = xf(L * 0.62, -belly * 0.2);
    g.circle(eyx, eyy, 1.5 * scale);
    g.fill({ color: theme.backgroundDeep, alpha: 0.95 });
  }
}
