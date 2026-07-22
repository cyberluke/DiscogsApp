#!/usr/bin/env python
"""Batch-enrich discogs collection with Spotify audio features (BPM, key, energy, etc.).

Usage:
    python scripts/spotify_enrich.py [options]

Options:
    --db <path>          Path to discogs JSON (default: server/discogs_data_all.json)
    --out <path>         Output Spotify JSON (default: server/spotify_audio_features.json)
    --limit <n>          Max releases to process (default: all)
    --force              Re-process already-enriched releases
    --dry-run            Show what would be processed without calling API
    --delay <seconds>    Delay between API calls (default: 0.5)
"""

import argparse
import json
import logging
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.services.spotify.client import SpotifyClient
from server.services.spotify.store import SpotifyStore

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def load_discogs(path: str) -> list[dict]:
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh)
    return data.get('data', data if isinstance(data, list) else [])


def clean_track_title(title: str) -> str:
    """Remove remix/version info for better Spotify matching."""
    # Remove parenthetical remix info but keep the base title
    title = re.sub(r'\s*\([^)]*(?:mix|version|edit|remix|remake)[^)]*\)', '', title, flags=re.IGNORECASE)
    # Remove bracketed info
    title = re.sub(r'\s*\[[^\]]*\]', '', title)
    return title.strip()


def extract_features(track_id: str, client: SpotifyClient) -> dict | None:
    """Get audio features and format them for storage."""
    features = client.get_audio_features(track_id)
    if not features or features.get('tempo') is None:
        return None
    key = features.get('key', -1)
    mode = features.get('mode', 1)
    return {
        'spotify_track_id': track_id,
        'bpm': round(features.get('tempo', 0), 1),
        'key': SpotifyClient.key_name(key, mode),
        'key_code': key,
        'mode': mode,
        'energy': round(features.get('energy', 0), 3),
        'danceability': round(features.get('danceability', 0), 3),
        'valence': round(features.get('valence', 0), 3),
        'acousticness': round(features.get('acousticness', 0), 3),
        'instrumentalness': round(features.get('instrumentalness', 0), 3),
        'liveness': round(features.get('liveness', 0), 3),
        'speechiness': round(features.get('speechiness', 0), 3),
        'loudness': round(features.get('loudness', 0), 2),
        'duration_ms': features.get('duration_ms'),
        'time_signature': features.get('time_signature'),
    }


def enrich_release(release: dict, client: SpotifyClient, delay: float) -> dict | None:
    """Search Spotify for each track in a release, return aggregated entry."""
    artist = release.get('artists_sort', '')
    tracklist = release.get('tracklist', [])
    if not tracklist:
        return None

    tracks_data = []
    release_bpm_values = []

    for track in tracklist:
        title = track.get('title', '')
        if not title:
            continue
        # Use track-level artist if available (various artists compilations)
        track_artist = artist
        if track.get('artists'):
            track_artist = track['artists'][0].get('name', artist)

        search_title = clean_track_title(title)
        match = client.search_track(track_artist, search_title)
        time.sleep(delay)

        if not match:
            tracks_data.append({
                'position': track.get('position'),
                'title': title,
                'matched': False,
            })
            continue

        features = extract_features(match['id'], client)
        time.sleep(delay)

        if features:
            release_bpm_values.append(features['bpm'])
            tracks_data.append({
                'position': track.get('position'),
                'title': title,
                'matched': True,
                'spotify_track_name': match.get('name'),
                'spotify_artist': match.get('artists', [{}])[0].get('name', ''),
                **features,
            })
        else:
            tracks_data.append({
                'position': track.get('position'),
                'title': title,
                'matched': True,
                'spotify_track_id': match['id'],
                'spotify_track_name': match.get('name'),
                'bpm': None,
            })

    if not tracks_data:
        return None

    # Compute release-level dominant BPM (median of matched tracks)
    dominant_bpm = None
    if release_bpm_values:
        sorted_bpms = sorted(release_bpm_values)
        dominant_bpm = sorted_bpms[len(sorted_bpms) // 2]

    return {
        'release_id': release.get('release_id') or release.get('id'),
        'artist': artist,
        'title': release.get('title'),
        'dominant_bpm': dominant_bpm,
        'tracks': tracks_data,
        'enriched_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'source': 'spotify',
    }


def main():
    parser = argparse.ArgumentParser(description='Enrich discogs collection with Spotify audio features')
    parser.add_argument('--db', default='server/discogs_data_all.json')
    parser.add_argument('--out', default='server/spotify_audio_features.json')
    parser.add_argument('--not-found', default='server/spotify_not_found.json')
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--force', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--delay', type=float, default=0.3)
    args = parser.parse_args()

    # Load .env files
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'), override=False)
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server', '.env'), override=False)
    except ImportError:
        pass

    client_id = os.getenv('SPOTIFY_CLIENT_ID', '')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET', '')
    if not client_id or not client_secret:
        logger.error('Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables')
        sys.exit(1)

    releases = load_discogs(args.db)
    store = SpotifyStore(args.out)
    client = SpotifyClient(client_id, client_secret)

    logger.info('Loaded %d releases, %d already enriched', len(releases), store.count())

    processed = 0
    matched = 0
    skipped = 0
    not_found = []  # releases where no track matched on Spotify

    for release in releases:
        rid = str(release.get('release_id') or release.get('id'))
        if not args.force and store.has_release(rid):
            skipped += 1
            continue
        if args.limit and processed >= args.limit:
            break

        artist = release.get('artists_sort', '?')
        title = release.get('title', '?')

        if args.dry_run:
            logger.info('[DRY] Would process: %s - %s', artist, title)
            processed += 1
            continue

        logger.info('[%d/%d] Processing: %s - %s', processed + 1, len(releases) - skipped, artist, title)
        entry = enrich_release(release, client, args.delay)
        processed += 1

        if entry and any(t.get('matched') for t in entry.get('tracks', [])):
            store.set_release(rid, entry)
            matched += 1
            bpm_info = f" (BPM: {entry['dominant_bpm']})" if entry['dominant_bpm'] else ''
            logger.info('  ✓ Matched %d tracks%s', len(entry['tracks']), bpm_info)
        else:
            not_found.append({
                'release_id': rid,
                'artist': artist,
                'title': title,
                'styles': release.get('styles', []),
                'year': release.get('year'),
            })
            logger.info('  ✗ No tracks matched on Spotify')

        # Save periodically
        if processed % 10 == 0:
            store.save()
            logger.info('  [checkpoint saved]')

    store.save()

    # Save not-found releases for alternative processing
    with open(args.not_found, 'w', encoding='utf-8') as fh:
        json.dump(not_found, fh, ensure_ascii=False, indent=1)

    logger.info('=' * 60)
    logger.info('DONE')
    logger.info('  Processed: %d', processed)
    logger.info('  Matched:   %d', matched)
    logger.info('  Not found: %d (saved to %s)', len(not_found), args.not_found)
    logger.info('  Skipped:   %d (already enriched)', skipped)
    logger.info('  Total in store: %d', store.count())
    logger.info('=' * 60)


if __name__ == '__main__':
    main()
