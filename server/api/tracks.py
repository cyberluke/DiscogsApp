from flask import Blueprint, jsonify, request

try:
    from api.request_json import JsonRequestError, parse_json_body
except ImportError:
    from server.api.request_json import JsonRequestError, parse_json_body


def create_tracks_api(playback_runtime, runtime_error_response) -> Blueprint:
    tracks_api = Blueprint('runtime_tracks_api', __name__)

    @tracks_api.route('/track/play', methods=['POST'])
    def track_play():
        try:
            track = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error), 'playback': playback_runtime.status()}), 400
        try:
            return jsonify(playback_runtime.play_track(track)), 200
        except Exception as error:
            return runtime_error_response(error)

    return tracks_api