import { Injectable, NgZone, OnDestroy } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { BehaviorSubject, EMPTY, Observable, Subject, throwError, timer } from 'rxjs';
import { catchError, switchMap, takeUntil, tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import {
  PlaybackProgress,
  PlaybackQueue,
  PlaybackStatus,
  Playlist,
  RecommendationQuery,
  RecommendationResponse,
  RuntimeEvent,
  RuntimeEventType,
  Track
} from '../dao/track';

const idleStatus: PlaybackStatus = {
  current_track: null,
  current_playlist: null,
  queue: [],
  upcoming: [],
  elapsed: 0,
  duration: 0,
  remaining: 0,
  progress: 0,
  current_deck: null,
  current_cd: null,
  playback_state: 'idle',
  last_update_timestamp: 0,
  load_delay_seconds: 0,
  load_delay_remaining: 0,
  playback_start_delay_seconds: 0,
  playback_start_delay_enabled: true,
  mechanical_state: 'unknown',
  hardware_ready: false,
  display_disc: null,
  loaded_disc: null,
  door_open: false,
  power_state: 'unknown',
  model: null,
  player_status_raw: null,
  last_hardware_event: null,
  error: null
};

@Injectable({
  providedIn: 'root'
})
export class PlaybackService implements OnDestroy {
  private readonly serviceUrl = environment.serviceUrl;
  private readonly destroy$ = new Subject<void>();
  private readonly statusSubject = new BehaviorSubject<PlaybackStatus>(idleStatus);
  private readonly eventSubject = new Subject<RuntimeEvent>();
  private readonly liveConnectedSubject = new BehaviorSubject<boolean>(false);
  private socket?: WebSocket;
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private destroyed = false;

  status$ = this.statusSubject.asObservable();
  events$ = this.eventSubject.asObservable();
  liveConnected$ = this.liveConnectedSubject.asObservable();

  constructor(private readonly http: HttpClient, private readonly zone: NgZone) {
    this.connectEvents();
    this.startStatusRefresh();
  }

  playPlaylist(playlist: Playlist): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/playlist/play`, playlist).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  playTrack(track: Track): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/track/play`, track).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  pause(): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/playlist/pause`, {}).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  resume(): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/playlist/resume`, {}).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  setStartDelayEnabled(enabled: boolean): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/playback/start-delay`, { enabled }).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  resyncHardware(): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/playback/resync`, {}).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  setContinuousStatusEnabled(enabled: boolean): Observable<PlaybackStatus> {
    const suffix = enabled ? 'enable' : 'disable';
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/hardware/continuous-status/${suffix}`, {}).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  stop(): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/playlist/stop`, {}).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  nextTrack(): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/playlist/next`, {}).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  previousTrack(): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/playlist/previous`, {}).pipe(
      tap(status => this.statusSubject.next(status)),
      catchError(error => this.handleCommandError(error))
    );
  }

  status(): Observable<PlaybackStatus> {
    return this.http.get<PlaybackStatus>(`${this.serviceUrl}/playback/status`).pipe(
      tap(status => this.statusSubject.next(status))
    );
  }

  progress(): Observable<PlaybackProgress> {
    return this.http.get<PlaybackProgress>(`${this.serviceUrl}/playback/progress`);
  }

  queue(): Observable<PlaybackQueue> {
    return this.http.get<PlaybackQueue>(`${this.serviceUrl}/queue`);
  }

  recommendations(query: RecommendationQuery): Observable<RecommendationResponse> {
    let params = new HttpParams();
    Object.entries(query).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params = params.set(key, String(value));
      }
    });

    return this.http.get<RecommendationResponse>(`${this.serviceUrl}/recommendations`, { params });
  }

  ngOnDestroy(): void {
    this.destroyed = true;
    this.destroy$.next();
    this.destroy$.complete();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }
    this.liveConnectedSubject.next(false);
    this.socket?.close();
  }

  private startStatusRefresh(): void {
    timer(0, 5000).pipe(
      switchMap(() => this.status().pipe(
        catchError(error => {
          console.error('Playback status refresh failed', error);
          return EMPTY;
        })
      )),
      takeUntil(this.destroy$)
    ).subscribe();
  }

  private connectEvents(): void {
    if (typeof WebSocket === 'undefined') {
      return;
    }

    try {
      this.socket = new WebSocket(this.websocketUrl());
      this.socket.onopen = () => this.zone.run(() => this.liveConnectedSubject.next(true));
      this.socket.onmessage = message => this.zone.run(() => this.handleEvent(message.data));
      this.socket.onerror = () => this.socket?.close();
      this.socket.onclose = () => this.zone.run(() => {
        this.liveConnectedSubject.next(false);
        this.scheduleReconnect();
      });
    } catch (error) {
      console.debug('Playback WebSocket unavailable', error);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.destroyed || this.reconnectTimer) {
      return;
    }

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined;
      this.connectEvents();
    }, 5000);
  }

  private handleEvent(data: string): void {
    try {
      const event = JSON.parse(data) as RuntimeEvent;
      if (event.payload) {
        this.eventSubject.next({ type: this.normalizeEventType(event.type), payload: event.payload });
        this.statusSubject.next(event.payload);
      }
    } catch (error) {
      console.debug('Ignored playback event', error);
    }
  }

  private normalizeEventType(eventType: string): RuntimeEventType {
    const knownTypes: RuntimeEventType[] = [
      'snapshot',
      'playback_started',
      'playback_stopped',
      'progress_tick',
      'queue_changed',
      'playlist_changed',
      'playback_paused',
      'playback_error'
    ];
    return knownTypes.includes(eventType as RuntimeEventType) ? eventType as RuntimeEventType : 'snapshot';
  }

  private handleCommandError(error: unknown): Observable<never> {
    const response = error as { error?: { error?: string; playback?: PlaybackStatus }; message?: string };
    const playback = response.error?.playback || this.statusSubject.value;
    this.statusSubject.next({
      ...playback,
      playback_state: 'error',
      error: response.error?.error || response.message || 'Playback command failed'
    });
    return throwError(() => error);
  }

  private websocketUrl(): string {
    const url = new URL(this.serviceUrl);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.pathname = '/playback/events';
    return url.toString();
  }
}