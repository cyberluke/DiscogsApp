from flask import Blueprint, jsonify, request

try:
    from api.playlists import create_playlists_api
    from api.queue import create_queue_api
    from api.recommendations import create_recommendations_api
    from api.tracks import create_tracks_api
    from api.history import create_history_api
except ImportError:
    from server.api.playlists import create_playlists_api
    from server.api.queue import create_queue_api
    from server.api.recommendations import create_recommendations_api
    from server.api.tracks import create_tracks_api
    from server.api.history import create_history_api


def create_playback_api(playback_runtime, recommendation_engine, data_repository=None) -> Blueprint:
    playback_api = Blueprint('playback_api', __name__)

    def runtime_error_response(error: Exception):
        return jsonify({'error': str(error), 'playback': playback_runtime.status()}), 500

    def adapter_response(callback):
        try:
            return jsonify({'available': True, 'adapter': callback()}), 200
        except Exception as error:
            return jsonify({'available': False, 'error': str(error)}), 502

    @playback_api.route('/playback/status', methods=['GET'])
    def playback_status():
        return jsonify(playback_runtime.status()), 200

    @playback_api.route('/playback/progress', methods=['GET'])
    def playback_progress():
        return jsonify(playback_runtime.progress()), 200

    @playback_api.route('/playback/start-delay', methods=['POST'])
    def playback_start_delay():
        data = request.get_json(silent=True) or {}
        return jsonify(playback_runtime.set_playback_start_delay_enabled(bool(data.get('enabled')))), 200

    @playback_api.route('/playback/resync', methods=['POST'])
    def playback_resync():
        return jsonify(playback_runtime.request_resync()), 200

    @playback_api.route('/hardware/status', methods=['GET'])
    def hardware_status():
        return jsonify(playback_runtime.status()), 200

    @playback_api.route('/hardware/adapter/status', methods=['GET'])
    def hardware_adapter_status():
        return adapter_response(lambda: playback_runtime.slink_client.adapter_get('/status'))

    @playback_api.route('/hardware/slink/last-packet', methods=['GET'])
    def hardware_last_packet():
        return adapter_response(lambda: playback_runtime.slink_client.adapter_get('/slink/last-packet'))

    @playback_api.route('/hardware/slink/recent-packets', methods=['GET'])
    def hardware_recent_packets():
        return adapter_response(lambda: playback_runtime.slink_client.adapter_get('/slink/recent-packets'))

    @playback_api.route('/hardware/slink/debug/enable', methods=['POST'])
    def hardware_debug_enable():
        return adapter_response(lambda: playback_runtime.slink_client.adapter_post('/slink/debug/enable'))

    @playback_api.route('/hardware/slink/debug/disable', methods=['POST'])
    def hardware_debug_disable():
        return adapter_response(lambda: playback_runtime.slink_client.adapter_post('/slink/debug/disable'))

    @playback_api.route('/hardware/continuous-status/enable', methods=['POST'])
    def enable_continuous_status():
        return jsonify(playback_runtime.set_continuous_status_enabled(True)), 200

    @playback_api.route('/hardware/continuous-status/disable', methods=['POST'])
    def disable_continuous_status():
        return jsonify(playback_runtime.set_continuous_status_enabled(False)), 200

    playback_api.register_blueprint(create_playlists_api(playback_runtime, runtime_error_response, data_repository))
    playback_api.register_blueprint(create_tracks_api(playback_runtime, runtime_error_response))
    playback_api.register_blueprint(create_queue_api(playback_runtime, runtime_error_response))
    playback_api.register_blueprint(create_recommendations_api(recommendation_engine))
    playback_api.register_blueprint(create_history_api(playback_runtime))
    return playback_api