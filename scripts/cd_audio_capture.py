#!/usr/bin/env python3
"""
CD Audio Capture Pipeline for Sony CDP-CX disc changers.

Captures CD audio via RME RayDAT SPDIF digital input, controlled through
the existing Sony S-Link protocol implementation (server.sony.slink).

This CLI script reuses the shared CaptureService from server.services.capture.

Usage:
    python scripts/cd_audio_capture.py [options]

Examples:
    # Dry run - show what would be captured
    python scripts/cd_audio_capture.py --dry-run

    # Capture all pending releases
    python scripts/cd_audio_capture.py

    # Capture only deck 1
    python scripts/cd_audio_capture.py --deck 1

    # Capture a single release
    python scripts/cd_audio_capture.py --release-id 5127714

    # Capture first 5 pending releases
    python scripts/cd_audio_capture.py --limit 5
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Project imports – reuse the authoritative S-Link implementation
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from server.services.capture import CaptureService  # noqa: E402
from server.sony.slink import SLinkClient  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = r"D:\DiscogsAudioCapture"
DEFAULT_WEBHOOK_PORT = 5001

LOGGER = logging.getLogger("cd_audio_capture")


# ===================================================================
# Discogs helpers (dry-run only)
# ===================================================================

def load_releases(db_path: str) -> list[dict]:
    import json
    with open(db_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    releases = data.get("data", [])
    LOGGER.info("Loaded %d releases from %s", len(releases), db_path)
    return releases


def audio_track_count(release: dict) -> int:
    return len([
        t for t in release.get("tracklist", [])
        if t.get("type_", "track") == "track"
    ])


# ===================================================================
# CLI entry point
# ===================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CD Audio Capture Pipeline for Sony CDP-CX disc changers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db", default=os.path.join("server", "discogs_data_all.json"),
                        help="Path to Discogs JSON database")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR,
                        help="Root output directory (default: %(default)s)")
    parser.add_argument("--state", default=None,
                        help="Capture-state JSON (default: <output>/capture_state.json)")
    parser.add_argument("--webhook-port", type=int, default=DEFAULT_WEBHOOK_PORT,
                        help="Port for the webhook receiver (default: %(default)s)")
    parser.add_argument("--deck", type=int, choices=[1, 2], default=None,
                        help="Capture only this deck number")
    parser.add_argument("--release-id", type=int, default=None,
                        help="Capture a single release by ID")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of releases to capture in this run")
    parser.add_argument("--dry-run", action="store_true",
                        help="List pending releases without capturing")
    parser.add_argument("--slink-server", default=None,
                        help="ESP32 S-Link adapter URL (default: auto-discover)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Debug-level logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )

    state_path = args.state or os.path.join(args.output, "capture_state.json")

    # -- dry run (no hardware needed) ------------------------------------
    if args.dry_run:
        from server.services.capture.state import CaptureState

        releases = load_releases(args.db)
        if args.release_id is not None:
            releases = [r for r in releases if r.get("release_id") == args.release_id]
        if args.deck is not None:
            releases = [r for r in releases if r.get("deck_number") == args.deck]
        releases.sort(key=lambda r: (r.get("deck_number", 1), r.get("cd_position", 0)))

        state = CaptureState(state_path)
        pending = [r for r in releases if not state.is_complete(r["release_id"])]
        if args.limit:
            pending = pending[:args.limit]

        LOGGER.info("Releases total=%d  pending=%d", len(releases), len(pending))
        for rel in pending:
            last = state.last_track(rel["release_id"])
            note = f"resume track {last + 1}" if last else "new"
            LOGGER.info(
                "  [DRY]  %-30s  %-40s  deck=%d cd=%-3d tracks=%d  (%s)",
                rel.get("artists_sort", "?")[:30],
                rel.get("title", "?")[:40],
                rel.get("deck_number", 1),
                rel.get("cd_position", 0),
                audio_track_count(rel),
                note,
            )
        return

    # -- live capture via CaptureService ---------------------------------
    slink = SLinkClient(args.slink_server)
    service = CaptureService(
        slink,
        output_dir=args.output,
        state_path=state_path,
        webhook_port=args.webhook_port,
    )

    result = service.start(deck=args.deck, release_id=args.release_id, limit=args.limit)
    if "error" in result:
        LOGGER.error("Cannot start: %s", result["error"])
        sys.exit(1)

    LOGGER.info("Capture started – press Ctrl+C to stop")

    try:
        while service.state in ("running", "paused", "stopping"):
            time.sleep(2)
            progress = service.progress()
            current = service.current()
            release = current.get("release") or {}
            LOGGER.info(
                "  %s  %s  track=%s  %.0f%%  (%d/%d)",
                progress["state"],
                release.get("title", "—")[:40],
                current.get("track", "—"),
                progress["percent"],
                progress["done"],
                progress["total"],
            )
    except KeyboardInterrupt:
        LOGGER.info("Interrupted – stopping capture")
        service.stop()
        time.sleep(3)

    LOGGER.info("Done.")


if __name__ == "__main__":
    main()
