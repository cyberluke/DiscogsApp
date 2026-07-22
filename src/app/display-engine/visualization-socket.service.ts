import { Injectable, NgZone, OnDestroy } from '@angular/core';
import { environment } from '../../environments/environment';
import { SPECTRUM_BANDS, VisualizationFrame } from './frame.model';

/**
 * Receives real-time visualization frames from the backend audio engine over
 * the `/visualization/frames` WebSocket and exposes a small interpolation
 * buffer so the PixiJS render loop can sample smooth values between the
 * ~60 Hz network frames.
 *
 * Design notes:
 * - Deliberately does NOT emit an RxJS value per frame. Per-frame Observables
 *   would trigger Angular change detection 60x/second. The display engine
 *   instead polls `sample()` from its own requestAnimationFrame loop.
 * - The WebSocket callbacks run outside Angular's zone (the render loop is
 *   zone-free), so no change detection is triggered on message receipt.
 */
@Injectable({ providedIn: 'root' })
export class VisualizationSocketService implements OnDestroy {
  private socket?: WebSocket;
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private destroyed = false;

  /** Recent frames with their browser arrival time for interpolation. */
  private buffer: { arrival: number; frame: VisualizationFrame }[] = [];
  private readonly maxBuffer = 8;

  private connected = false;
  private readonly listeners = new Set<(connected: boolean) => void>();

  constructor(private readonly zone: NgZone) {}

  /** Latest connectivity state. */
  isConnected(): boolean {
    return this.connected;
  }

  /** Subscribe to connectivity changes. Returns an unsubscribe function. */
  onConnectionChange(listener: (connected: boolean) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  connect(): void {
    if (typeof WebSocket === 'undefined') {
      return;
    }
    if (this.socket && (this.socket.readyState === WebSocket.CONNECTING || this.socket.readyState === WebSocket.OPEN)) {
      return;
    }

    // Run the socket entirely outside Angular so high-frequency messages
    // never trigger change detection.
    this.zone.runOutsideAngular(() => {
      try {
        const socket = new WebSocket(this.websocketUrl());
        this.socket = socket;
        socket.onopen = () => this.setConnected(true);
        socket.onmessage = message => this.handleMessage(message.data);
        socket.onerror = () => socket.close();
        socket.onclose = () => {
          this.setConnected(false);
          this.scheduleReconnect();
        };
      } catch (error) {
        console.debug('Visualization WebSocket unavailable', error);
        this.scheduleReconnect();
      }
    });
  }

  disconnect(): void {
    this.destroyed = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
    if (this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = undefined;
    }
    this.setConnected(false);
  }

  ngOnDestroy(): void {
    this.disconnect();
  }

  /**
   * Sample an interpolated frame for the given browser timestamp
   * (`performance.now()`). Interpolates scalar fields between the two most
   * recent frames; spectrum arrays are interpolated band-by-band. Returns
   * `null` until the first frame has arrived.
   */
  sample(now: number): VisualizationFrame | null {
    const count = this.buffer.length;
    if (count === 0) {
      return null;
    }
    if (count === 1) {
      return this.buffer[0].frame;
    }

    const last = this.buffer[count - 1];
    const prev = this.buffer[count - 2];
    const span = last.arrival - prev.arrival;
    let t = span > 0 ? (now - prev.arrival) / span : 1;
    t = Math.max(0, Math.min(1, t));

    return this.interpolate(prev.frame, last.frame, t);
  }

  /** Most recent raw frame without interpolation. */
  latest(): VisualizationFrame | null {
    return this.buffer.length ? this.buffer[this.buffer.length - 1].frame : null;
  }

  private handleMessage(data: string): void {
    try {
      const frame = JSON.parse(data) as VisualizationFrame;
      if (!frame || !Array.isArray(frame.fft)) {
        return;
      }
      this.buffer.push({ arrival: performance.now(), frame });
      if (this.buffer.length > this.maxBuffer) {
        this.buffer.shift();
      }
    } catch (error) {
      console.debug('Ignored visualization frame', error);
    }
  }

  private interpolate(a: VisualizationFrame, b: VisualizationFrame, t: number): VisualizationFrame {
    const lerp = (x: number, y: number): number => x + (y - x) * t;
    const fft = new Array<number>(SPECTRUM_BANDS);
    const peaks = new Array<number>(SPECTRUM_BANDS);
    for (let i = 0; i < SPECTRUM_BANDS; i++) {
      fft[i] = lerp(a.fft[i] ?? 0, b.fft[i] ?? 0);
      peaks[i] = lerp(a.peaks[i] ?? 0, b.peaks[i] ?? 0);
    }
    return {
      timestamp: lerp(a.timestamp, b.timestamp),
      fft,
      peaks,
      vuLeft: lerp(a.vuLeft, b.vuLeft),
      vuRight: lerp(a.vuRight, b.vuRight),
      peakLeft: lerp(a.peakLeft, b.peakLeft),
      peakRight: lerp(a.peakRight, b.peakRight),
      bass: lerp(a.bass, b.bass),
      mid: lerp(a.mid, b.mid),
      treble: lerp(a.treble, b.treble),
      energy: lerp(a.energy, b.energy),
      width: lerp(a.width, b.width),
      // Beat is a discrete event: surface it only on the newest frame.
      beat: t > 0.5 ? b.beat : a.beat,
      bpm: lerp(a.bpm, b.bpm),
      key: t > 0.5 ? b.key : a.key,
      phraseProgress: lerp(a.phraseProgress, b.phraseProgress),
      phraseLength: b.phraseLength,
      track: t > 0.5 ? b.track : a.track,
      nextTransition: t > 0.5 ? b.nextTransition : a.nextTransition
    };
  }

  private setConnected(value: boolean): void {
    if (this.connected === value) {
      return;
    }
    this.connected = value;
    this.listeners.forEach(listener => listener(value));
  }

  private scheduleReconnect(): void {
    if (this.destroyed || this.reconnectTimer) {
      return;
    }
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined;
      this.connect();
    }, 3000);
  }

  private websocketUrl(): string {
    const base = (environment as { serviceUrl?: string }).serviceUrl || 'http://127.0.0.1:5000';
    const url = new URL(base, typeof window !== 'undefined' ? window.location.origin : base);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = '/visualization/frames';
    url.search = '';
    url.hash = '';
    return url.toString();
  }
}
