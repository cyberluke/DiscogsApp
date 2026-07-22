from flask import Blueprint, jsonify

try:
    from api.request_json import JsonRequestError, parse_json_body
except ImportError:
    from server.api.request_json import JsonRequestError, parse_json_body


def create_queue_api(playback_runtime, runtime_error_response=None) -> Blueprint:
    queue_api = Blueprint('runtime_queue_api', __name__)

    def _error_response(error):
        if runtime_error_response:
            return runtime_error_response(error)
        return jsonify({'error': str(error)}), 500

    @queue_api.route('/queue', methods=['GET'])
    def playback_queue():
        return jsonify(playback_runtime.queue()), 200

    @queue_api.route('/queue/add', methods=['POST'])
    def queue_add():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        track = data.get('track')
        if not track:
            return jsonify({'error': 'Missing "track" in request body'}), 400
        position = data.get('position', 'next')
        try:
            result = playback_runtime.queue_add(track, position)
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    @queue_api.route('/queue/add-many', methods=['POST'])
    def queue_add_many():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        tracks = data.get('tracks')
        if not tracks or not isinstance(tracks, list):
            return jsonify({'error': 'Missing "tracks" list in request body'}), 400
        position = data.get('position', 'end')
        try:
            result = playback_runtime.queue_add_many(tracks, position)
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    @queue_api.route('/queue/remove', methods=['POST'])
    def queue_remove():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        index = data.get('index')
        if index is None:
            return jsonify({'error': 'Missing "index" in request body'}), 400
        try:
            result = playback_runtime.queue_remove(int(index))
        except (TypeError, ValueError):
            return jsonify({'error': '"index" must be an integer'}), 400
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    @queue_api.route('/queue/move', methods=['POST'])
    def queue_move():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        from_index = data.get('from_index')
        to_index = data.get('to_index')
        if from_index is None or to_index is None:
            return jsonify({'error': 'Missing "from_index" or "to_index"'}), 400
        try:
            result = playback_runtime.queue_move(int(from_index), int(to_index))
        except (TypeError, ValueError):
            return jsonify({'error': '"from_index" and "to_index" must be integers'}), 400
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    @queue_api.route('/queue/move-to-top', methods=['POST'])
    def queue_move_to_top():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        index = data.get('index')
        if index is None:
            return jsonify({'error': 'Missing "index"'}), 400
        try:
            result = playback_runtime.queue_move_to_top(int(index))
        except (TypeError, ValueError):
            return jsonify({'error': '"index" must be an integer'}), 400
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    @queue_api.route('/queue/move-to-bottom', methods=['POST'])
    def queue_move_to_bottom():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        index = data.get('index')
        if index is None:
            return jsonify({'error': 'Missing "index"'}), 400
        try:
            result = playback_runtime.queue_move_to_bottom(int(index))
        except (TypeError, ValueError):
            return jsonify({'error': '"index" must be an integer'}), 400
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    @queue_api.route('/queue/clear', methods=['POST'])
    def queue_clear():
        try:
            result = playback_runtime.queue_clear()
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    @queue_api.route('/queue/play-index', methods=['POST'])
    def queue_play_index():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        index = data.get('index')
        if index is None:
            return jsonify({'error': 'Missing "index"'}), 400
        try:
            result = playback_runtime.queue_play_index(int(index))
        except (TypeError, ValueError):
            return jsonify({'error': '"index" must be an integer'}), 400
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    @queue_api.route('/queue/shuffle', methods=['POST'])
    def queue_shuffle():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        enabled = data.get('enabled', False)
        try:
            result = playback_runtime.queue_set_shuffle(bool(enabled))
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    @queue_api.route('/queue/repeat', methods=['POST'])
    def queue_repeat():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        mode = data.get('mode', 'off')
        try:
            result = playback_runtime.queue_set_repeat(mode)
        except Exception as error:
            return _error_response(error)
        return jsonify(result), 200

    return queue_api