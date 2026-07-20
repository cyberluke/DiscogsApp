import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { BehaviorSubject } from 'rxjs';
import { NowPlayingComponent } from './now-playing.component';
import { PlaybackService } from './playback.service';
import { PlaybackStatus } from '../dao/track';
import { PlaylistService } from '../playlist/playlist.service';

describe('NowPlayingComponent', () => {
  let fixture: ComponentFixture<NowPlayingComponent>;
  let statusSubject: BehaviorSubject<PlaybackStatus>;

  const status: PlaybackStatus = {
    current_track: {
      title: 'Cowgirl',
      full_name: 'Underworld - Cowgirl',
      position: '2',
      duration: '5:21',
      artist: 'Underworld',
      artists: [],
      type_: 'track',
      cd_position: 10,
      deck_number: 1
      ,
      album_title: 'Dubnobasswithmyheadman',
      artwork_url: '/assets/default.png'
    },
    current_playlist: 'Dance',
    queue: [],
    upcoming: [],
    elapsed: 65,
    duration: 321,
    remaining: 256,
    progress: 20,
    current_deck: 1,
    current_cd: 10,
    playback_state: 'playing',
    last_update_timestamp: 1,
      load_delay_seconds: 0,
      load_delay_remaining: 0,
    playback_start_delay_seconds: 0,
    playback_start_delay_enabled: true,
    error: null
  };

  beforeEach(() => {
    statusSubject = new BehaviorSubject(status);
    TestBed.configureTestingModule({
      imports: [NowPlayingComponent, NoopAnimationsModule],
      providers: [
        {
          provide: PlaybackService,
          useValue: {
            status$: statusSubject.asObservable(),
            liveConnected$: statusSubject.asObservable(),
            playTrack: jasmine.createSpy('playTrack'),
            resume: jasmine.createSpy('resume'),
            pause: jasmine.createSpy('pause'),
            stop: jasmine.createSpy('stop'),
            nextTrack: jasmine.createSpy('nextTrack'),
            previousTrack: jasmine.createSpy('previousTrack'),
            setStartDelayEnabled: jasmine.createSpy('setStartDelayEnabled')
          }
        },
        {
          provide: PlaylistService,
          useValue: {
            addToPlaylist: jasmine.createSpy('addToPlaylist')
          }
        }
      ]
    });
    fixture = TestBed.createComponent(NowPlayingComponent);
    fixture.detectChanges();
  });

  it('renders the current playback status', () => {
    const text = fixture.nativeElement.textContent;

    expect(text).toContain('Underworld - Cowgirl');
    expect(text).toContain('Dubnobasswithmyheadman');
    expect(text).toContain('Dance');
    expect(text).toContain('Deck 1');
    expect(text).toContain('CD 10');
    expect(text).toContain('1:05');
  });

  it('renders runtime errors', () => {
    statusSubject.next({ ...status, playback_state: 'error', error: 'S-Link offline' });
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('S-Link offline');
  });
});