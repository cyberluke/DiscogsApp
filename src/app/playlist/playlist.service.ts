// playlist.service.ts

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Playlist, Track } from '../dao/track'; // Assuming Track is a class or interface
import { environment } from '../../environments/environment';
import { PlaybackService } from '../now-playing/playback.service';
import { Observable, tap } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class PlaylistService {
  private readonly serviceUrl = environment.serviceUrl;

  // Your playlist array
  private playlist: Playlist = {
    name: '001 Dance',
    tracks: []
  };
  private playlists: Playlist[] = [];

  constructor(private readonly http: HttpClient, private readonly playbackService: PlaybackService) { }

  addToPlaylist(track: Track) {
    this.playlist.tracks.push(track);
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
    this.playbackService.playPlaylist(playlist).subscribe({ error: error => console.error('Playlist playback failed', error) });
  }

  playSingleTrack(track: Track) {
    this.playbackService.playTrack(track).subscribe({ error: error => console.error('Track playback failed', error) });
  }

  pausePlaylist() {
    this.playbackService.pause().subscribe({ error: error => console.error('Pause failed', error) });
  }

  stopPlaylist() {
    this.playbackService.stop().subscribe({ error: error => console.error('Stop failed', error) });
  }
  
  loadAll(): void {
    this.loadAll$()
    .subscribe({
      error: error => console.error('Error fetching playlists:', error)
    });
  }

  loadAll$(): Observable<Playlist[]> {
    return this.http.get<Playlist[]>(`${this.serviceUrl}/playlists`).pipe(
      tap(response => this.playlists = response)
    );
  }

  getPlaylists(): Playlist[] {
    return this.playlists;
  }

  savePlaylist(playlistName: string) {
    this.playlist.name = playlistName;

    this.http.post<Playlist>(`${this.serviceUrl}/save-playlist`, this.playlist)
      .subscribe({ error: error => console.error('Playlist save failed', error) });
  }
  
}
