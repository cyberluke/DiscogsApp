"""Background CD Audio Capture Service.

Orchestrates S-Link commands, webhook events, and SPDIF recording to
digitize the CD collection. Designed to run as a long-lived background
worker inside the Flask server, controllable via REST API.
"""

import json
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from server.services.capture.audio import AudioCapture, discover_rme_spdif
from server.services.capture.decode import (
    audio_track_count,
    decode_webhook_disc,
    decode_webhook_track,
)
from server.services.capture.state import CaptureState
from server.services.capture.webhook import WebhookReceiver, DEFAULT_WEBHOOK_PORT
from server.sony.slink import SLinkClient

LOGGER = logging.getLogger(__name__)

# Timing constants
DISC_LOAD_TIMEOUT = 45       # seconds to wait for a disc to start playing
TRACK_TIMEOUT = 900          # 15 min safety net per track
INTER_DISC_GAP = 3           # seconds to pause between discs
MAIN_BACKEND_WEBHOOK_PORT = 5000

# Service states
STATE_IDLE = "idle"
STATE_RUNNING = "running"
STATE_PAUSED = "paused"
STATE_STOPPING = "stopping"


class CaptureService:
    """Manages the background CD audio capture pipeline.

    Thread-safe: all public methods can be called from any thread.
    The actual capture work runs on a dedicated daemon thread.
    """

    def __init__(
        self,
        slink_client: SLinkClient,
        output_dir: str = r"D:\DiscogsAudioCapture",
        state_path: str | None = None,
        webhook_port: int = DEFAULT_WEBHOOK_PORT,
    ):
        self._slink = slink_client
        self._output_dir = output_dir
        self._state_path = state_path or str(Path(output_dir) / "capture_state.json")
        self._webhook_port = webhook_port

        # Runtime state
        self._lock = threading.Lock()
        self._service_state = STATE_IDLE
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()  # set = running, clear = paused
        self._pause_event.set()

        # Progress tracking
        self._current_release: dict | None = None
        self._current_track: int | None = None
        self._current_filename: str | None = None
        self._current_deck: int | None = None
        self._session_started_at: float | None = None
        self._releases_completed: int = 0
        self._releases_failed: int = 0
        self._total_pending: int = 0
        self._log_buffer: deque[str] = deque(maxlen=200)

        # Components (created on start)
        self._audio: AudioCapture | None = None
        self._webhook: WebhookReceiver | None = None
        self._capture_state: CaptureState | None = None

        # State-change listeners (e.g. the visualization audio engine, which
        # must reselect shared vs dedicated SPDIF input when capture toggles).
        self._state_listeners: list = []

    # ===================================================================
    # Public API – thread-safe
    # ===================================================================

    @property
    def audio(self) -> AudioCapture | None:
        """The active ``AudioCapture`` while a capture session is running.

        Used by the visualization engine to tap the SPDIF stream in
        shared mode (no second audio device opened). Returns ``None`` when
        capture is idle so the engine falls back to a dedicated stream.
        """
        with self._lock:
            if self._service_state in (STATE_RUNNING, STATE_PAUSED):
                return self._audio
            return None

    @property
    def state(self) -> str:
        with self._lock:
            return self._service_state

    def add_state_listener(self, listener) -> None:
        """Register ``listener(new_state)`` called on every state transition."""
        with self._lock:
            if listener not in self._state_listeners:
                self._state_listeners.append(listener)

    def _notify_state(self, new_state: str) -> None:
        with self._lock:
            listeners = list(self._state_listeners)
        for listener in listeners:
            try:
                listener(new_state)
            except Exception:  # noqa: BLE001 - listeners are best-effort
                LOGGER.debug("Capture state listener failed", exc_info=True)

    def start(self, deck: int | None = None, release_id: int | None = None, limit: int | None = None) -> dict:
        """Start the capture worker. Returns immediately."""
        with self._lock:
            if self._service_state in (STATE_RUNNING, STATE_PAUSED):
                return {"error": "Capture already active", "state": self._service_state}
            self._service_state = STATE_RUNNING
            self._stop_event.clear()
            self._pause_event.set()
            self._releases_completed = 0
            self._releases_failed = 0
            self._session_started_at = time.monotonic()

        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            args=(deck, release_id, limit),
            daemon=True,
            name="capture-worker",
        )
        self._worker_thread.start()
        self._log("Capture session started")
        return {"state": STATE_RUNNING}

    def stop(self) -> dict:
        """Request graceful stop."""
        with self._lock:
            if self._service_state == STATE_IDLE:
                return {"error": "Not running", "state": STATE_IDLE}
            self._service_state = STATE_STOPPING
        self._stop_event.set()
        self._pause_event.set()  # unblock if paused
        self._log("Stop requested")
        return {"state": STATE_STOPPING}

    def record_current(self, playback_runtime) -> dict:
        """Record the currently playing track and continue on track changes.

        Saves into the same {release_id}/tracks/{NN}.wav structure as batch
        recording and marks tracks in CaptureState so batch skips them.

        Args:
            playback_runtime: PlaybackRuntime instance to get current track info
        """
        with self._lock:
            if self._service_state != STATE_IDLE:
                return {"error": "Capture already active", "state": self._service_state}

            status = playback_runtime.status()
            current_track = status.get("current_track")
            if not current_track:
                return {"error": "No track currently playing", "state": STATE_IDLE}

            if not isinstance(current_track, dict):
                return {"error": "Cannot identify current track", "state": STATE_IDLE}

            release_id = current_track.get("release_id") or current_track.get("id")
            if not release_id:
                return {"error": "Current track has no release_id – cannot save to release folder", "state": STATE_IDLE}

            self._service_state = STATE_RUNNING
            self._stop_event.clear()
            self._pause_event.set()
            self._session_started_at = time.monotonic()
            self._current_deck = status.get("current_deck")

        self._worker_thread = threading.Thread(
            target=self._record_current_worker,
            args=(playback_runtime,),
            daemon=True,
            name="capture-single-track",
        )
        self._worker_thread.start()
        self._log("Single-track recording started (continuous, splits on track change)")
        return {"state": STATE_RUNNING}

    def _record_current_worker(self, playback_runtime) -> None:
        """Worker thread for single-track recording."""
        try:
            self._run_single_track_capture(playback_runtime)
        except Exception as exc:
            LOGGER.error("Single-track capture crashed: %s", exc, exc_info=True)
            self._log(f"FATAL: {exc}")
        finally:
            self._cleanup()
            with self._lock:
                self._service_state = STATE_IDLE
            self._notify_state(STATE_IDLE)

    @staticmethod
    def _track_identity(track) -> str:
        """Build a stable string key for a track so we can detect changes
        by value rather than object identity."""
        if track is None:
            return ""
        if isinstance(track, dict):
            # Prefer a unique id; fall back to title+artist
            rid = track.get("release_id") or track.get("id") or ""
            pos = track.get("position") or track.get("track_number") or ""
            title = track.get("title", "")
            artist = track.get("artist", "") or track.get("artists_sort", "")
            return f"{rid}|{pos}|{artist}|{title}"
        return str(track)

    def _run_single_track_capture(self, playback_runtime) -> None:
        """Record continuously, saving into {release_id}/tracks/{NN}.wav.

        Splits into a new WAV on every track change. Marks each track in
        CaptureState so batch recording skips already-captured tracks.
        Stops when the user stops or playback stops/idles.
        """
        # Discover hardware
        self._log("Discovering RME SPDIF input...")
        device_id = discover_rme_spdif()
        self._log(f"RME SPDIF found at device index {device_id}")

        # Start webhook receiver
        self._webhook = WebhookReceiver(port=self._webhook_port)
        self._webhook.start()
        try:
            self._slink.configure_webhook_target(port=self._webhook_port, path="/webhook")
            self._log(f"ESP32 webhook redirected to port {self._webhook_port}")
        except Exception as exc:
            self._log(f"ERROR: Cannot configure ESP32 webhook: {exc}")
            raise

        # Start audio stream
        self._audio = AudioCapture(device_id)
        self._audio.start()
        # Let the visualization engine tap this stream (shared mode).
        self._notify_state(STATE_RUNNING)

        # Initialize capture state
        self._capture_state = CaptureState(self._state_path)

        def _track_position(track: dict) -> int:
            """Extract 1-based track position from a track dict."""
            pos = track.get("position") or track.get("track_number")
            if pos is None:
                return 0
            try:
                return int(str(pos).strip())
            except (ValueError, TypeError):
                return 0

        def _release_dir_for(track: dict) -> Path:
            """Get the release directory for a track."""
            rid = track.get("release_id") or track.get("id") or 0
            return Path(self._output_dir) / str(rid)

        def _ensure_metadata(release_dir: Path, track: dict) -> None:
            """Write metadata.json if it doesn't exist yet."""
            meta_path = release_dir / "metadata.json"
            if meta_path.exists():
                return
            release_dir.mkdir(parents=True, exist_ok=True)
            # Try to load full release data from Discogs DB for richer metadata
            releases = self._load_releases(None, track.get("release_id"))
            if releases:
                release = releases[0]
                with open(meta_path, "w", encoding="utf-8") as fh:
                    json.dump({
                        "release_id": release.get("release_id"),
                        "title": release.get("title"),
                        "artist": release.get("artists_sort"),
                        "deck_number": release.get("deck_number"),
                        "cd_position": release.get("cd_position"),
                        "tracklist": release.get("tracklist", []),
                    }, fh, indent=2, ensure_ascii=False)
            else:
                with open(meta_path, "w", encoding="utf-8") as fh:
                    json.dump({
                        "release_id": track.get("release_id"),
                        "title": track.get("release_title", ""),
                        "artist": track.get("artist") or track.get("artists_sort", ""),
                        "tracklist": [],
                    }, fh, indent=2, ensure_ascii=False)

        def _open_wav_for_track(track: dict) -> Path:
            """Open a WAV file for a track in the release folder."""
            release_dir = _release_dir_for(track)
            tracks_dir = release_dir / "tracks"
            tracks_dir.mkdir(parents=True, exist_ok=True)
            _ensure_metadata(release_dir, track)

            pos = _track_position(track)
            if pos > 0:
                wav_path = tracks_dir / f"{pos:02d}.wav"
            else:
                # Fallback: use a timestamp-based name if position unknown
                ts = datetime.now().strftime("%H%M%S")
                title = track.get("title", "Unknown")
                safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:40]
                wav_path = tracks_dir / f"{ts} - {safe_title}.wav"

            self._audio.open_track(wav_path)
            with self._lock:
                self._current_filename = str(wav_path)
                self._current_track = pos or None
            return wav_path

        def _mark_track_done(track: dict) -> None:
            """Mark a track as captured in CaptureState."""
            rid = track.get("release_id") or track.get("id")
            pos = _track_position(track)
            if not rid or pos <= 0:
                return
            # Get expected track count from Discogs DB
            releases = self._load_releases(None, rid)
            expected = audio_track_count(releases[0]) if releases else 0
            self._capture_state.mark_track_captured(rid, pos, expected)

        # Open the first file
        current_status = playback_runtime.status()
        current_track = current_status.get("current_track")
        if not isinstance(current_track, dict):
            self._log("ERROR: Cannot identify current track")
            return

        current_key = self._track_identity(current_track)
        wav_path = _open_wav_for_track(current_track)
        track_title = current_track.get("title", "Unknown")
        track_artist = current_track.get("artist", "") or current_track.get("artists_sort", "Unknown")
        self._log(f"▶ Recording: {track_artist} – {track_title}")
        self._log(f"  Output: {wav_path}")

        tracks_captured = 0
        # Generous overall deadline (8 hours) – real exit is via stop/playback-state
        deadline = time.monotonic() + 8 * 3600

        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                self._log("Stop requested by user")
                break

            current_status = playback_runtime.status()
            playback_state = current_status.get("playback_state")

            if playback_state in ("stopped", "idle"):
                self._log("Playback stopped – ending recording")
                break

            # Detect track change by value, not by object identity
            new_track = current_status.get("current_track")
            new_key = self._track_identity(new_track)

            if new_key and new_key != current_key:
                # Close the finished track (read duration before closing)
                dur = self._audio.current_duration
                self._audio.close_track()
                _mark_track_done(current_track)
                tracks_captured += 1
                self._log(f"■ Track done ({dur:.1f}s)")

                # Open the next file
                if isinstance(new_track, dict):
                    current_track = new_track
                    current_key = new_key
                    wav_path = _open_wav_for_track(new_track)
                    track_title = new_track.get("title", "Unknown")
                    track_artist = new_track.get("artist", "") or new_track.get("artists_sort", "Unknown")
                    self._log(f"▶ New track: {track_artist} – {track_title}")
                    self._log(f"  Output: {wav_path}")
                else:
                    self._log("WARNING: New track is not a dict – stopping")
                    break

            time.sleep(0.5)

        # Close the final track
        dur = self._audio.current_duration
        self._audio.close_track()
        _mark_track_done(current_track)
        tracks_captured += 1
        self._log(f"■ Recording session complete – {tracks_captured} track(s) captured")

    def pause(self) -> dict:
        """Pause capture (finishes current track, then waits)."""
        with self._lock:
            if self._service_state != STATE_RUNNING:
                return {"error": "Not running", "state": self._service_state}
            self._service_state = STATE_PAUSED
        self._pause_event.clear()
        self._log("Paused")
        return {"state": STATE_PAUSED}

    def resume(self) -> dict:
        """Resume from pause."""
        with self._lock:
            if self._service_state != STATE_PAUSED:
                return {"error": "Not paused", "state": self._service_state}
            self._service_state = STATE_RUNNING
        self._pause_event.set()
        self._log("Resumed")
        return {"state": STATE_RUNNING}

    def status(self) -> dict:
        """Full status snapshot for the API."""
        with self._lock:
            elapsed = (time.monotonic() - self._session_started_at) if self._session_started_at else 0
            state_summary = self._capture_state.summary() if self._capture_state else {}
            return {
                "state": self._service_state,
                "current_deck": self._current_deck,
                "current_release": self._release_summary(self._current_release),
                "current_track": self._current_track,
                "current_filename": self._current_filename,
                "elapsed_seconds": round(elapsed, 1),
                "releases_completed": self._releases_completed,
                "releases_failed": self._releases_failed,
                "total_pending": self._total_pending,
                "state_summary": state_summary,
                "has_unfinished": self._capture_state.has_unfinished() if self._capture_state else False,
            }

    def progress(self) -> dict:
        """Lightweight progress for polling."""
        with self._lock:
            elapsed = (time.monotonic() - self._session_started_at) if self._session_started_at else 0
            total = self._total_pending or 1
            done = self._releases_completed + self._releases_failed
            pct = round((done / total) * 100, 1) if total else 0
            # Estimate remaining based on average time per release
            avg_per_release = elapsed / max(done, 1)
            remaining = avg_per_release * (total - done) if done > 0 else 0
            return {
                "state": self._service_state,
                "percent": pct,
                "done": done,
                "total": total,
                "elapsed_seconds": round(elapsed, 1),
                "estimated_remaining_seconds": round(remaining, 1),
            }

    def current(self) -> dict:
        """What is being captured right now."""
        with self._lock:
            return {
                "state": self._service_state,
                "deck": self._current_deck,
                "release": self._release_summary(self._current_release),
                "track": self._current_track,
                "filename": self._current_filename,
                "recording": self._audio.is_recording if self._audio else False,
                "track_duration": round(self._audio.current_duration, 1) if self._audio else 0,
            }

    def log(self, lines: int = 50) -> list[str]:
        """Return the last N log lines."""
        with self._lock:
            return list(self._log_buffer)[-lines:]

    # ===================================================================
    # Worker loop – runs on dedicated thread
    # ===================================================================

    def _worker_loop(self, deck: int | None, release_id: int | None, limit: int | None) -> None:
        try:
            self._run_capture(deck, release_id, limit)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Capture worker crashed: %s", exc, exc_info=True)
            self._log(f"FATAL: {exc}")
        finally:
            self._cleanup()
            with self._lock:
                self._service_state = STATE_IDLE
            self._notify_state(STATE_IDLE)

    def _run_capture(self, deck: int | None, release_id: int | None, limit: int | None) -> None:
        # -- discover hardware -------------------------------------------
        self._log("Discovering RME SPDIF input...")
        device_id = discover_rme_spdif()
        self._log(f"RME SPDIF found at device index {device_id}")

        # -- load releases -----------------------------------------------
        releases = self._load_releases(deck, release_id)
        self._capture_state = CaptureState(self._state_path)
        pending = [r for r in releases if not self._capture_state.is_complete(r["release_id"])]
        if limit:
            pending = pending[:limit]

        with self._lock:
            self._total_pending = len(pending)
        self._log(f"Releases: total={len(releases)} pending={len(pending)}")

        if not pending:
            self._log("Nothing to capture – all releases complete.")
            return

        # -- start webhook receiver & redirect ESP32 ---------------------
        self._webhook = WebhookReceiver(port=self._webhook_port)
        self._webhook.start()
        try:
            self._slink.configure_webhook_target(port=self._webhook_port, path="/webhook")
            self._log(f"ESP32 webhook redirected to port {self._webhook_port}")
        except Exception as exc:  # noqa: BLE001
            self._log(f"ERROR: Cannot configure ESP32 webhook: {exc}")
            raise

        # -- start audio stream ------------------------------------------
        self._audio = AudioCapture(device_id)
        self._audio.start()
        # Let the visualization engine tap this stream (shared mode).
        self._notify_state(STATE_RUNNING)

        # -- capture loop ------------------------------------------------
        for idx, release in enumerate(pending):
            if self._stop_event.is_set():
                self._log("Stopping – user requested stop")
                break

            # Wait if paused
            self._pause_event.wait()
            if self._stop_event.is_set():
                break

            with self._lock:
                self._current_release = release
                self._current_deck = release.get("deck_number")

            try:
                ok = self._capture_release(release)
                with self._lock:
                    if ok:
                        self._releases_completed += 1
                    else:
                        self._releases_failed += 1
            except Exception as exc:  # noqa: BLE001
                LOGGER.error("Error capturing release %s: %s", release.get("release_id"), exc, exc_info=True)
                self._log(f"ERROR on release {release.get('release_id')}: {exc}")
                self._capture_state.mark_error(release["release_id"], str(exc))
                with self._lock:
                    self._releases_failed += 1
                try:
                    self._slink.send_stop(release.get("deck_number", 1))
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(2)

            # Gap between discs
            if idx < len(pending) - 1 and not self._stop_event.is_set():
                time.sleep(INTER_DISC_GAP)

        self._log(f"Session finished: completed={self._releases_completed} failed={self._releases_failed}")

    def _capture_release(self, release: dict) -> bool:
        """Capture all tracks of a single release. Returns True on success."""
        release_id: int = release["release_id"]
        deck: int = release["deck_number"]
        cd_pos: int = release["cd_position"]
        artist: str = release.get("artists_sort", "Unknown Artist")
        title: str = release.get("title", "Unknown")
        expected: int = audio_track_count(release)

        self._log(f"--- {artist} – {title} (deck={deck} cd={cd_pos} tracks={expected}) ---")

        # Prepare output directory
        release_dir = Path(self._output_dir) / str(release_id)
        tracks_dir = release_dir / "tracks"
        tracks_dir.mkdir(parents=True, exist_ok=True)

        meta_path = release_dir / "metadata.json"
        if not meta_path.exists():
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump({
                    "release_id": release_id,
                    "title": title,
                    "artist": artist,
                    "deck_number": deck,
                    "cd_position": cd_pos,
                    "tracklist": release.get("tracklist", []),
                }, fh, indent=2, ensure_ascii=False)

        # Resume support
        start_track = self._capture_state.last_track(release_id) + 1
        if start_track > 1:
            self._log(f"  Resuming from track {start_track}")

        # Check which tracks were already captured (e.g. by single-track mode)
        already_captured = self._capture_state.captured_tracks(release_id)
        if already_captured:
            self._log(f"  Already captured: {sorted(already_captured)}")

        # Flush stale events
        self._webhook.drain()

        # Send play command
        self._slink.send_track({
            "deck_number": deck,
            "cd_position": cd_pos,
            "position": str(start_track),
        })

        # Wait for first PLAY event
        current_track: int | None = None
        deadline = time.monotonic() + DISC_LOAD_TIMEOUT

        while time.monotonic() < deadline:
            if self._stop_event.is_set():
                return False
            event = self._webhook.wait_for_event(timeout=1.0)
            if event is None:
                continue
            status = event.get("status", "")
            if status == "PLAY":
                track_num = decode_webhook_track(event)
                if track_num is not None:
                    current_track = track_num
                    break
            elif status in ("STOP", "EJECT"):
                self._log(f"  Received {status} during disc load")
                self._capture_state.mark_error(release_id, f"Received {status} during disc load")
                return False

        if current_track is None:
            self._log(f"  Timeout waiting for disc {cd_pos} to load")
            self._capture_state.mark_error(release_id, "Timeout waiting for disc load")
            try:
                self._slink.send_stop(deck)
            except Exception:  # noqa: BLE001
                pass
            return False

        # Begin recording
        wav_path = tracks_dir / f"{current_track:02d}.wav"

        # Skip if already captured (e.g. by single-track mode)
        skip_current = wav_path.exists() or current_track in already_captured
        if skip_current:
            self._log(f"  Track {current_track} already captured – skipping")
        else:
            self._audio.open_track(wav_path)
            with self._lock:
                self._current_track = current_track
                self._current_filename = str(wav_path)

        tracks_captured = current_track
        track_deadline = time.monotonic() + TRACK_TIMEOUT

        while True:
            if self._stop_event.is_set():
                break

            # Respect pause
            self._pause_event.wait()
            if self._stop_event.is_set():
                break

            event = self._webhook.wait_for_event(timeout=1.0)

            if event is None:
                if time.monotonic() > track_deadline:
                    self._log(f"  Track timeout after track {current_track}")
                    break
                continue

            status = event.get("status", "")

            if status == "PLAY":
                track_num = decode_webhook_track(event)
                if track_num is not None and track_num != current_track:
                    ev_deck, ev_cd = decode_webhook_disc(event)
                    if ev_cd is not None and ev_cd != cd_pos:
                        continue

                    # Close the previous track only if it was being recorded
                    if not skip_current:
                        self._audio.close_track()

                    current_track = track_num
                    wav_path = tracks_dir / f"{current_track:02d}.wav"

                    # Skip if already captured (e.g. by single-track mode)
                    skip_current = wav_path.exists() or current_track in already_captured
                    if skip_current:
                        self._log(f"  Track {current_track} already captured – skipping")
                    else:
                        self._audio.open_track(wav_path)
                        with self._lock:
                            self._current_track = current_track
                            self._current_filename = str(wav_path)
                        self._log(f"  Track → {current_track}")

                    tracks_captured = max(tracks_captured, current_track)
                    self._capture_state.mark_partial(release_id, current_track, expected)
                    track_deadline = time.monotonic() + TRACK_TIMEOUT

            elif status in ("STOP", "EJECT"):
                self._log(f"  Received {status} – disc finished")
                break

            elif status == "PAUSE":
                track_deadline = time.monotonic() + TRACK_TIMEOUT

        # Finalize
        if not skip_current:
            self._audio.close_track()
        try:
            self._slink.send_stop(deck)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)

        self._capture_state.mark_complete(release_id, tracks_captured)
        self._log(f"  Done: {tracks_captured} tracks captured")

        if tracks_captured != expected:
            self._log(f"  Note: captured={tracks_captured} expected={expected}")

        return True

    # ===================================================================
    # Helpers
    # ===================================================================

    def _load_releases(self, deck: int | None, release_id: int | None) -> list[dict]:
        """Load releases from the Discogs database."""
        db_path = Path("server") / "discogs_data_all.json"
        if not db_path.exists():
            db_path = Path("discogs_data_all.json")
        with open(db_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        releases = data.get("data", [])

        if release_id is not None:
            releases = [r for r in releases if r.get("release_id") == release_id]
        if deck is not None:
            releases = [r for r in releases if r.get("deck_number") == deck]

        releases.sort(key=lambda r: (r.get("deck_number", 1), r.get("cd_position", 0)))
        return releases

    def _cleanup(self) -> None:
        """Stop audio, restore webhook, release resources."""
        if self._audio:
            self._audio.stop()
            self._audio = None

        # Restore ESP32 webhook to main backend
        try:
            self._slink.configure_webhook_target(port=MAIN_BACKEND_WEBHOOK_PORT, path="/webhook")
            self._log(f"Webhook restored to port {MAIN_BACKEND_WEBHOOK_PORT}")
        except Exception as exc:  # noqa: BLE001
            self._log(f"Warning: could not restore webhook: {exc}")

        if self._webhook:
            self._webhook.stop()
            self._webhook = None

        with self._lock:
            self._current_release = None
            self._current_track = None
            self._current_filename = None
            self._current_deck = None

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        with self._lock:
            self._log_buffer.append(line)
        LOGGER.info("Capture: %s", message)

    @staticmethod
    def _release_summary(release: dict | None) -> dict | None:
        if not release:
            return None
        return {
            "release_id": release.get("release_id"),
            "title": release.get("title"),
            "artist": release.get("artists_sort"),
            "deck_number": release.get("deck_number"),
            "cd_position": release.get("cd_position"),
        }
