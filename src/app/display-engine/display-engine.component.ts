import {
  AfterViewInit,
  Component,
  ElementRef,
  HostListener,
  Input,
  NgZone,
  OnDestroy,
  ViewChild
} from '@angular/core';
import { Application, Container } from 'pixi.js';
import { VisualizationSocketService } from './visualization-socket.service';
import { DISPLAY_HEIGHT, DISPLAY_WIDTH, LayerContext } from './layers/layer';
import { ILayer } from './layers/layer';
import { BackgroundLayer } from './layers/background-layer';
import { VuMeterLayer } from './layers/vu-meter-layer';
import { TrackInfoLayer } from './layers/track-info-layer';
import { AiOverlayLayer } from './layers/ai-overlay-layer';
import { DebugOverlayLayer, VisualWeight } from './layers/debug-overlay-layer';
import { IRenderer } from './renderers/renderer';
import { DolphinSpriteRenderer } from './renderers/dolphin-sprite-renderer';
import { WaveRenderer } from './renderers/wave-renderer';
import { SpectrumRenderer } from './renderers/spectrum-renderer';
import { PersistencePass } from './renderers/persistence-pass';
import { PostProcessingRenderer } from './renderers/post-processing-renderer';
import { DEFAULT_THEME_ID, DisplayTheme, resolveTheme } from './theme';

/**
 * The Pioneer Heritage Display Engine.
 *
 * Renders a fixed 320×128 internal canvas that is integer-scaled to fit its
 * container with nearest-neighbour filtering, preserving the crisp pixel
 * character of a hardware OEL display. All PixiJS work runs outside Angular's
 * zone so the 60 fps render loop never triggers change detection.
 *
 * Usage:
 *   <app-display-engine themeId="heritage-blue"></app-display-engine>
 */
@Component({
  selector: 'app-display-engine',
  template: `<div #host class="display-host"></div>`,
  styles: [
    `
      :host {
        display: block;
        width: 100%;
        height: 100%;
      }
      .display-host {
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #000;
        overflow: hidden;
      }
      .display-host canvas {
        image-rendering: pixelated;
        image-rendering: crisp-edges;
      }
    `
  ]
})
export class DisplayEngineComponent implements AfterViewInit, OnDestroy {
  @ViewChild('host', { static: true }) hostRef!: ElementRef<HTMLDivElement>;

  /** Theme id to apply. Defaults to heritage-blue. */
  @Input()
  set themeId(value: string | null | undefined) {
    this.theme = resolveTheme(value);
    for (const layer of this.layers) {
      layer.applyTheme(this.theme);
    }
    for (const renderer of this.renderers) {
      renderer.onTheme(this.theme);
    }
    this.post?.applyTheme(this.theme);
  }

  private app?: Application;
  private theme: DisplayTheme = resolveTheme(DEFAULT_THEME_ID);

  // Modular render pipeline.
  private readonly layers: ILayer[] = [];
  private readonly renderers: IRenderer[] = [];
  private persistence?: PersistencePass;
  private post?: PostProcessingRenderer;
  private elapsed = 0;

  // Typed references for the debug overlay.
  private dolphinSprite?: DolphinSpriteRenderer;
  private waveRenderer?: WaveRenderer;
  private spectrumRenderer?: SpectrumRenderer;
  private debugOverlay?: DebugOverlayLayer;

  // FPS tracking for the debug overlay.
  private fps = 0;
  private fpsAccum = 0;
  private fpsFrames = 0;

  // Visual-weight metrics (computed from canvas pixels, one frame behind).
  private pendingWeights: VisualWeight[] = [];
  private weightAccum = 0;
  private static readonly WEIGHT_INTERVAL = 0.25; // recompute every 250ms

  private readonly onKeyDown = (e: KeyboardEvent): void => {
    if (e.key === 'd' || e.key === 'D') {
      this.debugOverlay?.toggle();
    }
  };

  private rafId = 0;
  private lastTime = 0;
  private resizeObserver?: ResizeObserver;
  private unsubscribeConnection?: () => void;
  private destroyed = false;

  constructor(
    private readonly zone: NgZone,
    private readonly socket: VisualizationSocketService
  ) {}

  ngAfterViewInit(): void {
    // Run the entire PixiJS lifecycle outside Angular's zone.
    this.zone.runOutsideAngular(() => this.bootstrap());
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    if (this.rafId) {
      cancelAnimationFrame(this.rafId);
      this.rafId = 0;
    }
    this.resizeObserver?.disconnect();
    this.unsubscribeConnection?.();
    window.removeEventListener('keydown', this.onKeyDown);
    for (const layer of this.layers) {
      layer.destroy();
    }
    for (const renderer of this.renderers) {
      renderer.destroy();
    }
    this.persistence?.destroy();
    this.post?.destroy();
    this.layers.length = 0;
    this.renderers.length = 0;
    this.app?.destroy(true, { children: true, texture: false });
    this.socket.disconnect();
  }

  @HostListener('window:resize')
  onWindowResize(): void {
    this.fitCanvas();
  }

  private async bootstrap(): Promise<void> {
    const app = new Application();
    await app.init({
      width: DISPLAY_WIDTH,
      height: DISPLAY_HEIGHT,
      backgroundColor: this.theme.backgroundDeep,
      antialias: false,
      resolution: 1,
      autoDensity: false,
      // Prefer a crisp, non-blurred upscale.
      preferWebGLVersion: 2
    });
    this.app = app;

    const host = this.hostRef.nativeElement;
    host.appendChild(app.canvas);
    this.fitCanvas();

    // Observe container size changes for responsive integer scaling.
    this.resizeObserver = new ResizeObserver(() => this.fitCanvas());
    this.resizeObserver.observe(host);

    // Build the scene. Everything renders into a dedicated scene container that
    // is a child of the stage — post-processing filters are applied to this
    // container (NOT the stage), because PixiJS v8 does not reliably render
    // filters attached to the root stage.
    //
    // Composition (back → front):
    //   1. BackgroundLayer            — crisp, opaque backdrop
    //   2. PersistencePass.output     — theme + waves + spectrum with afterglow
    //   3. VuMeter / TrackInfo / AiOverlay — crisp text & meters on top
    const scene = new Container();
    app.stage.addChild(scene);

    const layerContext: LayerContext = {
      root: scene,
      theme: this.theme,
      width: DISPLAY_WIDTH,
      height: DISPLAY_HEIGHT
    };

    // Crisp backdrop (does NOT feed the persistence buffer, so it never smears).
    this.addLayer(new BackgroundLayer(), layerContext);

    // Live animated renderers feed the phosphor persistence pass.
    this.persistence = new PersistencePass(DISPLAY_WIDTH, DISPLAY_HEIGHT);
    scene.addChild(this.persistence.output);

    this.dolphinSprite = new DolphinSpriteRenderer();
    this.waveRenderer = new WaveRenderer();
    this.spectrumRenderer = new SpectrumRenderer();
    this.addRenderer(this.dolphinSprite, this.persistence.live);
    this.addRenderer(this.waveRenderer, this.persistence.live);
    this.addRenderer(this.spectrumRenderer, this.persistence.live);

    // Crisp overlays on top of the glowing scene.
    this.addLayer(new VuMeterLayer(), layerContext);
    this.addLayer(new TrackInfoLayer(), layerContext);
    this.addLayer(new AiOverlayLayer(), layerContext);

    // Diagnostic overlay (toggle with `D`) — rendered last, on top.
    this.debugOverlay = new DebugOverlayLayer();
    this.addLayer(this.debugOverlay, layerContext);

    // Final glass: bloom on the phosphor trail only + CRT on the whole scene.
    this.post = new PostProcessingRenderer(scene, this.persistence.glowWrap, this.theme);

    // Toggle the debug overlay with the `D` key.
    window.addEventListener('keydown', this.onKeyDown);

    // Connect the data source and start rendering.
    this.socket.connect();
    this.unsubscribeConnection = this.socket.onConnectionChange(() => {
      /* connectivity could drive an idle overlay in future */
    });

    this.lastTime = performance.now();
    this.loop();
  }

  private loop = (): void => {
    if (this.destroyed) {
      return;
    }
    this.rafId = requestAnimationFrame(this.loop);

    const now = performance.now();
    const dt = Math.min(0.1, (now - this.lastTime) / 1000);
    this.lastTime = now;
    this.elapsed += dt;

    // FPS tracking (rolling 0.5s window).
    this.fpsAccum += dt;
    this.fpsFrames++;
    if (this.fpsAccum >= 0.5) {
      this.fps = this.fpsFrames / this.fpsAccum;
      this.fpsAccum = 0;
      this.fpsFrames = 0;
    }

    // The socket already interpolates between audio frames, so `frame` is a
    // smooth, continuous signal. Renderers are driven purely by wall-clock
    // time (`elapsed`) + this interpolated frame — no throttling, full rate.
    const frame = this.socket.sample(now);

    for (const renderer of this.renderers) {
      renderer.render(frame, dt, this.elapsed);
    }

    // Feed the debug overlay with fresh metrics + bounding boxes (before the
    // overlay layer draws this frame).
    if (this.debugOverlay?.isVisible) {
      // Recompute visual weights periodically (expensive pixel readback).
      this.weightAccum += dt;
      if (this.weightAccum >= DisplayEngineComponent.WEIGHT_INTERVAL) {
        this.weightAccum = 0;
        this.pendingWeights = this.computeVisualWeights();
      }

      this.debugOverlay.setMetrics({
        fps: this.fps,
        bloom: this.post?.bloomStrength ?? 0,
        persistence: this.persistence?.persistence ?? 0,
        boxes: [
          { label: 'DOLPHIN', ...this.dolphinSprite!.bounds },
          { label: 'WAVE', ...this.waveRenderer!.bounds },
          { label: 'FFT', ...this.spectrumRenderer!.bounds }
        ],
        weights: this.pendingWeights
      });
    }

    for (const layer of this.layers) {
      if (frame) {
        layer.update(frame, dt);
      }
    }

    // Advance the phosphor afterglow / motion-blur feedback buffer.
    if (this.app && this.persistence) {
      this.persistence.update(this.app.renderer);
    }

    if (frame && this.post) {
      if (frame.beat) {
        this.post.pulse(frame.energy);
      }
      this.post.relax(dt, this.theme);
    }

    this.app?.renderer.render(this.app.stage);
  };

  /**
   * Compute visual-weight metrics for each element by reading canvas pixels.
   * Returns luminance, occupied pixels, contrast vs background, glow, and a
   * composite score (0–100) for the dolphin, waves, and FFT.
   */
  private computeVisualWeights(): VisualWeight[] {
    const app = this.app;
    if (!app) {
      return [];
    }

    const canvas = app.canvas as HTMLCanvasElement;
    const gl = (canvas.getContext('webgl2') || canvas.getContext('webgl')) as
      | WebGLRenderingContext
      | WebGL2RenderingContext
      | null;
    if (!gl) {
      return [];
    }

    const w = DISPLAY_WIDTH;
    const h = DISPLAY_HEIGHT;
    const pixels = new Uint8Array(w * h * 4);
    gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, pixels);

    const boxes = [
      { label: 'DOLPHIN', ...this.dolphinSprite!.bounds },
      { label: 'WAVE', ...this.waveRenderer!.bounds },
      { label: 'FFT', ...this.spectrumRenderer!.bounds }
    ];

    // Compute average background luminance (pixels outside all boxes).
    let bgLumSum = 0;
    let bgCount = 0;
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const inBox = boxes.some(
          (b) => x >= b.x && x < b.x + b.w && y >= b.y && y < b.y + b.h
        );
        if (!inBox) {
          const i = (y * w + x) * 4;
          bgLumSum += 0.299 * pixels[i] + 0.587 * pixels[i + 1] + 0.114 * pixels[i + 2];
          bgCount++;
        }
      }
    }
    const bgLum = bgCount > 0 ? bgLumSum / bgCount : 0;

    const weights: VisualWeight[] = [];
    for (const box of boxes) {
      const bx = Math.max(0, Math.floor(box.x));
      const by = Math.max(0, Math.floor(box.y));
      const bw = Math.min(w - bx, Math.ceil(box.w));
      const bh = Math.min(h - by, Math.ceil(box.h));

      let lumSum = 0;
      let occupied = 0;
      const threshold = 30;

      for (let y = by; y < by + bh; y++) {
        for (let x = bx; x < bx + bw; x++) {
          const i = (y * w + x) * 4;
          const lum = 0.299 * pixels[i] + 0.587 * pixels[i + 1] + 0.114 * pixels[i + 2];
          lumSum += lum;
          if (lum > threshold) {
            occupied++;
          }
        }
      }

      const area = bw * bh;
      const avgLum = area > 0 ? lumSum / area : 0;
      const contrast = avgLum - bgLum;

      // Glow: average luminance in a 4px ring around the box.
      let glowSum = 0;
      let glowCount = 0;
      const ring = 4;
      for (let y = Math.max(0, by - ring); y < Math.min(h, by + bh + ring); y++) {
        for (let x = Math.max(0, bx - ring); x < Math.min(w, bx + bw + ring); x++) {
          const inBox = x >= bx && x < bx + bw && y >= by && y < by + bh;
          if (!inBox) {
            const i = (y * w + x) * 4;
            glowSum += 0.299 * pixels[i] + 0.587 * pixels[i + 1] + 0.114 * pixels[i + 2];
            glowCount++;
          }
        }
      }
      const glow = glowCount > 0 ? glowSum / glowCount : 0;

      // Composite score: weighted combination of luminance, occupancy, contrast, glow.
      const lumScore = Math.min(100, (avgLum / 255) * 100);
      const occScore = Math.min(100, (occupied / area) * 100);
      const contrastScore = Math.min(100, Math.max(0, contrast / 2));
      const glowScore = Math.min(100, (glow / 255) * 100);
      const score = Math.round(
        0.35 * lumScore + 0.25 * occScore + 0.25 * contrastScore + 0.15 * glowScore
      );

      weights.push({
        label: box.label,
        luminance: Math.round(avgLum),
        occupiedPixels: occupied,
        contrast: Math.round(contrast),
        glow: Math.round(glow),
        score
      });
    }

    return weights;
  }

  /** Register a crisp overlay layer (background / text / meters). */
  private addLayer(layer: ILayer, context: LayerContext): void {
    layer.init(context);
    this.layers.push(layer);
  }

  /** Register a live animated renderer into a parent container. */
  private addRenderer(renderer: IRenderer, parent: Container): void {
    parent.addChild(renderer.container);
    renderer.onInit?.(DISPLAY_WIDTH, DISPLAY_HEIGHT, this.theme);
    this.renderers.push(renderer);
  }

  /** Integer-scale the fixed internal canvas to fit the host, centered. */
  private fitCanvas(): void {
    const app = this.app;
    const host = this.hostRef?.nativeElement;
    if (!app || !host) {
      return;
    }
    const hostWidth = host.clientWidth;
    const hostHeight = host.clientHeight;
    if (!hostWidth || !hostHeight) {
      return;
    }

    const scale = Math.max(
      1,
      Math.floor(Math.min(hostWidth / DISPLAY_WIDTH, hostHeight / DISPLAY_HEIGHT))
    );
    const cssWidth = DISPLAY_WIDTH * scale;
    const cssHeight = DISPLAY_HEIGHT * scale;

    const canvas = app.canvas;
    canvas.style.width = `${cssWidth}px`;
    canvas.style.height = `${cssHeight}px`;
  }
}
