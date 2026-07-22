import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface CaptureReleaseSummary {
  release_id: number;
  title: string;
  artist: string;
  deck_number: number;
  cd_position: number;
}

export interface CaptureStatus {
  state: 'idle' | 'running' | 'paused' | 'stopping';
  current_deck: number | null;
  current_release: CaptureReleaseSummary | null;
  current_track: number | null;
  current_filename: string | null;
  elapsed_seconds: number;
  releases_completed: number;
  releases_failed: number;
  total_pending: number;
  state_summary: { total: number; complete: number; partial: number; error: number };
  has_unfinished: boolean;
}

export interface CaptureProgress {
  state: string;
  percent: number;
  done: number;
  total: number;
  elapsed_seconds: number;
  estimated_remaining_seconds: number;
}

export interface CaptureCurrent {
  state: string;
  deck: number | null;
  release: CaptureReleaseSummary | null;
  track: number | null;
  filename: string | null;
  recording: boolean;
  track_duration: number;
}

@Injectable({
  providedIn: 'root'
})
export class CaptureService {
  private readonly serviceUrl = environment.serviceUrl;

  constructor(private readonly http: HttpClient) {}

  start(options?: { deck?: number; release_id?: number; limit?: number }): Observable<{ state: string; error?: string }> {
    return this.http.post<{ state: string; error?: string }>(`${this.serviceUrl}/api/capture/start`, options || {});
  }

  stop(): Observable<{ state: string; error?: string }> {
    return this.http.post<{ state: string; error?: string }>(`${this.serviceUrl}/api/capture/stop`, {});
  }

  pause(): Observable<{ state: string; error?: string }> {
    return this.http.post<{ state: string; error?: string }>(`${this.serviceUrl}/api/capture/pause`, {});
  }

  resume(): Observable<{ state: string; error?: string }> {
    return this.http.post<{ state: string; error?: string }>(`${this.serviceUrl}/api/capture/resume`, {});
  }

  recordCurrent(): Observable<{ state: string; error?: string; track?: string; artist?: string }> {
    return this.http.post<{ state: string; error?: string; track?: string; artist?: string }>(
      `${this.serviceUrl}/api/capture/record-current`, {}
    );
  }

  status(): Observable<CaptureStatus> {
    return this.http.get<CaptureStatus>(`${this.serviceUrl}/api/capture/status`);
  }

  progress(): Observable<CaptureProgress> {
    return this.http.get<CaptureProgress>(`${this.serviceUrl}/api/capture/progress`);
  }

  current(): Observable<CaptureCurrent> {
    return this.http.get<CaptureCurrent>(`${this.serviceUrl}/api/capture/current`);
  }

  log(lines = 50): Observable<{ log: string[] }> {
    return this.http.get<{ log: string[] }>(`${this.serviceUrl}/api/capture/log?lines=${lines}`);
  }
}
