// release.component.ts

import { Component, OnInit, HostListener } from '@angular/core';
import { ReleaseService } from './release.service';
import { PlaylistService } from '../playlist/playlist.service';
import { AiMetadata, Track } from '../dao/track';
import { map, startWith } from 'rxjs/operators';
import { Observable } from 'rxjs';
import { ChipColor } from '../app.module';
import { FormControl } from '@angular/forms';

@Component({
  selector: 'app-release',
  templateUrl: './release.component.html',
  styleUrls: ['./release.component.css']
})
export class ReleaseComponent implements OnInit {
  release: any;
  releases: any[] = [];
  currentSlideIndex: number = 0;
  currentCdIndex: number = 1;
  currentDeckNumber: number = 1;
  carouselButtonSelected: boolean = false;
  aiMetadata: AiMetadata | null = null;
  aiLoading: boolean = false;
  aiEnriching: boolean = false;
  aiError: string = '';

  availableColors: ChipColor[] = [
    {name: 'none', color: undefined},
    {name: 'Primary', color: 'primary'},
    {name: 'Accent', color: 'accent'},
    {name: 'Warn', color: 'warn'},
  ];

  myControl = new FormControl('');
  filteredOptions!: Observable<any[]>;

  constructor(private readonly releaseService: ReleaseService, private readonly playlistService: PlaylistService) {}

  @HostListener('window:keydown', ['$event'])
  handleKeyboardEvent(event: KeyboardEvent) {
    if (event.key === 'ArrowLeft') {
      this.prevSlide();
    } else if (event.key === 'ArrowRight') {
      this.nextSlide();
    }
  }

  prevSlide() {
    this.goToReleaseIndex(this.currentSlideIndex <= 0 ? this.releases.length - 1 : this.currentSlideIndex - 1);
  }

  nextSlide() {
    this.goToReleaseIndex(this.currentSlideIndex >= this.releases.length - 1 ? 0 : this.currentSlideIndex + 1);
  }

  releaseGoToSlide(release: any): void {
    const targetIndex = this.releases.findIndex(item => item.release_id === release.release_id);
    if (targetIndex < 0) {
      return;
    }

    this.currentSlideIndex = targetIndex;
    this.setCurrentRelease(this.releases[targetIndex]);
    this.hideCarousel();
  }

  goToReleaseIndex(index: number): void {
    if (!this.releases.length || index < 0 || index >= this.releases.length) {
      return;
    }
    this.currentSlideIndex = index;
    this.setCurrentRelease(this.releases[index]);
  }

  trackRelease(_index: number, release: any): number | string {
    return release?.release_id || release?.id || _index;
  }

  addToFavourites(release: any, track: any) {
    this.releaseService.addToFavourites(release, track).subscribe(
      response => {
        console.log('Track added to favourites successfully', response);
        track._score = 1;
        const updatedTrack = response?.tracklist?.find((item: any) => item.position === track.position);
        if (updatedTrack) {
          Object.assign(track, updatedTrack);
        }
      },
      error => {
        console.error('Error adding track to favourites', error);
        // Handle error here
      }
    );
  }

  // Use this method in your template to add to the playlist
  addTrackToPlaylist(release: any, track: any) {
    track["cd_position"] = release.cd_position;
    track["full_name"] = release.artists_sort + " - " + track.title;
    track["album_title"] = release.title;
    track["artwork_url"] = this.getPrimaryImageUrl(release);
    this.playlistService.addToPlaylist(track);
  }

  switchCarousel(): void {
    this.carouselButtonSelected = !this.carouselButtonSelected;
  }

  hideCarousel(): void {
    this.carouselButtonSelected = false;
  }

  getPlaylistSize() {
    return this.playlistService.getPlaylist().tracks.length;
  }

  playSingleTrack(release: any, track: Track) {
    track["deck_number"] = release.deck_number;
    track["cd_position"] = release.cd_position;
    track["artist"] = release.artists_sort;
    track["full_name"] = release.artists_sort + " - " + track.title;
    track["album_title"] = release.title;
    track["artwork_url"] = this.getPrimaryImageUrl(release);
    this.playlistService.playSingleTrack(track);
  }

  ngOnInit() {
    this.getReleases();
    this.filteredOptions = this.myControl.valueChanges.pipe(
      startWith(''),
      map(value => this._filter(value || '')),
    );
  }

  getReleases(): void {
    this.releaseService.getReleases()
      .subscribe(
        releases => this.processReleases(releases)
      );
  }

  processReleases(releases: any[]): void {
    releases.forEach((release:any, index) => {
      if (!release.images) {
        console.debug("Release Images are missing!");
        release.images = [];
      }

      // Add the deck number each track in release
      release.tracklist.forEach((track: Track) => {
        track.deck_number = release.deck_number;
        track.cd_position = release.cd_position;
        track.artist = release.artists_sort;
        track.full_name = release.artists_sort + " - " + track.title;
        track.album_title = release.title;
        track.artwork_url = this.getPrimaryImageUrl(release);
      });
    });

    this.releases = releases;
    this.currentSlideIndex = 0;
    this.setCurrentRelease(this.releases[0]);
  }

  // Helper function to get the primary image URL
  getPrimaryImageUrl(release: any): string {
    var primaryImage = release.images.find((image: { type: any; }) => image.type === 'primary');
    if (primaryImage == null) {
      primaryImage = release.images.find((image: { type: any; }) => image.type === 'secondary');
    }

    if (primaryImage != null) {
      return primaryImage.uri;
    } else {
      return "/assets/default.png";
    }
  }

  private setCurrentRelease(release: any): void {
    this.release = release;
    this.currentCdIndex = release?.cd_position || 1;
    this.currentDeckNumber = release?.deck_number || 1;
    this.loadAiForRelease(release);
  }

  loadAiForRelease(release: any): void {
    this.aiMetadata = release?.ai || null;
    this.aiError = '';
    if (!release?.release_id) {
      return;
    }

    this.aiLoading = true;
    this.releaseService.getReleaseAi(release.release_id).subscribe({
      next: metadata => {
        this.aiMetadata = metadata;
        release.ai = metadata;
        this.aiLoading = false;
      },
      error: error => {
        this.aiError = error?.error?.error || 'AI metadata unavailable';
        this.aiLoading = false;
      }
    });
  }

  enrichAi(force = false): void {
    if (!this.release?.release_id || this.aiEnriching) {
      return;
    }

    this.aiError = '';
    this.aiEnriching = true;
    this.releaseService.enrichRelease(this.release.release_id, force).subscribe({
      next: metadata => {
        this.aiMetadata = metadata;
        this.release.ai = metadata;
        this.aiEnriching = false;
      },
      error: error => {
        this.aiError = error?.error?.error || 'AI enrichment failed';
        this.aiEnriching = false;
      }
    });
  }

  aiScoreEntries(metadata: AiMetadata | null): Array<{ label: string; value: number }> {
    if (!metadata) {
      return [];
    }

    return [
      ['Energy', metadata.energy],
      ['Danceability', metadata.danceability],
      ['Euphoria', metadata.euphoria],
      ['Commercial', metadata.commercial],
      ['Club', metadata.club],
      ['Radio', metadata.radio],
      ['Nostalgia', metadata.nostalgia],
      ['Cheese', metadata.cheese]
    ].filter(([, value]) => value !== undefined && value !== null)
      .map(([label, value]) => ({ label: label as string, value: Number(value) }));
  }

  joinAiList(items: string[] | undefined): string {
    return (items || []).join(', ');
  }

  private _filter(value: string): any[] {
    const filterValue = value.toLowerCase();

    let filteredOptions = this.releases.filter((r: { title: string; artists_sort: string;  tracklist: any[]}) => 
        r.title.toLowerCase().includes(filterValue.toLowerCase()) ||
        r.artists_sort.toLowerCase().includes(filterValue.toLowerCase()) ||
        (r.tracklist && r.tracklist.some(track => 
          track.title.toLowerCase().includes(filterValue) ||
          (track.artists && track.artists.some((artist: { name: string; }) => artist.name.toLowerCase().includes(filterValue)))
      ))
    );
    
    return filteredOptions;
  }

  getTracksForDisc(release: any): any[] {
    // If there is only one disc, return the whole tracklist
    if (release.format_quantity === 1) {
        return release.tracklist;
    }

    // Extract the disc number from the title, e.g., "CD 2" -> 2
    let discNumber = 1;
    if (release.title.includes('(CD ')) {
      discNumber = parseInt(release.title.split('(CD ')[1]);
    }

    // Filter tracks that belong to the current disc
    return release.tracklist.filter((track: { position: { split: (arg0: string) => [any]; }; }) => {
        let [discId, ] = track.position.split('-');
        return parseInt(discId) === discNumber;
    });
}
}