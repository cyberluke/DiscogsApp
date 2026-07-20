import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { ReleaseComponent } from './release/release.component';
import { HttpClientModule } from '@angular/common/http';
import { AsyncPipe, CommonModule } from '@angular/common';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { DragDropModule } from '@angular/cdk/drag-drop';
import { PlaylistComponent } from "./playlist/playlist.component";
import { AccordionModule, BadgeComponent, CarouselModule, GridModule, ListGroupModule, SharedModule } from '@coreui/angular';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { RouterModule } from '@angular/router';
import { MatGridListModule } from '@angular/material/grid-list';
import { MatTooltipModule } from '@angular/material/tooltip';
import {ThemePalette} from '@angular/material/core';
import {MatChipsModule} from '@angular/material/chips';
import {MatAutocompleteModule} from '@angular/material/autocomplete';
import {MatInputModule} from '@angular/material/input';
import {MatFormFieldModule} from '@angular/material/form-field';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { IonicModule } from '@ionic/angular';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { NowPlayingComponent } from './now-playing/now-playing.component';
import { AppComponent } from './app.component';
import { AiDjComponent } from './ai-dj/ai-dj.component';

export interface ChipColor {
    name: string;
    color: ThemePalette;
  }

@NgModule({
    declarations: [
      AppComponent,
        ReleaseComponent,
        AiDjComponent
    ],
    providers: [
    provideAnimationsAsync()
  ],
    bootstrap: [AppComponent],
    imports: [
        BrowserModule,
        HttpClientModule,
        NgbModule,
        FormsModule,
        NoopAnimationsModule,
        DragDropModule,
        CommonModule,
        PlaylistComponent,
        NowPlayingComponent,
        CarouselModule,
        GridModule,
        MatButtonModule,
        MatIconModule,
        MatListModule,
        AccordionModule,
        SharedModule,
        ListGroupModule,
        BadgeComponent,
        MatGridListModule,
        MatTooltipModule,
        MatChipsModule,
        MatFormFieldModule,
        MatInputModule,
        MatCheckboxModule,
        MatAutocompleteModule,
        ReactiveFormsModule,
        AsyncPipe,
        RouterModule.forRoot([
          { path: '', component: ReleaseComponent },
          { path: 'now-playing', component: NowPlayingComponent },
          { path: 'ai-dj', component: AiDjComponent }
        ]),
        IonicModule.forRoot({})
    ]
})
export class AppModule { }
