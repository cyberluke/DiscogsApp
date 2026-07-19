import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { PlaybackService } from './playback.service';
import { environment } from '../../environments/environment';
import { PlaybackStatus, Track } from '../dao/track';

describe('PlaybackService', () => {
  let service: PlaybackService;
  let httpMock: HttpTestingController;

  const status: PlaybackStatus = {
    current_track: null,
    current_playlist: null,
    queue: [],
    upcoming: [],
    elapsed: 0,
    duration: 0,
    remaining: 0,
    progress: 0,
    current_deck: null,
    current_cd: null,
    playback_state: 'idle',
    last_update_timestamp: 0,
    load_delay_seconds: 0,
    load_delay_remaining: 0,
    error: null
  };

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule]
    });
    service = TestBed.inject(PlaybackService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    flushStatusRequests();
    service.ngOnDestroy();
    httpMock.verify();
  });

  it('plays playlists through the runtime endpoint and updates status', () => {
    service.playPlaylist({ name: 'Mix', tracks: [] }).subscribe(response => {
      expect(response.current_playlist).toBe('Mix');
    });

    httpMock.expectOne(`${environment.serviceUrl}/playlist/play`).flush({ ...status, current_playlist: 'Mix', playback_state: 'playing' });
  });

  it('plays tracks through the runtime endpoint', () => {
    const track = { title: 'Song', position: '1' } as Track;

    service.playTrack(track).subscribe(response => {
      expect(response.current_track?.title).toBe('Song');
    });

    httpMock.expectOne(`${environment.serviceUrl}/track/play`).flush({ ...status, current_track: track, playback_state: 'playing' });
  });

  it('resumes playback through the runtime endpoint', () => {
    service.resume().subscribe(response => {
      expect(response.playback_state).toBe('playing');
    });

    httpMock.expectOne(`${environment.serviceUrl}/playlist/resume`).flush({ ...status, playback_state: 'playing' });
  });

  it('skips to next and previous tracks through runtime endpoints', () => {
    service.nextTrack().subscribe(response => {
      expect(response.current_track?.title).toBe('Next');
    });
    service.previousTrack().subscribe(response => {
      expect(response.current_track?.title).toBe('Previous');
    });

    httpMock.expectOne(`${environment.serviceUrl}/playlist/next`).flush({ ...status, current_track: { title: 'Next' } as Track });
    httpMock.expectOne(`${environment.serviceUrl}/playlist/previous`).flush({ ...status, current_track: { title: 'Previous' } as Track });
  });

  it('queries recommendations with filter params', () => {
    service.recommendations({ artist: 'Underworld', limit: 5 }).subscribe(response => {
      expect(response.count).toBe(1);
    });

    const request = httpMock.expectOne(req => req.url === `${environment.serviceUrl}/recommendations`);
    expect(request.request.params.get('artist')).toBe('Underworld');
    expect(request.request.params.get('limit')).toBe('5');
    request.flush({ count: 1, results: [] });
  });

  function flushStatusRequests(): void {
    httpMock.match(`${environment.serviceUrl}/playback/status`).forEach(request => request.flush(status));
  }
});