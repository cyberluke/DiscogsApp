import { Injectable, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, Subject, Subscription, tap } from 'rxjs';
import { environment } from '../../environments/environment';
import { PlaybackStatus, QueueState, Track } from '../dao/track';
import { PlaybackService } from '../now-playing/playback.service';

@Injectable({ providedIn: 'root' })
export class QueueService implements OnDestroy {
  private readonly serviceUrl = environment.serviceUrl;
  private readonly queueSubject = new BehaviorSubject<QueueState | null>(null);
  private readonly errorSubject = new Subject<string>();
  private readonly statusSub: Subscription;

  queue$ = this.queueSubject.asObservable();
  error$ = this.errorSubject.asObservable();

  constructor(private readonly http: HttpClient, playbackService: PlaybackService) {
    // Keep queue in sync with real-time WebSocket status updates
    this.statusSub = playbackService.status$.subscribe(status => this.applyStatus(status));
  }

  ngOnDestroy(): void {
    this.statusSub.unsubscribe();
  }

  get current(): QueueState | null {
    return this.queueSubject.value;
  }

  refresh(): Observable<QueueState> {
    return this.http.get<QueueState>(`${this.serviceUrl}/queue`).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  /** Apply a full status snapshot from WebSocket events. */
  applyStatus(status: PlaybackStatus): void {
    this.queueSubject.next({
      current_track: status.current_track,
      queue: status.queue,
      upcoming: status.upcoming,
      current_playlist: status.current_playlist,
      playback_state: status.playback_state,
      current_index: status.current_index ?? 0,
      shuffle: status.shuffle ?? false,
      repeat: status.repeat ?? 'off',
      queue_stats: status.queue_stats ?? null,
      recent_history: status.recent_history ?? [],
    });
  }

  add(track: Track, position: 'next' | 'end' = 'next'): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/add`, { track, position }).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  addMany(tracks: Track[], position: 'next' | 'end' = 'end'): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/add-many`, { tracks, position }).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  remove(index: number): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/remove`, { index }).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  move(fromIndex: number, toIndex: number): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/move`, { from_index: fromIndex, to_index: toIndex }).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  moveToTop(index: number): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/move-to-top`, { index }).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  moveToBottom(index: number): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/move-to-bottom`, { index }).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  clear(): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/clear`, {}).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  playIndex(index: number): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/play-index`, { index }).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  setShuffle(enabled: boolean): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/shuffle`, { enabled }).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  setRepeat(mode: 'off' | 'one' | 'all'): Observable<QueueState> {
    return this.http.post<QueueState>(`${this.serviceUrl}/queue/repeat`, { mode }).pipe(
      tap(state => this.queueSubject.next(state))
    );
  }

  private handleError(error: unknown): void {
    const message = error instanceof Error ? error.message : 'Queue operation failed';
    this.errorSubject.next(message);
  }
}
