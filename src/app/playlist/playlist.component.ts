// playlist.component.ts
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { PlaylistService } from '../playlist/playlist.service';
import { DragDropModule } from '@angular/cdk/drag-drop';
import {CdkDragDrop, CdkDropList, CdkDrag, moveItemInArray} from '@angular/cdk/drag-drop';
import { GridModule } from '@coreui/angular';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { Playlist, Track } from '../dao/track';


@Component({
  selector: 'app-playlist',
  templateUrl: './playlist.component.html',
  styleUrls: ['./playlist.component.css'],
  standalone: true,
  imports: [CdkDropList, CdkDrag, DragDropModule, FormsModule, CommonModule, MatButtonModule,
    MatIconModule, GridModule,
    MatListModule],
})
export class PlaylistComponent {
  playlistName: string = '';
  playlists: any = [];

  constructor(private http: HttpClient, private playlistService: PlaylistService) {
    this.playlistService.loadAll();
  }

  drop(event: CdkDragDrop<Track[]>): void {
    moveItemInArray(this.playlistService.getPlaylist().tracks, event.previousIndex, event.currentIndex);
  }

  addToPlaylist(track: Track) {
    this.playlistService.addToPlaylist(track);
  }

  removeFromPlaylist(index: number) {
    this.playlistService.removeAtIndex(index);
  }

  getPlaylist() {
    return this.playlistService.getPlaylist();
  }

  getPlaylists(): Playlist[] {
    return this.playlistService.getPlaylists();
  }

  savePlaylist() {
    this.playlistService.savePlaylist(this.playlistName);
  }

  editPlaylist(playlist: Playlist) {
    this.playlistService.setPlaylist(playlist);
  }

  playSingleTrack(track: Track) {
    this.playlistService.playSingleTrack(track);
  }

  playPlaylist(playlist: Playlist) {
    this.playlistService.playPlaylist(playlist);
  }

  
}
