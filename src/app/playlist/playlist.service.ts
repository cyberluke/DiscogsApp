// playlist.service.ts

import { Injectable } from '@angular/core';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { Playlist, Track } from '../dao/track'; // Assuming Track is a class or interface
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class PlaylistService {
  private serviceUrl = environment.serviceUrl;

  // Your playlist array
  private playlist: Playlist = {
    name: '001 Dance',
    tracks: []
  };
  private playlists: Playlist[] = [];

  constructor(private http: HttpClient) { }

  addToPlaylist(track: Track) {
    this.playlist.tracks.push(track);
    console.log(this.playlist);
    // Additional logic to handle the playlist
  }

  removeAtIndex(index: number) {
    this.playlist.tracks.splice(index, 1);
  }

  getPlaylist() {
    return this.playlist;
  }

  setPlaylist(playlist: Playlist) {
    this.playlist = playlist;
  }

  playPlaylist(playlist: Playlist) {
    this.http.post(`${this.serviceUrl}/playlist`, playlist)
    .subscribe(response => {
      console.log(response);
      // Handle response here
    });
  }

  playSingleTrack(track: Track) {
    this.http.post(`${this.serviceUrl}/track`, track)
      .subscribe(response => {
        console.log(response);
        // Handle response here
      });
  }
  
  loadAll(): void {
    this.http.get<Playlist[]>(`${this.serviceUrl}/playlists`)
    .subscribe({
      next: (response) => {
        console.log(response);
        this.playlists = response;
      },
      error: (error) => {
        console.error('Error fetching playlists:', error);
      },
      complete: () => console.log('Playlist loading completed')
    });
  }

  getPlaylists(): Playlist[] {
    return this.playlists;
  }

  savePlaylist(playlistName: string) {
    this.playlist.name = playlistName;

    this.http.post<Playlist>(`${this.serviceUrl}/save-playlist`, this.playlist)
      .subscribe(response => {
        console.log(response);
        // Handle response here
      });
  }
  
}
