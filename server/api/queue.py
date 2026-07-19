from flask import Blueprint, jsonify


def create_queue_api(playback_runtime) -> Blueprint:
    queue_api = Blueprint('runtime_queue_api', __name__)

    @queue_api.route('/queue', methods=['GET'])
    def playback_queue():
        return jsonify(playback_runtime.queue()), 200

    return queue_api