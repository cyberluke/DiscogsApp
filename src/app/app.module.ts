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
        RouterModule.forRoot([])
    ]
})
export class AppModule { }
