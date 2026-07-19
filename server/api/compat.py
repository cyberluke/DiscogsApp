from flask import Blueprint, jsonify

try:
    from api.request_json import JsonRequestError, parse_json_body
except ImportError:
    from server.api.request_json import JsonRequestError, parse_json_body


def create_compat_api(playback_runtime) -> Blueprint:
    compat_api = Blueprint('compat_api', __name__)

    def runtime():
        return playback_runtime() if callable(playback_runtime) else playback_runtime

    @compat_api.route('/playlist', methods=['POST'])
    def playlist():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error), 'playback': runtime().status()}), 400

        try:
            playback = runtime().play_playlist(data)
        except ValueError as error:
            return jsonify({'error': str(error), 'playback': runtime().status()}), 400
        except Exception as error:
            return jsonify({'error': str(error), 'playback': runtime().status()}), 500
        return jsonify({'status': 'Playlist sent', 'playback': playback}), 200

    @compat_api.route('/track', methods=['POST'])
    def track():
        try:
            track_data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error), 'playback': runtime().status()}), 400

        try:
            playback = runtime().play_track(track_data)
        except Exception as error:
            return jsonify({'error': str(error), 'playback': runtime().status()}), 500
        return jsonify({'status': 'Track sent', 'playback': playback}), 200

    return compat_api