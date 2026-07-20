// release.service.ts

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { AiMetadata } from '../dao/track';

@Injectable({
  providedIn: 'root'
})
export class ReleaseService {
  private readonly serviceUrl = environment.serviceUrl;
  private readonly releasesUrl = `${this.serviceUrl}/releases`;  // URL to web api
  private readonly favouriteUrl = `${this.serviceUrl}/favourite`;  // URL to web api

  constructor(private readonly http: HttpClient) { }

  getReleases(): Observable<any[]> {
    return this.http.get<any[]>(this.releasesUrl);
  }

  addToFavourites(release: any, track: any): Observable<any>  {
    const payload = { release, track }; // Adjust payload as per your API requirements

    return this.http.post<any>(this.favouriteUrl, payload);
  }

  getReleaseAi(releaseId: number): Observable<AiMetadata | null> {
    return this.http.get<AiMetadata>(`${this.serviceUrl}/api/releases/${releaseId}/ai`).pipe(
      catchError(error => error.status === 404 ? of(null) : throwError(() => error))
    );
  }

  enrichRelease(releaseId: number, force = false): Observable<AiMetadata> {
    const url = `${this.serviceUrl}/api/ai/enrich/${releaseId}${force ? '?force=true' : ''}`;
    return this.http.post<AiMetadata>(url, {});
  }
}
