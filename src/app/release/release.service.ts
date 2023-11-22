// release.service.ts

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ReleaseService {
  private releasesUrl = 'http://localhost:5000/releases';  // URL to web api
  private favouriteUrl = 'http://localhost:5000/favourite';  // URL to web api

  constructor(private http: HttpClient) { }

  getReleases(): Observable<any[]> {
    return this.http.get<any[]>(this.releasesUrl);
  }

  addToFavourites(release: any, track: any): Observable<any[]>  {
    const payload = { release, track }; // Adjust payload as per your API requirements

    return this.http.post<any[]>(this.favouriteUrl, payload);
  }
}
