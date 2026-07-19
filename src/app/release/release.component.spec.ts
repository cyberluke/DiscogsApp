import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { AccordionModule, BadgeComponent, CarouselModule, GridModule, ListGroupModule, SharedModule } from '@coreui/angular';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { ReactiveFormsModule } from '@angular/forms';
import { MatAutocompleteModule } from '@angular/material/autocomplete';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatGridListModule } from '@angular/material/grid-list';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatListModule } from '@angular/material/list';
import { MatTooltipModule } from '@angular/material/tooltip';
import { IonicModule } from '@ionic/angular';

import { ReleaseComponent } from './release.component';
import { ReleaseService } from './release.service';
import { PlaylistService } from '../playlist/playlist.service';
import { ImageService } from '../image.service';
import { PlaylistComponent } from '../playlist/playlist.component';
import { NowPlayingComponent } from '../now-playing/now-playing.component';

describe('ReleaseComponent', () => {
  let component: ReleaseComponent;
  let fixture: ComponentFixture<ReleaseComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [ReleaseComponent],
      imports: [
        HttpClientTestingModule,
        RouterTestingModule,
        ReactiveFormsModule,
        NoopAnimationsModule,
        IonicModule.forRoot({}),
        AccordionModule,
        BadgeComponent,
        CarouselModule,
        GridModule,
        ListGroupModule,
        SharedModule,
        MatAutocompleteModule,
        MatButtonModule,
        MatChipsModule,
        MatFormFieldModule,
        MatGridListModule,
        MatIconModule,
        MatInputModule,
        MatListModule,
        MatTooltipModule,
        PlaylistComponent,
        NowPlayingComponent
      ],
      providers: [
        {
          provide: ReleaseService,
          useValue: {
            getReleases: () => of([]),
            getReleaseAi: () => of(null),
            enrichRelease: () => of({ scene: 'Euro House', summary: 'Cached analysis' }),
            addToFavourites: () => of({})
          }
        },
        {
          provide: PlaylistService,
          useValue: {
            loadAll: jasmine.createSpy('loadAll'),
            addToPlaylist: jasmine.createSpy('addToPlaylist'),
            removeAtIndex: jasmine.createSpy('removeAtIndex'),
            savePlaylist: jasmine.createSpy('savePlaylist'),
            setPlaylist: jasmine.createSpy('setPlaylist'),
            playSingleTrack: jasmine.createSpy('playSingleTrack'),
            playPlaylist: jasmine.createSpy('playPlaylist'),
            pausePlaylist: jasmine.createSpy('pausePlaylist'),
            stopPlaylist: jasmine.createSpy('stopPlaylist'),
            getPlaylist: () => ({ name: 'Mix', tracks: [] }),
            getPlaylists: () => []
          }
        },
        {
          provide: ImageService,
          useValue: {
            downloadImage: () => of({ url: '/assets/default.png' })
          }
        }
      ]
    });
    fixture = TestBed.createComponent(ReleaseComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
