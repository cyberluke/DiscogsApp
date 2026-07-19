// release.component.ts

import { Component, OnInit, HostListener, ViewChild } from '@angular/core';
import { ReleaseService } from './release.service';
import { PlaylistService } from '../playlist/playlist.service';
import { CarouselControlComponent } from '@coreui/angular';
import { AiMetadata, Track } from '../dao/track';
import { map, startWith, take } from 'rxjs/operators';
import { Observable, Subject } from 'rxjs';
import { ChipColor } from '../app.module';
import { FormControl } from '@angular/forms';

@Component({
  selector: 'app-release',
  templateUrl: './release.component.html',
  styleUrls: ['./release.component.css']
})
export class ReleaseComponent implements OnInit {
  @ViewChild('prevControl')
  prevControl!: CarouselControlComponent;
  @ViewChild('nextControl')
  nextControl!: CarouselControlComponent;
  release: any;
  releases: any[] = [];
  currentCdIndex: number = 1;
  currentDeckNumber: number = 1;
  private readonly indexUpdated = new Subject<void>();
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
    if (this.prevControl) {
      this.prevControl['play'](); // Using bracket notation to access the method
    }
  }

  nextSlide() {
    if (this.nextControl) {
      this.nextControl['play'](); // Using bracket notation to access the method
    }
  }

  async releaseGoToSlide(release: any): Promise<void> {
    if (release.cd_position == this.currentCdIndex && release.deck_number == this.currentDeckNumber) {
      this.hideCarousel();
      return;
    }
    let finalPosition = release;
    let difference = Math.abs(release.cd_position - this.currentCdIndex);

    if (finalPosition.deck_number > this.currentDeckNumber) {
      difference += 300 - this.currentDeckNumber + 1;
    } else if (finalPosition.deck_number < this.currentDeckNumber) {
      difference += 300 - this.currentDeckNumber + 1;
    }

    if (finalPosition.cd_position > this.currentCdIndex) {
      for (let i = 0; i < difference; i++) {
        let oldIndex = this.currentCdIndex;
        this.nextSlide();
        // Wait for the currentCdIndex to be updated
        let waitTime = 0;
        const maxWaitTime = 400; // Maximum wait time in milliseconds
        while (this.currentCdIndex === oldIndex && waitTime < maxWaitTime) {
          await this.delay(1); // Delay for a short period (10 ms)
          waitTime += 1;
        }

        // Break the loop if currentCdIndex didn't change within the maxWaitTime
        if (this.currentCdIndex === oldIndex) {
          console.error('Failed to update currentCdIndex after waiting');
          break;
        }
      }
    } else {
      for (let i = 0; i < difference; i++) {
        let oldIndex = this.currentCdIndex;
        this.prevSlide();
        // Wait for the currentCdIndex to be updated
        let waitTime = 0;
        const maxWaitTime = 500; // Maximum wait time in milliseconds
        while (this.currentCdIndex === oldIndex && waitTime < maxWaitTime) {
          await this.delay(1); // Delay for a short period (10 ms)
          waitTime += 1;
        }

        // Break the loop if currentCdIndex didn't change within the maxWaitTime
        if (this.currentCdIndex === oldIndex) {
          console.error('Failed to update currentCdIndex after waiting');
          break;
        }
      }
    }
    this.releaseGoToSlide(finalPosition);
  }

  async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private waitForIndexUpdate(): Promise<void> {
    return new Promise(resolve => {
      this.indexUpdated.pipe(take(1)).subscribe(() => resolve());
    });
  }

  addToFavourites(release: any, track: any) {
    this.releaseService.addToFavourites(release, track).subscribe(
      response => {
        console.log('Track added to favourites successfully', response);
        // Handle successful response here
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
    this.release = this.releases[0];
    this.loadAiForRelease(this.release);
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

  onItemChange($event: any): void {
    console.log('Carousel onItemChange', $event);
    var releaseIndex:number = $event;
    if (!releaseIndex) {
      releaseIndex = 0;
    }

    this.release = this.releases[releaseIndex];
    this.currentCdIndex = this.release.cd_position;
    this.currentDeckNumber = this.release.deck_number;
    this.loadAiForRelease(this.release);

    // Notify that the index has been updated
    this.indexUpdated.next();
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