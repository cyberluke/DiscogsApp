from flask import Blueprint, jsonify

try:
    from api.playlists import create_playlists_api
    from api.queue import create_queue_api
    from api.recommendations import create_recommendations_api
    from api.tracks import create_tracks_api
except ImportError:
    from server.api.playlists import create_playlists_api
    from server.api.queue import create_queue_api
    from server.api.recommendations import create_recommendations_api
    from server.api.tracks import create_tracks_api


def create_playback_api(playback_runtime, recommendation_engine) -> Blueprint:
    playback_api = Blueprint('playback_api', __name__)

    def runtime_error_response(error: Exception):
        return jsonify({'error': str(error), 'playback': playback_runtime.status()}), 500

    @playback_api.route('/playback/status', methods=['GET'])
    def playback_status():
        return jsonify(playback_runtime.status()), 200

    @playback_api.route('/playback/progress', methods=['GET'])
    def playback_progress():
        return jsonify(playback_runtime.progress()), 200

    playback_api.register_blueprint(create_playlists_api(playback_runtime, runtime_error_response))
    playback_api.register_blueprint(create_tracks_api(playback_runtime, runtime_error_response))
    playback_api.register_blueprint(create_queue_api(playback_runtime))
    playback_api.register_blueprint(create_recommendations_api(recommendation_engine))
    return playback_api