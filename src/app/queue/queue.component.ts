import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subscription } from 'rxjs';
import { QueueState, Track } from '../dao/track';
import { PlaybackService } from '../now-playing/playback.service';
import { QueueService } from './queue.service';

@Component({
  selector: 'app-queue',
  standalone: true,
  imports: [CommonModule, DragDropModule, MatButtonModule, MatIconModule, MatTooltipModule],
  templateUrl: './queue.component.html',
  styleUrls: ['./queue.component.scss']
})
export class QueueComponent implements OnInit, OnDestroy {
  queueState: QueueState | null = null;
  private sub?: Subscription;

  constructor(
    private readonly queueService: QueueService,
    private readonly playbackService: PlaybackService
  ) {}

  ngOnInit(): void {
    this.sub = this.queueService.queue$.subscribe(state => this.queueState = state);
    this.queueService.refresh().subscribe();
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  get tracks(): Track[] {
    return this.queueState?.queue ?? [];
  }

  get currentIndex(): number {
    return this.queueState?.current_index ?? -1;
  }

  get shuffle(): boolean {
    return this.queueState?.shuffle ?? false;
  }

  get repeat(): string {
    return this.queueState?.repeat ?? 'off';
  }

  get upcomingCount(): number {
    return this.queueState?.queue_stats?.upcoming ?? 0;
  }

  get totalCount(): number {
    return this.queueState?.queue_stats?.total ?? 0;
  }

  trackName(track: Track | null): string {
    if (!track) return 'Nothing playing';
    return track.full_name || `${track.artist} – ${track.title}`;
  }

  trackSubtitle(track: Track): string {
    const parts: string[] = [];
    if (track.album_title) parts.push(track.album_title);
    if (track.position) parts.push(`Track ${track.position}`);
    if (track.duration) parts.push(track.duration);
    return parts.join(' · ');
  }

  isCurrent(index: number): boolean {
    return index === this.currentIndex;
  }

  playIndex(index: number): void {
    this.queueService.playIndex(index).subscribe();
  }

  removeTrack(index: number): void {
    this.queueService.remove(index).subscribe();
  }

  moveToTop(index: number): void {
    this.queueService.moveToTop(index).subscribe();
  }

  clearQueue(): void {
    this.queueService.clear().subscribe();
  }

  toggleShuffle(): void {
    this.queueService.setShuffle(!this.shuffle).subscribe();
  }

  cycleRepeat(): void {
    const modes: Array<'off' | 'one' | 'all'> = ['off', 'all', 'one'];
    const current = modes.indexOf(this.repeat as 'off' | 'one' | 'all');
    const next = modes[(current + 1) % modes.length];
    this.queueService.setRepeat(next).subscribe();
  }

  repeatIcon(): string {
    return this.repeat === 'one' ? 'repeat_one' : 'repeat';
  }

  repeatLabel(): string {
    const labels: Record<string, string> = { off: 'Repeat off', one: 'Repeat one', all: 'Repeat all' };
    return labels[this.repeat] ?? 'Repeat off';
  }

  onDrop(event: CdkDragDrop<Track[]>): void {
    if (event.previousIndex === event.currentIndex) return;
    this.queueService.move(event.previousIndex, event.currentIndex).subscribe();
  }

  formatDuration(track: Track): string {
    return track.duration || '—';
  }
}
