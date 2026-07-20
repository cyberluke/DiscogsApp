import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { Observable } from 'rxjs';
import { PlaylistService } from '../playlist/playlist.service';
import { PlaybackStatus, RecommendationResult, Track } from '../dao/track';
import { PlaybackService } from './playback.service';

@Component({
  selector: 'app-now-playing',
  standalone: true,
  imports: [CommonModule, FormsModule, MatButtonModule, MatCheckboxModule, MatFormFieldModule, MatIconModule, MatInputModule],
  templateUrl: './now-playing.component.html',
  styleUrls: ['./now-playing.component.scss']
})
export class NowPlayingComponent {
  status$: Observable<PlaybackStatus> = this.playbackService.status$;
  liveConnected$: Observable<boolean> = this.playbackService.liveConnected$;
  recommendationQuery = '';
  recommendationArtist = '';
  recommendationAlbum = '';
  recommendationGenre = '';
  recommendationStyle = '';
  recommendationYear: number | null = null;
  recommendationLabel = '';
  recommendationDeck: number | null = null;
  recommendationCd: number | null = null;
  favouritesOnly = false;
  recommendationResults: RecommendationResult[] = [];
  recommendationLoading = false;
  recommendationError = '';

  constructor(private readonly playbackService: PlaybackService, private readonly playlistService: PlaylistService) {}

  pause(): void {
    this.playbackService.pause().subscribe();
  }

  resume(): void {
    this.playbackService.resume().subscribe();
  }

  play(status: PlaybackStatus): void {
    if (!status.current_track) {
      return;
    }
    const command = status.playback_state === 'paused'
      ? this.playbackService.resume()
      : this.playbackService.playTrack(status.current_track);
    command.subscribe();
  }

  setPlaybackStartDelayEnabled(enabled: boolean): void {
    this.playbackService.setStartDelayEnabled(enabled).subscribe();
  }

  resyncHardware(): void {
    this.playbackService.resyncHardware().subscribe();
  }

  enableContinuousStatus(): void {
    this.playbackService.setContinuousStatusEnabled(true).subscribe();
  }

  hardwareStateLabel(status: PlaybackStatus): string {
    if (status.door_open) {
      return 'Door open';
    }
    if (status.power_state === 'off') {
      return 'Powered off';
    }
    return (status.mechanical_state || 'unknown').replace(/_/g, ' ');
  }

  hardwareStateClass(status: PlaybackStatus): string {
    return (status.mechanical_state || 'unknown').replace(/_/g, '-');
  }

  stop(): void {
    this.playbackService.stop().subscribe();
  }

  nextTrack(): void {
    this.playbackService.nextTrack().subscribe();
  }

  previousTrack(): void {
    this.playbackService.previousTrack().subscribe();
  }

  searchRecommendations(): void {
    this.recommendationLoading = true;
    this.recommendationError = '';
    this.playbackService.recommendations({
      q: this.recommendationQuery,
      artist: this.recommendationArtist,
      album: this.recommendationAlbum,
      genre: this.recommendationGenre,
      style: this.recommendationStyle,
      year: this.recommendationYear || undefined,
      label: this.recommendationLabel,
      deck: this.recommendationDeck || undefined,
      cd_position: this.recommendationCd || undefined,
      favourites: this.favouritesOnly || undefined,
      limit: 12
    }).subscribe({
      next: response => {
        this.recommendationResults = response.results;
        this.recommendationLoading = false;
      },
      error: () => {
        this.recommendationError = 'Recommendations unavailable';
        this.recommendationLoading = false;
      }
    });
  }

  playRecommendedTrack(release: RecommendationResult, track: Track): void {
    this.playbackService.playTrack(this.trackWithReleaseMetadata(release, track)).subscribe();
  }

  addRecommendedTrack(release: RecommendationResult, track: Track): void {
    this.playlistService.addToPlaylist(this.trackWithReleaseMetadata(release, track));
  }

  primaryImageUrl(release: RecommendationResult): string {
    const images = (release.images || []) as Array<{ type?: string; uri?: string; primary_image?: string }>;
    const image = images.find(item => item.type === 'primary') || images.find(item => item.type === 'secondary') || images[0];
    return image?.primary_image || image?.uri || '/assets/default.png';
  }

  trackName(track: Track | null): string {
    if (!track) {
      return 'Nothing playing';
    }

    return track.full_name || `${track.artist || ''} ${track.title}`.trim() || track.title;
  }

  formatTime(seconds: number): string {
    const safeSeconds = Math.max(0, Math.floor(seconds || 0));
    const minutes = Math.floor(safeSeconds / 60);
    const remainder = safeSeconds % 60;
    return `${minutes}:${remainder.toString().padStart(2, '0')}`;
  }

  private trackWithReleaseMetadata(release: RecommendationResult, track: Track): Track {
    const artist = release.artists_sort === 'Various' && track.artists?.length ? track.artists[0].name : release.artists_sort;
    return {
      ...track,
      artist,
      deck_number: release.deck_number,
      cd_position: release.cd_position,
      full_name: `${artist} - ${track.title}`,
      album_title: release.title,
      artwork_url: track.artwork_url || this.primaryImageUrl(release)
    };
  }
}