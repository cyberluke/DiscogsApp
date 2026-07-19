# DiscogsApp Runtime Modernization v2 Plan

Modernize DiscogsApp into a deterministic, offline-first music controller by moving playback ownership into a Flask Playback Runtime, adding a scheduler that advances queues from local duration metadata, streaming live state to Angular via WebSocket, and adding a local-only recommendation engine backed by startup indexes. Existing Library and Playlist views stay functional while new REST endpoints and a Now Playing dashboard are added.

## Steps

1. Backend package split and app wiring
   - Create backend packages under `server/api/`, `server/playback/`, `server/recommendation/`, `server/sony/`, and `server/websocket/`.
   - Keep `server/app.py` as the Flask composition root during the first pass: load config, initialize indexes/runtime/event hub, register routes, and retain legacy endpoints while delegating logic out.
   - Move S-Link formatting and transport currently represented by `slinkSend`, `slinkPlaylist`, and `slinkTrack` into `server/sony/slink.py` without changing command encoding.

2. Local data repository and startup indexes
   - Add a local repository abstraction for `discogs_data_all.json`, `playlists.json`, `video_offsets.json`, and `downloaded_images/`.
   - Build startup indexes in `server/recommendation/index_builder.py` for artist, album, genre, style, year, label, deck, and CD position.
   - Normalize index keys case-insensitively and preserve original release/track objects for API responses.
   - Keep Discogs API usage isolated to the existing manual import flow; no playback, recommendation, queue, or status endpoint should call Discogs online.

3. Playback Runtime state model
   - Implement `server/playback/state.py` with in-memory state fields: current track, current playlist, queue, elapsed, duration, remaining, current deck, current CD, playback state, and last update timestamp.
   - Define explicit states such as `idle`, `playing`, `paused`, `stopped`, `preparing`, and `error`.
   - Implement `server/playback/queue.py` to own queue mutation, current index advancement, playlist replacement, single-track play, stop, and soft pause.
   - Playback Runtime becomes the only backend owner of playback state; Angular services only read or request commands.

4. Deterministic scheduler
   - Implement `server/playback/scheduler.py` as a backend timer loop/thread owned by the runtime.
   - On track start, parse duration from local JSON metadata, compute elapsed/remaining/progress from monotonic time, and schedule next-track preparation before the current track ends.
   - Send S-Link `PLAY` through `server/sony/slink.py` before the current track finishes, then advance queue state deterministically.
   - Do not depend on Angular events or frontend timers for queue advancement.
   - Treat `POST /playlist/pause` as a soft scheduler pause: stop automatic advancement and expose paused state, without assuming a physical CD pause command.

5. Event hub and WebSocket live updates
   - Add `server/websocket/events.py` as an internal event publisher for playback started, stopped, progress tick, queue changed, playlist changed, paused, and error events.
   - Add Flask WebSocket support using a project-appropriate dependency, most likely Flask-SocketIO or a lightweight WebSocket-compatible extension after checking dependency fit.
   - Broadcast runtime snapshots on state transitions and periodic progress ticks.
   - Keep REST status endpoints authoritative so clients can recover after reconnect.

6. Stable REST API layer
   - Add route modules under `server/api/` for playback, queue, playlists, tracks, and recommendations.
   - Implement `GET /playback/status`, `GET /playback/progress`, `GET /queue`, `GET /recommendations`, `POST /playlist/play`, `POST /playlist/stop`, `POST /playlist/pause`, and `POST /track/play`.
   - Keep existing endpoints `/playlist`, `/track`, `/playlists`, `/save-playlist`, `/releases`, and `/favourite` as compatibility wrappers at first, delegating to the new services where applicable.
   - Return typed, stable JSON responses that future AI clients can consume without knowing Angular internals.

7. Recommendation Engine
   - Implement `server/recommendation/engine.py` using only local indexes and playlist/favourite data.
   - Support searches/filters by artist, genres, styles, year, labels, release/album, deck/CD position, and favourites.
   - Keep results instant by using in-memory indexes; avoid scanning the full JSON file per request after startup.
   - Include track/release identifiers and enough metadata for frontend display and future REST API consumers.

8. Angular typed playback client
   - Add TypeScript interfaces for playback status, progress, queue items, recommendation query/results, and runtime events in or near `src/app/dao/track.ts`.
   - Add a playback service under `src/app/now-playing/` that calls REST endpoints and subscribes to backend WebSocket events.
   - Update `src/app/playlist/playlist.service.ts` so `playPlaylist` uses `POST /playlist/play`, `playSingleTrack` uses `POST /track/play`, and stop/pause commands call the new runtime API.
   - Keep existing service methods as wrappers to avoid breaking `ReleaseComponent` and `PlaylistComponent` immediately.

9. Now Playing page
   - Add `src/app/now-playing/now-playing.component.ts/html/scss` and route/module wiring in `src/app/app.module.ts`.
   - Display artwork, artist, title, album, deck, CD position, track position, progress bar, elapsed, remaining, upcoming queue, and playback state.
   - Backend computes elapsed, remaining, and progress percent; Angular only renders the latest snapshot.
   - Preserve existing Library and Playlist views; add navigation without replacing the current bootstrap flow until routing is intentionally broadened.

10. Legacy compatibility and cleanup
    - Keep manual import and image cache endpoints working with existing Postman workflow.
    - Ensure `process_webhook` remains useful for external hardware/Kodi status but does not become the source of playlist advancement.
    - Move only playback/recommendation/S-Link runtime logic out of `server/app.py`; leave unrelated import/Kodi code for later refactors unless needed for wiring.

## Relevant Files

- `server/app.py` - current Flask monolith and composition root; existing routes at `/releases`, `/playlists`, `/save-playlist`, `/playlist`, `/track`; current symbols `slinkSend`, `slinkPlaylist`, `slinkTrack`, and `process_webhook` to delegate.
- `server/requirements.txt` - add WebSocket dependency if needed.
- `server/discogs_data_all.json` - offline metadata source for startup indexes and durations.
- `server/playlists.json` - existing playlist persistence; remains source for saved playlists.
- `server/downloaded_images/` - existing local artwork cache.
- `src/app/dao/track.ts` - existing `Artist`, `Track`, and `Playlist` interfaces; extend with runtime API interfaces.
- `src/app/playlist/playlist.service.ts` - current playback command client; update to call new runtime endpoints while preserving method names.
- `src/app/playlist/playlist.component.ts` - existing playlist UI; keep behavior, optionally add pause/stop controls if desired.
- `src/app/release/release.component.ts` - current library UI and single-track play integration; should continue to work through service wrappers.
- `src/app/release/release.service.ts` - current local release/favourite API client; should remain runtime-offline.
- `src/app/app.module.ts` - current bootstrap and empty router config; add Now Playing route/imports.
- `src/environments/environment.ts` - base service URL for REST and WebSocket URL derivation.

## Verification

1. Backend unit tests for duration parsing, queue advancement, soft pause behavior, and S-Link command formatting for deck/CD positions including >100 and >200.
2. Backend integration tests for `GET /playback/status`, `GET /playback/progress`, `GET /queue`, `GET /recommendations`, `POST /playlist/play`, `POST /playlist/stop`, `POST /playlist/pause`, and `POST /track/play` using local fixture metadata only.
3. Startup test verifies indexes build from local JSON and recommendation requests do not call Discogs API.
4. Scheduler test with shortened fixture durations verifies automatic next-track advancement without frontend events.
5. WebSocket test verifies events are published for playback start, progress ticks, queue change, playlist change, pause, stop, and reconnect recovery via REST status.
6. Angular tests for playback service REST calls, WebSocket event handling, and Now Playing component rendering of progress/queue/state.
7. Manual offline verification: disconnect Internet, start Flask and Angular, load library/playlists, play playlist, observe queue auto-advance and Now Playing live updates.
8. Regression check: existing `/releases`, `/playlists`, `/save-playlist`, `/playlist`, `/track`, `/favourite`, image cache, and manual import workflow still behave as expected.

## Decisions

- Transport: WebSocket live updates.
- Runtime persistence: in-memory only; runtime resets on Flask restart.
- Pause: soft scheduler pause only; no physical CD pause opcode assumed.
- Offline-first boundary: Discogs API remains manual import only, never runtime playback/recommendation/status.
- Architecture boundary: Playback Runtime owns state; Angular renders state and sends commands.
- Excluded from this phase: Soul Platform, Conversation Runtime, MCP, Tool Calls, CyberLuke integration, LLM recommendations, SQLite migration, broad app redesign, and full Kodi refactor.

## Further Considerations

1. WebSocket library choice should be confirmed during implementation by checking compatibility with the current Flask/gevent setup and Angular client needs.
2. Because runtime state is in-memory, browser reconnect can recover from Flask state, but Flask restart intentionally returns to idle.
3. The scheduler lead time for sending the next S-Link PLAY command should be configurable after hardware testing, with a conservative default such as 2-5 seconds before track end.
