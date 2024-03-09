import { NgModule } from '@angular/core';
import { ServerModule } from '@angular/platform-server';

import { AppModule } from './app.module';
import { ReleaseComponent } from './release/release.component';

@NgModule({
  imports: [
    AppModule,
    ServerModule,
  ],
  bootstrap: [ReleaseComponent],
})
export class AppServerModule {}
