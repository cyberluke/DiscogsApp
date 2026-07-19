import { Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { Router } from '@angular/router';
import { PlaylistService } from '../playlist/playlist.service';
import { AiTrackRecommendation, ChatContext, ChatResponse, Track } from '../dao/track';
import { AiDjService } from './ai-dj.service';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  suggested_tracks?: AiTrackRecommendation[];
}

@Component({
  selector: 'app-ai-dj',
  templateUrl: './ai-dj.component.html',
  styleUrls: ['./ai-dj.component.scss']
})
export class AiDjComponent implements OnInit {
  @ViewChild('chatInput') chatInput?: ElementRef<HTMLTextAreaElement>;

  readonly quickSuggestions = [
    'Play something similar',
    'More energetic',
    'More melodic',
    'More trance',
    'More house',
    'More Eurodance',
    'More underground',
    'Night driving',
    'Workout',
    'Surprise me',
    'Hidden gem',
    'Forgotten classic',
    'Continue this vibe'
  ];

  context: ChatContext | null = null;
  messages: ChatMessage[] = [];
  recommendations: AiTrackRecommendation[] = [];
  inputText = '';
  chatLoading = false;
  recommendationLoading = false;
  error = '';
  aiUsed = false;
  explainedRecommendation: AiTrackRecommendation | null = null;

  constructor(
    private readonly aiDjService: AiDjService,
    private readonly playlistService: PlaylistService,
    private readonly router: Router
  ) {}

  ngOnInit(): void {
    this.refreshContext();
    this.loadCurrentRecommendations();
  }

  refreshContext(): void {
    this.aiDjService.context().subscribe({
      next: context => this.context = context,
      error: () => this.error = 'AI DJ context is unavailable'
    });
  }

  loadCurrentRecommendations(): void {
    this.recommendationLoading = true;
    this.aiDjService.recommendationsForCurrent(6).subscribe({
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
    this.inputText = suggestion;
    setTimeout(() => this.chatInput?.nativeElement.focus());
  }

  playRecommendation(recommendation: AiTrackRecommendation): void {
    this.aiDjService.play(recommendation.track).subscribe({
      next: () => this.refreshContext(),
      error: () => this.error = 'Playback command failed'
    });
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

  trackName(track: Track | null | undefined): string {
    if (!track) {
      return 'Nothing playing';
    }
    return track.full_name || `${track.artist || ''} ${track.title}`.trim() || track.title;
  }

  primaryImageUrl(): string {
    return this.context?.current_track?.artwork_url || '/assets/default.png';
  }

  dnaText(values: string[] | undefined): string {
    return (values || []).join(', ');
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
  }
}