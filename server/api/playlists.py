from flask import Blueprint, jsonify, request

try:
    from api.request_json import JsonRequestError, parse_json_body
except ImportError:
    from server.api.request_json import JsonRequestError, parse_json_body


def create_playlists_api(playback_runtime, runtime_error_response, data_repository=None) -> Blueprint:
    playlists_api = Blueprint('runtime_playlists_api', __name__)

    @playlists_api.route('/playlist/play', methods=['POST'])
    def playlist_play():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error), 'playback': playback_runtime.status()}), 400
        mode = data.get('mode', 'replace')
        try:
            if mode == 'append':
                playback = playback_runtime.play_playlist_append(data)
            else:
                playback = playback_runtime.play_playlist(data)
        except ValueError as error:
            return jsonify({'error': str(error), 'playback': playback_runtime.status()}), 400
        except Exception as error:
            return runtime_error_response(error)
        return jsonify(playback), 200

    @playlists_api.route('/playlist/stop', methods=['POST'])
    def playlist_stop():
        return jsonify(playback_runtime.stop()), 200

    @playlists_api.route('/playlist/pause', methods=['POST'])
    def playlist_pause():
        return jsonify(playback_runtime.pause()), 200

    @playlists_api.route('/playlist/resume', methods=['POST'])
    def playlist_resume():
        return jsonify(playback_runtime.resume()), 200

    @playlists_api.route('/playlist/next', methods=['POST'])
    def playlist_next():
        return jsonify(playback_runtime.next_track()), 200

    @playlists_api.route('/playlist/previous', methods=['POST'])
    def playlist_previous():
        return jsonify(playback_runtime.previous_track()), 200

    @playlists_api.route('/playlists/<name>', methods=['GET'])
    def playlist_detail(name):
        if data_repository is None:
            return jsonify({'error': 'Data repository not available'}), 500
        playlists = data_repository.all_playlists()
        playlist = next((p for p in playlists if p.get('name') == name), None)
        if playlist is None:
            return jsonify({'error': f'Playlist "{name}" not found'}), 404
        tracks = playlist.get('tracks', [])
        total_seconds = 0
        for t in tracks:
            dur = t.get('duration', '')
            parts = str(dur).split(':')
            try:
                if len(parts) == 2:
                    total_seconds += int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    total_seconds += int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except (ValueError, TypeError):
                pass
        return jsonify({
            'name': playlist.get('name'),
            'tracks': tracks,
            'track_count': len(tracks),
            'total_duration_seconds': total_seconds,
        }), 200

    return playlists_api