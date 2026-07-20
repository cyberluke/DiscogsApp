import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { AiTrackRecommendation, ChatContext, ChatRequest, ChatResponse, PlaybackStatus, Track, VideoAsset, VideoSyncState } from '../dao/track';

export interface AiDjChatMessage {
  role: 'user' | 'assistant';
  content: string;
  suggested_tracks?: AiTrackRecommendation[];
}

export interface AiDjState {
  context: ChatContext | null;
  messages: AiDjChatMessage[];
  recommendations: AiTrackRecommendation[];
  inputText: string;
  aiUsed: boolean;
  useNativeVideoOffset: boolean;
  nativeVideoManualOffsetSeconds: number;
}

@Injectable({
  providedIn: 'root'
})
export class AiDjService {
  private readonly serviceUrl = environment.serviceUrl;
  private readonly stateKey = 'discogs.aiDj.state';
  private state: AiDjState = this.loadState();

  constructor(private readonly http: HttpClient) {}

  stateSnapshot(): AiDjState {
    return {
      ...this.state,
      messages: [...this.state.messages],
      recommendations: [...this.state.recommendations]
    };
  }

  saveState(update: Partial<AiDjState>): void {
    this.state = { ...this.state, ...update };
    this.persistState();
  }

  context(): Observable<ChatContext> {
    return this.http.get<ChatContext>(`${this.serviceUrl}/api/chat/context`);
  }

  chat(request: ChatRequest): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.serviceUrl}/api/chat`, request);
  }

  recommendationsForCurrent(limit = 5): Observable<ChatResponse> {
    return this.http.get<ChatResponse>(`${this.serviceUrl}/api/recommendations/current?limit=${limit}`);
  }

  play(track: Track): Observable<PlaybackStatus> {
    return this.http.post<PlaybackStatus>(`${this.serviceUrl}/api/play`, { track });
  }

  videoSync(): Observable<VideoSyncState> {
    return this.http.get<VideoSyncState>(`${this.serviceUrl}/video/sync`);
  }

  downloadVideo(): Observable<VideoSyncState> {
    return this.http.post<VideoSyncState>(`${this.serviceUrl}/video/download`, {});
  }

  saveVideoOffsetPreference(manualOffsetSeconds: number, useDetectedOffset: boolean): Observable<VideoSyncState> {
    return this.http.post<VideoSyncState>(`${this.serviceUrl}/video/offset`, {
      manual_offset_seconds: manualOffsetSeconds,
      use_detected_offset: useDetectedOffset
    });
  }

  mediaUrl(video: VideoAsset): string {
    if (!video.url) {
      return '';
    }
    if (/^https?:\/\//i.test(video.url)) {
      return video.url;
    }
    return `${this.serviceUrl}${video.url.startsWith('/') ? '' : '/'}${video.url}`;
  }

  private loadState(): AiDjState {
    const emptyState: AiDjState = {
      context: null,
      messages: [],
      recommendations: [],
      inputText: '',
      aiUsed: false,
      useNativeVideoOffset: true,
      nativeVideoManualOffsetSeconds: 0
    };
    try {
      if (typeof sessionStorage === 'undefined') {
        return emptyState;
      }
      const raw = sessionStorage.getItem(this.stateKey);
      return raw ? { ...emptyState, ...JSON.parse(raw) } : emptyState;
    } catch {
      return emptyState;
    }
  }

  private persistState(): void {
    try {
      if (typeof sessionStorage !== 'undefined') {
        sessionStorage.setItem(this.stateKey, JSON.stringify(this.state));
      }
    } catch {
      // Session persistence is a convenience; chat should still work without it.
    }
  }
}