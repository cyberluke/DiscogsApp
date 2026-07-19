import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { ChatContext, ChatRequest, ChatResponse, PlaybackStatus, Track } from '../dao/track';

@Injectable({
  providedIn: 'root'
})
export class AiDjService {
  private readonly serviceUrl = environment.serviceUrl;

  constructor(private readonly http: HttpClient) {}

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
}