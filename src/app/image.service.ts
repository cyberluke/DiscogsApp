import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class ImageService {

  constructor(private http: HttpClient) {}

  downloadImage(imageUrl: string, rename: string) {
    return this.http.post<{url: string}>('http://localhost:5000/download-image', { image_url: imageUrl, rename: rename});
  }
}
