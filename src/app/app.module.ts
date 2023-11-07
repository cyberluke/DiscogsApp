import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { NgbModule } from '@ng-bootstrap/ng-bootstrap';
import { FormsModule } from '@angular/forms';
import { ReleaseComponent } from './release/release.component';
import { HttpClientModule } from '@angular/common/http';
import { PlaylistComponent } from './playlist/playlist.component';

@NgModule({
  declarations: [
    ReleaseComponent,
    PlaylistComponent
  ],
  imports: [
    BrowserModule,
    HttpClientModule,
    NgbModule,
    FormsModule 
  ],
  providers: [],
  bootstrap: [ReleaseComponent]
})
export class AppModule { }
