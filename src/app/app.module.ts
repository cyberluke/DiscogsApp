import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { FormsModule } from '@angular/forms';
import { ReleaseComponent } from './release/release.component';
import { HttpClientModule } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { DragDropModule } from '@angular/cdk/drag-drop';
import { PlaylistComponent } from "./playlist/playlist.component";
import { CarouselModule, GridModule } from '@coreui/angular';
import { ListGroupModule, AccordionModule, SharedModule, BadgeComponent } from '@coreui/angular';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { RouterModule } from '@angular/router';
import { MatGridListModule } from '@angular/material/grid-list';
import { MatTooltipModule } from '@angular/material/tooltip';
import {ThemePalette} from '@angular/material/core';
import {MatChipsModule} from '@angular/material/chips';
import {FormControl, ReactiveFormsModule} from '@angular/forms';
import {Observable} from 'rxjs';
import {map, startWith} from 'rxjs/operators';
import {AsyncPipe} from '@angular/common';
import {MatAutocompleteModule} from '@angular/material/autocomplete';
import {MatInputModule} from '@angular/material/input';
import {MatFormFieldModule} from '@angular/material/form-field';

export interface ChipColor {
    name: string;
    color: ThemePalette;
  }

@NgModule({
    declarations: [
        ReleaseComponent
    ],
    providers: [],
    bootstrap: [ReleaseComponent],
    imports: [
        BrowserModule,
        HttpClientModule,
        NgbModule,
        FormsModule,
        NoopAnimationsModule,
        DragDropModule,
        CommonModule,
        PlaylistComponent,
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
        MatAutocompleteModule,
        ReactiveFormsModule,
        AsyncPipe,
        RouterModule.forRoot([])
    ]
})
export class AppModule { }
