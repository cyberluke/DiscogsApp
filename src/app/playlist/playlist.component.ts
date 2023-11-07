// playlist.component.ts

import { Component } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { PlaylistService } from '../playlist/playlist.service';

@Component({
  selector: 'app-playlist',
  templateUrl: './playlist.component.html',
  styleUrls: ['./playlist.component.css']
})
export class PlaylistComponent {
  playlistName: string = '';

  constructor(private http: HttpClient, private playlistService: PlaylistService) { }

  addToPlaylist(track: any) {
    this.playlistService.addToPlaylist(track);
  }

  removeFromPlaylist(index: number) {
    this.playlistService.removeAtIndex(index);
  }

  getPlaylist() {
    return this.playlistService.getPlaylist();
  }

  savePlaylist() {
    const playlistData = {
      name: this.playlistName,
      tracks: this.playlistService.getPlaylist()
    };
    this.http.post('http://localhost:5000/playlist', playlistData)
      .subscribe(response => {
        console.log(response);
        // Handle response here
      });
  }
}
