// playlist.service.ts

import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class PlaylistService {
  // Your playlist array
  private playlist:any = [];

  constructor() { }

  addToPlaylist(track: any) {
    this.playlist.push(track);
    console.log(this.playlist);
    // Additional logic to handle the playlist
  }

  removeAtIndex(index: number) {
    this.playlist.splice(index, 1);
  }

  getPlaylist() {
    return this.playlist;
  }
}
