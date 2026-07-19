import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

import { PlaylistComponent } from './playlist.component';
import { PlaylistService } from './playlist.service';

describe('PlaylistComponent', () => {
  let component: PlaylistComponent;
  let fixture: ComponentFixture<PlaylistComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [PlaylistComponent, HttpClientTestingModule, NoopAnimationsModule],
      providers: [
        {
          provide: PlaylistService,
          useValue: {
            loadAll: jasmine.createSpy('loadAll'),
            getPlaylist: () => ({ name: 'Mix', tracks: [] }),
            getPlaylists: () => [],
            addToPlaylist: jasmine.createSpy('addToPlaylist'),
            removeAtIndex: jasmine.createSpy('removeAtIndex'),
            savePlaylist: jasmine.createSpy('savePlaylist'),
            setPlaylist: jasmine.createSpy('setPlaylist'),
            playSingleTrack: jasmine.createSpy('playSingleTrack'),
            playPlaylist: jasmine.createSpy('playPlaylist'),
            pausePlaylist: jasmine.createSpy('pausePlaylist'),
            stopPlaylist: jasmine.createSpy('stopPlaylist')
          }
        }
      ]
    });
    fixture = TestBed.createComponent(PlaylistComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
