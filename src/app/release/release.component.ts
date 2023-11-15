// release.component.ts

import { Component, OnInit, HostListener, ViewChild, EventEmitter } from '@angular/core';
import { ReleaseService } from './release.service';
import { PlaylistService } from '../playlist/playlist.service';
import { ImageService } from '../image.service';
import { CarouselControlComponent } from '@coreui/angular';
import { Track } from '../dao/track';
import { first, map, startWith } from 'rxjs/operators';
import { Observable, Subject } from 'rxjs';
import { take } from 'rxjs/operators';
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
  private indexUpdated = new Subject<void>();
  carouselButtonSelected: boolean = false;

  availableColors: ChipColor[] = [
    {name: 'none', color: undefined},
    {name: 'Primary', color: 'primary'},
    {name: 'Accent', color: 'accent'},
    {name: 'Warn', color: 'warn'},
  ];

  myControl = new FormControl('');
  options: string[] = ['One', 'Two', 'Three'];
  filteredOptions!: Observable<string[]>;

  constructor(private releaseService: ReleaseService, private playlistService: PlaylistService,
    private imageService: ImageService) {}

  @HostListener('window:keydown', ['$event'])
  handleKeyboardEvent(event: KeyboardEvent) {
    if (event.key === 'ArrowLeft') {
      this.prevSlide();
    } else if (event.key === 'ArrowRight') {
      this.nextSlide();
    }
  }

  prevSlide() {
    this.prevControl.play();
  }

  nextSlide() {
    this.nextControl.play();
  }

  async releaseGoToSlide(release: any): Promise<void> {
    if (release.cd_position == this.currentCdIndex) {
      this.hideCarousel();
      return;
    }
    let finalPosition = release;
    const difference = Math.abs(release.cd_position - this.currentCdIndex);

    if (finalPosition.cd_position > this.currentCdIndex) {
      for (let i = 0; i < difference; i++) {
        let oldIndex = this.currentCdIndex;
        this.nextSlide();
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



  // Use this method in your template to add to the playlist
  addTrackToPlaylist(release: any, track: any) {
    track["cd_position"] = release.cd_position;
    track["full_name"] = release.artists_sort + " - " + track.title;
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
    track["cd_position"] = release.cd_position;
    track["full_name"] = release.artists_sort + " - " + track.title;
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
        release.images[primaryImageIndex] = {};
        release.images[primaryImageIndex].primary_image = "/assets/default.png";
        return;
      }
      var primaryImageIndex = release.images.findIndex((image: { type: string; }) => image.type === 'primary');
      if (primaryImageIndex == -1) {
        primaryImageIndex = release.images.findIndex((image: { type: string; }) => image.type === 'secondary');
      }
      if (primaryImageIndex !== -1) {
        release.images[primaryImageIndex].primary_image = "/assets/default.png";
        const primaryImage = release.images[primaryImageIndex];

        var sanitized = (release.artists_sort + "-" + release.title).replace(/[\\.,'`"/\\:*?<>| ]+/g, '');
        sanitized = sanitized.split(' ').map((word: string) => word.charAt(0).toUpperCase() + word.slice(1)).join('');

        this.imageService.downloadImage(primaryImage.uri, sanitized).subscribe(image => {
          release.images[primaryImageIndex].uri = image.url;
          release.images[primaryImageIndex].primary_image = this.getPrimaryImageUrl(release);
        }, error => {
          console.error('Error downloading the image:', error);
        });
      }
    });

    this.releases = releases;
    this.release = this.releases[0];
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

    // Notify that the index has been updated
    this.indexUpdated.next();
  }

  private _filter(value: string): string[] {
    const filterValue = value.toLowerCase();

    return this.release.filter((r: { title: string; }) => r.title.toLowerCase().includes(filterValue));
  }
}