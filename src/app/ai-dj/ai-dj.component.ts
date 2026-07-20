import { Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { PlaylistService } from '../playlist/playlist.service';
import { AiTrackRecommendation, ChatContext, ChatResponse, PlaybackStatus, Track, VideoSyncState } from '../dao/track';
import { PlaybackService } from '../now-playing/playback.service';
import { AiDjChatMessage, AiDjService } from './ai-dj.service';

const NATIVE_VIDEO_CLOCK_COMPENSATION_SECONDS = -1;
const NATIVE_VIDEO_RATE_CORRECTION_THRESHOLD_SECONDS = 0.75;
const NATIVE_VIDEO_SEEK_CORRECTION_THRESHOLD_SECONDS = 1.25;
const NATIVE_VIDEO_MAX_RATE_CORRECTION = 0.015;

@Component({
  selector: 'app-ai-dj',
  templateUrl: './ai-dj.component.html',
  styleUrls: ['./ai-dj.component.scss']
})
export class AiDjComponent implements OnInit, OnDestroy {
  @ViewChild('nativeVideo') nativeVideo?: ElementRef<HTMLVideoElement>;

  readonly quickSuggestions = [
    'Play something similar',
    'More energetic',
    'More melodic',
    'More trance',
    'More house',
    'More Eurodance',
    'More Euro House',
    'More Dance-pop',
    'More rave-pop',
    'More hard trance',
    'More vocal trance',
    'More underground',
    'Night driving',
    'Workout',
    'Surprise me',
    'Hidden gem',
    'Forgotten classic',
    'Continue this vibe'
  ];

  context: ChatContext | null = null;
  messages: AiDjChatMessage[] = [];
  recommendations: AiTrackRecommendation[] = [];
  inputText = '';
  chatLoading = false;
  recommendationLoading = false;
  error = '';
  aiUsed = false;
  explainedRecommendation: AiTrackRecommendation | null = null;
  videoSync: VideoSyncState | null = null;
  nativeVideoUrl = '';
  videoLoading = false;
  videoError = '';
  useNativeVideoOffset = true;
  nativeVideoManualOffsetSeconds = 0;
  private playbackSubscription?: Subscription;
  private videoAssetId = '';
  private lastVideoSeek = 0;
  private lastPlaybackElapsed: number | null = null;
  private lastVideoPlaybackState = '';
  private lastVideoCommandAt = 0;
  private lastVideoSyncKey = '';
  private lastVideoSyncElapsed = 0;
  private lastVideoSyncRequestedAt = 0;
  private nativeVideoReady = false;
  private syncControlsNativeVideo = false;
  private programmaticVideoEventUntil = 0;
  private forceNextVideoSeek = false;
  private resetVideoOnNextStoppedStatus = false;

  constructor(
    private readonly aiDjService: AiDjService,
    private readonly playbackService: PlaybackService,
    private readonly playlistService: PlaylistService,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    const state = this.aiDjService.stateSnapshot();
    this.context = state.context;
    this.messages = state.messages;
    this.recommendations = state.recommendations;
    this.inputText = state.inputText;
    this.aiUsed = state.aiUsed;
    this.useNativeVideoOffset = state.useNativeVideoOffset;
    this.nativeVideoManualOffsetSeconds = state.nativeVideoManualOffsetSeconds;
    this.refreshContext();
    if (!this.recommendations.length) {
      this.loadCurrentRecommendations();
    }
    this.playbackSubscription = this.playbackService.status$.subscribe(status => {
      this.applyPlaybackStatus(status);
      const needsVideoRefresh = this.shouldRefreshVideoSync(status);
      if (needsVideoRefresh) {
        this.loadVideoSync();
      } else {
        this.syncVideoToPlaybackStatus(status);
      }
    });
  }

  ngOnDestroy(): void {
    this.playbackSubscription?.unsubscribe();
  }

  refreshContext(): void {
    this.aiDjService.context().subscribe({
      next: context => {
        this.context = context;
        this.persistState();
      },
      error: () => this.error = 'AI DJ context is unavailable'
    });
  }

  loadCurrentRecommendations(): void {
    this.recommendationLoading = true;
    this.aiDjService.recommendationsForCurrent(10).subscribe({
      next: response => this.applyResponse(response, false),
      error: () => {
        this.error = 'AI DJ recommendations are unavailable';
        this.recommendationLoading = false;
      }
    });
  }

  sendMessage(message = this.inputText): void {
    const trimmed = message.trim();
    if (!trimmed || this.chatLoading) {
      return;
    }

    this.chatLoading = true;
    this.error = '';
    this.messages = [...this.messages, { role: 'user', content: trimmed }];
    this.inputText = '';
    this.persistState();

    this.aiDjService.chat({
      message: trimmed,
      conversation: this.messages,
      recent_recommendations: this.recommendations
    }).subscribe({
      next: response => this.applyResponse(response, true),
      error: () => {
        this.error = 'AI DJ request failed';
        this.chatLoading = false;
      }
    });
  }

  useSuggestion(suggestion: string): void {
    this.sendMessage(suggestion);
  }

  persistDraft(): void {
    this.persistState();
  }

  playRecommendation(recommendation: AiTrackRecommendation): void {
    this.playbackService.playTrack(recommendation.track).subscribe({
      next: status => this.applyPlaybackStatus(status),
      error: () => this.error = 'Playback command failed'
    });
  }

  playCurrentTrack(): void {
    const playback = this.context?.now_playing;
    const currentTrack = playback?.current_track;
    if (!currentTrack) {
      return;
    }
    if (playback.playback_state === 'paused') {
      this.resume();
      return;
    }
    this.playbackService.playTrack(currentTrack).subscribe({
      next: status => this.applyPlaybackStatus(status),
      error: () => this.error = 'Playback command failed'
    });
  }

  pause(): void {
    this.playbackService.pause().subscribe({ next: status => this.applyPlaybackStatus(status), error: () => this.error = 'Playback command failed' });
  }

  resume(): void {
    this.playbackService.resume().subscribe({ next: status => this.applyPlaybackStatus(status), error: () => this.error = 'Playback command failed' });
  }

  setPlaybackStartDelayEnabled(enabled: boolean): void {
    this.playbackService.setStartDelayEnabled(enabled).subscribe({
      next: status => {
        this.applyPlaybackStatus(status);
        this.loadVideoSync(true);
      },
      error: () => this.error = 'Playback command failed'
    });
  }

  resyncHardware(): void {
    this.playbackService.resyncHardware().subscribe({
      next: status => this.applyPlaybackStatus(status),
      error: () => this.error = 'Playback command failed'
    });
  }

  enableContinuousStatus(): void {
    this.playbackService.setContinuousStatusEnabled(true).subscribe({
      next: status => this.applyPlaybackStatus(status),
      error: () => this.error = 'Playback command failed'
    });
  }

  stop(): void {
    this.resetVideoOnNextStoppedStatus = true;
    this.playbackService.stop().subscribe({ next: status => this.applyPlaybackStatus(status), error: () => this.error = 'Playback command failed' });
  }

  nextTrack(): void {
    this.playbackService.nextTrack().subscribe({ next: status => this.applyPlaybackStatus(status), error: () => this.error = 'Playback command failed' });
  }

  previousTrack(): void {
    this.playbackService.previousTrack().subscribe({ next: status => this.applyPlaybackStatus(status), error: () => this.error = 'Playback command failed' });
  }

  loadVideoSync(force = false): void {
    if (force && this.context?.now_playing) {
      this.rememberVideoSyncRequest(this.context.now_playing);
      this.forceNextVideoSeek = true;
    }
    this.videoLoading = !this.videoSync;
    this.aiDjService.videoSync().subscribe({
      next: sync => {
        this.videoSync = sync;
        this.videoLoading = false;
        this.videoError = '';
        const forceSeek = this.forceNextVideoSeek;
        this.forceNextVideoSeek = false;
        this.applyVideoSync(sync, forceSeek);
      },
      error: () => {
        this.videoLoading = false;
        this.videoError = 'No suitable local video found.';
      }
    });
  }

  downloadVideo(): void {
    this.videoLoading = true;
    this.aiDjService.downloadVideo().subscribe({
      next: sync => {
        this.videoSync = sync;
        this.videoLoading = false;
        this.videoError = '';
        this.applyVideoSync(sync);
      },
      error: error => {
        this.videoLoading = false;
        this.videoError = error?.error?.message || 'Video download failed.';
      }
    });
  }

  playNativeVideo(): void {
    const video = this.nativeVideo?.nativeElement;
    if (!video) {
      return;
    }
    this.syncControlsNativeVideo = false;
    video.muted = true;
    void video.play().catch(() => this.videoError = 'Native video autoplay was blocked.');
    this.lastVideoPlaybackState = 'playing';
  }

  onNativeVideoPlay(): void {
    if (Date.now() < this.programmaticVideoEventUntil) {
      return;
    }
    this.lastVideoPlaybackState = 'playing';
    if (!this.videoSync?.should_play) {
      this.syncControlsNativeVideo = false;
    }
  }

  onNativeVideoPause(): void {
    if (Date.now() < this.programmaticVideoEventUntil) {
      return;
    }
    this.lastVideoPlaybackState = 'paused';
    if (!this.videoSync?.should_play) {
      this.syncControlsNativeVideo = false;
    }
  }

  onNativeVideoReady(): void {
    const wasReady = this.nativeVideoReady;
    this.nativeVideoReady = true;
    if (this.videoSync && !wasReady) {
      this.syncNativeVideo(this.withNativeVideoClockCompensation(this.withNativeVideoOffsetPreference(this.videoSync), false), true);
    }
  }

  onNativeVideoError(): void {
    this.videoError = 'Native video file is unavailable or cannot be decoded by this browser.';
  }

  queueRecommendation(recommendation: AiTrackRecommendation): void {
    this.playlistService.addToPlaylist(recommendation.track);
  }

  openRelease(recommendation: AiTrackRecommendation): void {
    this.router.navigate(['/'], { queryParams: { release_id: recommendation.release.release_id } });
  }

  explain(recommendation: AiTrackRecommendation): void {
    this.explainedRecommendation = recommendation;
  }

  matchLabel(recommendation: AiTrackRecommendation): string {
    const confidence = recommendation.confidence || 0;
    if (confidence >= 92) {
      return '★★★★★ Perfect continuation';
    }
    if (confidence >= 80) {
      return '★★★★☆ Strong Match';
    }
    if (confidence >= 65) {
      return '★★★☆☆ Similar energy';
    }
    return '★★☆☆☆ Wildcard';
  }

  trackName(track: Track | null | undefined): string {
    if (!track) {
      return 'Nothing playing';
    }
    return track.full_name || `${track.artist || ''} ${track.title}`.trim() || track.title;
  }

  primaryImageUrl(): string {
    return this.context?.current_track?.artwork_url || '/assets/default.png';
  }

  recommendationImageUrl(recommendation: AiTrackRecommendation): string {
    const image = (recommendation.release.images || [])[0] as { uri?: string; primary_image?: string } | undefined;
    return recommendation.track.artwork_url || image?.primary_image || image?.uri || '/assets/default.png';
  }

  dnaText(values: string[] | undefined): string {
    return (values || []).join(', ');
  }

  formatTime(seconds: number | null | undefined): string {
    const safeSeconds = Math.max(0, Math.floor(seconds || 0));
    const minutes = Math.floor(safeSeconds / 60);
    const remainder = safeSeconds % 60;
    return `${minutes}:${remainder.toString().padStart(2, '0')}`;
  }

  hardwareStateLabel(playback: PlaybackStatus): string {
    if (playback.door_open) {
      return 'Door open';
    }
    if (playback.power_state === 'off') {
      return 'Powered off';
    }
    return (playback.mechanical_state || 'unknown').replace(/_/g, ' ');
  }

  setNativeVideoOffsetEnabled(enabled: boolean): void {
    if (this.useNativeVideoOffset === enabled) {
      return;
    }
    this.useNativeVideoOffset = enabled;
    this.persistState();
    this.saveNativeVideoOffsetPreference();
    if (this.videoSync?.video) {
      this.applyVideoSync(this.videoSync, true, false);
    }
  }

  setNativeVideoManualOffset(value: string | number | null): void {
    const parsed = Number(value);
    this.nativeVideoManualOffsetSeconds = Number.isFinite(parsed) ? parsed : 0;
    this.persistState();
    this.saveNativeVideoOffsetPreference();
    if (this.videoSync?.video) {
      this.applyVideoSync(this.videoSync, true, false);
    }
  }

  nativeVideoSeekSeconds(): number {
    return this.videoSync ? this.withNativeVideoOffsetPreference(this.videoSync).seek_seconds : 0;
  }

  nativeVideoTotalOffsetSeconds(): number {
    if (!this.videoSync?.video) {
      return this.nativeVideoManualOffsetSeconds;
    }
    return this.preferredNativeVideoOffsetSeconds(this.videoSync);
  }

  formatSignedSeconds(seconds: number | null | undefined): string {
    const safeSeconds = Number.isFinite(Number(seconds)) ? Number(seconds) : 0;
    let sign = '';
    if (safeSeconds > 0) {
      sign = '+';
    } else if (safeSeconds < 0) {
      sign = '-';
    }
    return `${sign}${this.formatTime(Math.abs(safeSeconds))}`;
  }

  private applyVideoSync(sync: VideoSyncState, forceSeek = false, applyPersistedOffset = true): void {
    if (applyPersistedOffset) {
      this.applyPersistedNativeVideoOffset(sync);
    }
    const youtubeId = sync.video?.youtube_id || '';
    const videoUrl = sync.video?.provider === 'local' ? this.aiDjService.mediaUrl(sync.video) : '';
    const videoId = videoUrl || youtubeId;
    if (!videoId || !videoUrl) {
      this.nativeVideoUrl = '';
      this.videoAssetId = '';
      if (sync.video && sync.video.provider !== 'local') {
        this.videoError = 'Native video file is not available for this track.';
      }
      return;
    }

    const videoChanged = videoId !== this.videoAssetId;
    const preferredSync = this.withNativeVideoOffsetPreference(sync);
    const nativeSync = this.withNativeVideoClockCompensation(preferredSync, !(forceSeek || videoChanged));
    if (videoChanged) {
      this.videoAssetId = videoId;
      this.nativeVideoUrl = videoUrl;
      this.lastVideoSeek = nativeSync.seek_seconds;
      this.lastPlaybackElapsed = this.context?.now_playing?.elapsed ?? nativeSync.seek_seconds;
      this.lastVideoPlaybackState = '';
      this.nativeVideoReady = false;
      this.syncControlsNativeVideo = sync.should_play;
      setTimeout(() => this.syncNativeVideo(nativeSync, true), 300);
      return;
    }

    this.syncNativeVideo(nativeSync, false, forceSeek);
  }

  private withNativeVideoClockCompensation(sync: VideoSyncState, includeClockCompensation = true): VideoSyncState {
    const compensation = includeClockCompensation ? NATIVE_VIDEO_CLOCK_COMPENSATION_SECONDS : 0;
    return {
      ...sync,
      seek_seconds: Math.max(0, sync.seek_seconds + compensation)
    };
  }

  private withNativeVideoOffsetPreference(sync: VideoSyncState): VideoSyncState {
    const detectedOffset = sync.video?.offset_seconds || 0;
    const preferredOffset = this.preferredNativeVideoOffsetSeconds(sync);
    const baseElapsed = this.context?.now_playing?.elapsed ?? sync.seek_seconds - detectedOffset;
    return {
      ...sync,
      seek_seconds: Math.max(0, Math.floor(baseElapsed + preferredOffset))
    };
  }

  private preferredNativeVideoOffsetSeconds(sync: VideoSyncState): number {
    const detectedOffset = this.useNativeVideoOffset ? this.detectedNativeVideoOffsetSeconds(sync) : 0;
    return detectedOffset + this.nativeVideoManualOffsetSeconds;
  }

  private detectedNativeVideoOffsetSeconds(sync: VideoSyncState): number {
    return sync.video?.detected_offset_seconds ?? sync.video?.offset_seconds ?? 0;
  }

  private applyPersistedNativeVideoOffset(sync: VideoSyncState): void {
    const video = sync.video;
    if (!video) {
      return;
    }
    if (typeof video.use_detected_offset === 'boolean') {
      this.useNativeVideoOffset = video.use_detected_offset;
    }
    if (typeof video.manual_offset_seconds === 'number') {
      this.nativeVideoManualOffsetSeconds = video.manual_offset_seconds;
    }
    this.persistState();
  }

  private saveNativeVideoOffsetPreference(): void {
    if (!this.videoSync?.video) {
      return;
    }
    this.aiDjService.saveVideoOffsetPreference(this.nativeVideoManualOffsetSeconds, this.useNativeVideoOffset).subscribe({
      next: sync => {
        this.videoSync = sync;
        this.applyVideoSync(sync, true);
      },
      error: () => this.error = 'Video offset preference could not be saved'
    });
  }

  private syncNativeVideo(sync: VideoSyncState, videoChanged: boolean, forceSeek = false): void {
    const video = this.nativeVideo?.nativeElement;
    if (!video || (!this.nativeVideoReady && !videoChanged)) {
      return;
    }

    const playbackElapsed = this.context?.now_playing?.elapsed ?? sync.seek_seconds;
    const driftSeconds = Math.abs(video.currentTime - sync.seek_seconds);
    const now = Date.now();
    const canSendTransportCommand = videoChanged || now - this.lastVideoCommandAt > 1200;
    const shouldLetUserPreview = !sync.should_play && !this.syncControlsNativeVideo;

    const shouldHardSeek = videoChanged || forceSeek || (sync.should_play && driftSeconds > NATIVE_VIDEO_SEEK_CORRECTION_THRESHOLD_SECONDS);
    if (shouldHardSeek) {
      this.programmaticVideoEventUntil = now + 1000;
      video.currentTime = Math.floor(sync.seek_seconds);
    }

    this.applyNativeVideoRateCorrection(video, sync, shouldHardSeek ? 0 : driftSeconds, shouldLetUserPreview);

    const nextPlaybackState = this.videoPlaybackState(sync);
    if (sync.should_play && this.lastVideoPlaybackState !== 'playing' && canSendTransportCommand) {
      video.muted = true;
      this.programmaticVideoEventUntil = now + 1000;
      void video.play().catch(() => this.videoError = 'Native video autoplay was blocked.');
      this.lastVideoPlaybackState = 'playing';
      this.lastVideoCommandAt = now;
      this.syncControlsNativeVideo = true;
    } else if (sync.should_pause && this.syncControlsNativeVideo && this.lastVideoPlaybackState !== 'paused' && canSendTransportCommand) {
      this.programmaticVideoEventUntil = now + 1000;
      video.pause();
      this.lastVideoPlaybackState = 'paused';
      this.lastVideoCommandAt = now;
      this.syncControlsNativeVideo = false;
    }

    this.lastVideoSeek = sync.seek_seconds;
    this.lastPlaybackElapsed = playbackElapsed;
    if (!sync.should_play && !sync.should_pause) {
      this.lastVideoPlaybackState = nextPlaybackState;
    }
  }

  private applyNativeVideoRateCorrection(video: HTMLVideoElement, sync: VideoSyncState, driftSeconds: number, shouldLetUserPreview: boolean): void {
    if (!sync.should_play || shouldLetUserPreview || driftSeconds < NATIVE_VIDEO_RATE_CORRECTION_THRESHOLD_SECONDS) {
      video.playbackRate = 1;
      return;
    }

    video.playbackRate = video.currentTime < sync.seek_seconds
      ? 1 + NATIVE_VIDEO_MAX_RATE_CORRECTION
      : 1 - NATIVE_VIDEO_MAX_RATE_CORRECTION;
  }

  private videoPlaybackState(sync: VideoSyncState): string {
    if (sync.should_play) {
      return 'playing';
    }
    if (sync.should_pause) {
      return 'paused';
    }
    return sync.playback_state;
  }

  private syncVideoToPlaybackStatus(status: PlaybackStatus): void {
    if (!this.videoSync?.video || !this.nativeVideoUrl) {
      return;
    }

    const offsetSeconds = this.preferredNativeVideoOffsetSeconds(this.videoSync);
    const playbackState = status.playback_state;
    const shouldResetVideoOnStop = playbackState === 'stopped' && (this.resetVideoOnNextStoppedStatus || this.videoSync.playback_state !== 'stopped');
    const sync: VideoSyncState = {
      ...this.videoSync,
      playback_state: playbackState,
      seek_seconds: Math.max(0, (status.elapsed || 0) + offsetSeconds),
      should_play: playbackState === 'playing',
      should_pause: ['paused', 'stopped', 'idle', 'preparing', 'error'].includes(playbackState)
    };

    if (playbackState === 'stopped') {
      this.resetVideoOnNextStoppedStatus = false;
    }
    this.videoSync = sync;
    this.syncNativeVideo(this.withNativeVideoClockCompensation(sync, !shouldResetVideoOnStop), false, shouldResetVideoOnStop);
  }

  private shouldRefreshVideoSync(status: PlaybackStatus): boolean {
    if (!status.current_track) {
      return !!this.videoSync?.video;
    }

    const syncKey = `${this.trackSyncKey(status.current_track)}:${status.playback_state}`;
    const elapsed = Math.floor(status.elapsed || 0);
    const now = Date.now();
    const stateChanged = syncKey !== this.lastVideoSyncKey;
    const drifted = status.playback_state === 'playing' && Math.abs(elapsed - this.lastVideoSyncElapsed) > 20;
    const cooldownPassed = now - this.lastVideoSyncRequestedAt > 15000;

    if (!this.lastVideoSyncKey || stateChanged || (drifted && cooldownPassed)) {
      this.lastVideoSyncKey = syncKey;
      this.lastVideoSyncElapsed = elapsed;
      this.lastVideoSyncRequestedAt = now;
      return true;
    }

    return false;
  }

  private rememberVideoSyncRequest(status: PlaybackStatus): void {
    this.lastVideoSyncKey = `${this.trackSyncKey(status.current_track)}:${status.playback_state}`;
    this.lastVideoSyncElapsed = Math.floor(status.elapsed || 0);
    this.lastVideoSyncRequestedAt = Date.now();
  }

  private trackSyncKey(track: Track | null): string {
    if (!track) {
      return 'no-track';
    }
    return [track.release_id || '', track.cd_position || '', track.artist || '', track.title || ''].join('|');
  }

  private applyResponse(response: ChatResponse, appendAssistant: boolean): void {
    this.context = response.context;
    this.recommendations = response.suggested_tracks || [];
    this.aiUsed = !!response.ai_used;
    if (appendAssistant) {
      this.messages = [...this.messages, {
        role: 'assistant',
        content: response.response,
        suggested_tracks: response.suggested_tracks || []
      }];
    }
    this.chatLoading = false;
    this.recommendationLoading = false;
    this.persistState();
  }

  private applyPlaybackStatus(status: PlaybackStatus): void {
    if (this.context) {
      this.context = {
        ...this.context,
        now_playing: status,
        current_track: status.current_track,
        current_playlist: status.current_playlist
      };
      this.persistState();
    } else {
      this.refreshContext();
    }
  }

  private persistState(): void {
    this.aiDjService.saveState({
      context: this.context,
      messages: this.messages,
      recommendations: this.recommendations,
      inputText: this.inputText,
      aiUsed: this.aiUsed,
      useNativeVideoOffset: this.useNativeVideoOffset,
      nativeVideoManualOffsetSeconds: this.nativeVideoManualOffsetSeconds
    });
  }
}