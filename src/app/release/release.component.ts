// release.component.ts

import { Component, OnInit, HostListener, ViewChild } from '@angular/core';
import { ReleaseService } from './release.service';
import { PlaylistService } from '../playlist/playlist.service';
import { ImageService } from '../image.service';
import { CarouselControlComponent } from '@coreui/angular';
import { Track } from '../dao/track';

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
  
  // Use this method in your template to add to the playlist
  addTrackToPlaylist(release: any, track: any) {
    track["cd_position"] = release.cd_position;
    track["full_name"] = release.artists_sort + " - " + track.title;
    this.playlistService.addToPlaylist(track);
  }

  getPlaylistSize() {
    return this.playlistService.getPlaylist().tracks.length;
  }

  playSingleTrack(track: Track) {
    this.playlistService.playSingleTrack(track);
  }

  ngOnInit() {
    this.getReleases();
  }

  getReleases(): void {
    this.releaseService.getReleases()
      .subscribe(
        releases => this.processReleases(releases)
      );
  }

  processReleases(releases: any[]): void {
    releases.forEach((release:any, index) => {
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
    if (!releaseIndex) return;

    this.release = this.releases[releaseIndex];
  }
}