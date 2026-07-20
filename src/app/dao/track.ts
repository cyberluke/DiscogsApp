export interface Artist {
    name: string;
    anv: string;
    join: string;
    role: string;
    tracks: string;
    id: number;
    resource_url: string;
  }
  
  export interface Track {
    position: string;
    type_: string;
    artist: string;
    artists: Artist[];
    title: string;
    duration: string;
    cd_position: number;
    release_id?: number;
    full_name: string;
    deck_number: number;
    album_title?: string;
    artwork_url?: string;
  }

  export interface Playlist {
    name: string;
    tracks: Track[];
  }

  export type PlaybackStateName = 'idle' | 'playing' | 'paused' | 'stopped' | 'preparing' | 'error';

  export interface PlaybackStatus {
    current_track: Track | null;
    current_playlist: string | null;
    queue: Track[];
    upcoming: Track[];
    elapsed: number;
    duration: number;
    remaining: number;
    progress: number;
    current_deck: number | null;
    current_cd: number | null;
    playback_state: PlaybackStateName;
    last_update_timestamp: number;
    load_delay_seconds: number;
    load_delay_remaining: number;
    mechanical_state?: string;
    hardware_ready?: boolean;
    display_disc?: number | string | null;
    loaded_disc?: number | string | null;
    door_open?: boolean;
    power_state?: string;
    model?: unknown;
    player_status_raw?: unknown;
    last_hardware_event?: string | null;
    playback_start_delay_seconds: number;
    playback_start_delay_enabled: boolean;
    hardware_sync_state?: string;
    hardware_state_verified?: boolean;
    hardware_state_source?: string;
    error: string | null;
  }

  export interface PlaybackProgress {
    elapsed: number;
    duration: number;
    remaining: number;
    progress: number;
    playback_state: PlaybackStateName;
  }

  export interface PlaybackQueue {
    current_track: Track | null;
    queue: Track[];
    upcoming: Track[];
    current_playlist: string | null;
    playback_state: PlaybackStateName;
  }

  export type RuntimeEventType =
    | 'snapshot'
    | 'playback_started'
    | 'playback_stopped'
    | 'progress_tick'
    | 'queue_changed'
    | 'playlist_changed'
    | 'playback_paused'
    | 'playback_error';

  export interface RuntimeEvent {
    type: RuntimeEventType;
    payload: PlaybackStatus;
  }

  export interface RecommendationQuery {
    q?: string;
    artist?: string;
    album?: string;
    release?: string;
    genre?: string;
    style?: string;
    year?: string | number;
    label?: string;
    deck?: string | number;
    cd_position?: string | number;
    favourites?: boolean;
    limit?: number;
  }

  export interface RecommendationResult {
    id?: number;
    release_id?: number;
    title: string;
    artists_sort: string;
    year?: number;
    country?: string;
    genres: string[];
    styles: string[];
    labels: unknown[];
    deck_number: number;
    cd_position: number;
    images: unknown[];
    tracklist: Track[];
  }

  export interface RecommendationResponse {
    count: number;
    results: RecommendationResult[];
  }

  export interface AiMetadata {
    version: number;
    generated_at: string;
    scene: string;
    summary: string;
    energy?: number;
    danceability?: number;
    euphoria?: number;
    nostalgia?: number;
    commercial?: number;
    club?: number;
    radio?: number;
    cheese?: number;
    guilty_pleasure?: boolean;
    driving_music?: boolean;
    late_night?: boolean;
    festival?: boolean;
    mood?: string[];
    recommended_after?: string[];
    similar_artists?: string[];
    keywords?: string[];
  }

  export interface ChatCollectionStats {
    release_count: number;
    track_count: number;
    ai_enriched_release_count: number;
    top_labels: Array<{ name: string; count: number }>;
    top_countries: Array<{ name: string; count: number }>;
    top_years: Array<{ name: string; count: number }>;
  }

  export interface ChatContext {
    now_playing: PlaybackStatus;
    current_release: RecommendationResult | null;
    current_track: Track | null;
    current_playlist: string | null;
    saved_playlists?: Array<{ name: string; track_count: number }>;
    recent_history: Track[];
    collection: ChatCollectionStats;
  }

  export interface MusicDna {
    shared: string[];
    differs: string[];
  }

  export interface RecommendationAction {
    type: 'play' | 'queue_next' | 'replace_queue' | 'open_release' | 'explain';
    label: string;
  }

  export interface AiTrackRecommendation {
    track: Track;
    release: RecommendationResult;
    reason: string;
    confidence: number;
    musical_dna: MusicDna;
    actions: RecommendationAction[];
  }

  export interface ChatRequest {
    message: string;
    conversation?: Array<{ role: 'user' | 'assistant'; content: string; suggested_tracks?: AiTrackRecommendation[] }>;
    recent_recommendations?: AiTrackRecommendation[];
    limit?: number;
    playlist_size?: number;
  }

  export interface ChatResponse {
    response: string;
    suggested_tracks: AiTrackRecommendation[];
    actions: RecommendationAction[];
    context: ChatContext;
    ai_used?: boolean;
    playlist?: Playlist;
    playback?: PlaybackStatus;
    playlist_analysis?: unknown;
  }

  export type VideoProvider = 'local' | 'youtube' | 'kodi' | (string & {});
  export type VideoProviderId = number | string | null;

  export interface VideoAsset {
    video_id: string;
    provider?: VideoProvider;
    youtube_id?: string | null;
    provider_id?: VideoProviderId;
    title: string;
    channel: string;
    thumbnail?: string | null;
    duration?: number | string | null;
    embeddable?: boolean;
    playback_safe?: boolean;
    url?: string | null;
    confidence?: number | null;
    offset_seconds?: number;
    detected_offset_seconds?: number;
    manual_offset_seconds?: number;
    use_detected_offset?: boolean;
    effective_offset_seconds?: number;
    offset_source?: string;
    artist?: string;
    track?: string;
  }

  export interface VideoAcquisitionCandidate {
    provider: string;
    provider_id: string;
    title: string;
    channel: string;
    source_url?: string;
    artist?: string;
    track?: string;
    duration?: number | string | null;
    thumbnail?: string | null;
    confidence?: number | null;
  }

  export interface VideoSyncState {
    video: VideoAsset | null;
    candidate?: VideoAcquisitionCandidate | null;
    can_download?: boolean;
    message: string | null;
    playback_state: PlaybackStateName;
    seek_seconds: number;
    should_play: boolean;
    should_pause: boolean;
    source: string;
  }

  export type YouTubeVideo = VideoAsset;
  export type YouTubeSyncState = VideoSyncState;