from flask import Blueprint, jsonify, request


def create_history_api(playback_runtime) -> Blueprint:
    history_api = Blueprint('runtime_history_api', __name__)

    @history_api.route('/history', methods=['GET'])
    def get_history():
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        return jsonify(playback_runtime.get_history(limit=limit, offset=offset)), 200

    @history_api.route('/history/stats', methods=['GET'])
    def history_stats():
        result = playback_runtime.get_history(limit=500, offset=0)
        history = result.get('history', [])
        if not history:
            return jsonify({
                'total_tracks': 0,
                'total_duration_seconds': 0,
                'top_artists': [],
                'genre_distribution': {},
            }), 200

        artist_counts: dict[str, int] = {}
        total_seconds = 0
        for entry in history:
            artist = entry.get('artist') or 'Unknown'
            artist_counts[artist] = artist_counts.get(artist, 0) + 1
            dur = entry.get('duration') or ''
            parts = str(dur).split(':')
            try:
                if len(parts) == 2:
                    total_seconds += int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    total_seconds += int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except (ValueError, TypeError):
                pass

        top_artists = sorted(artist_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        return jsonify({
            'total_tracks': len(history),
            'total_duration_seconds': total_seconds,
            'top_artists': [{'artist': a, 'count': c} for a, c in top_artists],
        }), 200

    @history_api.route('/history', methods=['DELETE'])
    def clear_history():
        # Manual clear only — never auto-cleared
        playback_runtime.clear_history()
        return jsonify({'status': 'cleared'}), 200

    return history_api
