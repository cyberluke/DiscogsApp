from flask import Blueprint, jsonify, request

try:
    from api.request_json import JsonRequestError, parse_json_body
except ImportError:
    from server.api.request_json import JsonRequestError, parse_json_body


def create_playlists_api(playback_runtime, runtime_error_response) -> Blueprint:
    playlists_api = Blueprint('runtime_playlists_api', __name__)

    @playlists_api.route('/playlist/play', methods=['POST'])
    def playlist_play():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error), 'playback': playback_runtime.status()}), 400
        try:
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

    return playlists_api