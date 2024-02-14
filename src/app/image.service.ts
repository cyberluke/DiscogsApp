import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { environment } from '../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ImageService {
  private serviceUrl = environment.serviceUrl;

  constructor(private http: HttpClient) {}

  downloadImage(imageUrl: string, rename: string) {
    return this.http.post<{url: string}>(`${this.serviceUrl}/download-image`, { image_url: imageUrl, rename: rename});
  }
}
