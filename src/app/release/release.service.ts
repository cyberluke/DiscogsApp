// release.service.ts

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ReleaseService {
  private serviceUrl = environment.serviceUrl;
  private releasesUrl = `${this.serviceUrl}/releases`;  // URL to web api
  private favouriteUrl = `${this.serviceUrl}/favourite`;  // URL to web api

  constructor(private http: HttpClient) { }

  getReleases(): Observable<any[]> {
    return this.http.get<any[]>(this.releasesUrl);
  }

  addToFavourites(release: any, track: any): Observable<any[]>  {
    const payload = { release, track }; // Adjust payload as per your API requirements

    return this.http.post<any[]>(this.favouriteUrl, payload);
  }
}
