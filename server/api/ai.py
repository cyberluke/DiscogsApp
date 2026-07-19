from flask import Blueprint, jsonify, request

RELEASE_NOT_FOUND = 'Release not found'


def create_ai_api(data_repository, music_analysis_service) -> Blueprint:
    ai_api = Blueprint('ai_api', __name__, url_prefix='/api')

    @ai_api.route('/releases/<int:release_id>', methods=['GET'])
    def get_release(release_id: int):
        release = data_repository.get_release_by_id(release_id)
        if release is None:
            return jsonify({'error': RELEASE_NOT_FOUND}), 404
        return jsonify(release), 200

    @ai_api.route('/releases/<int:release_id>/ai', methods=['GET'])
    def get_release_ai(release_id: int):
        ai_metadata = music_analysis_service.get_release_ai(release_id)
        if ai_metadata is None:
            release = data_repository.get_release_by_id(release_id)
            if release is None:
                return jsonify({'error': RELEASE_NOT_FOUND}), 404
            return jsonify({'error': 'AI metadata not generated'}), 404
        return jsonify(ai_metadata), 200

    @ai_api.route('/ai/enrich/<int:release_id>', methods=['POST'])
    def enrich_release(release_id: int):
        force = _truthy(request.args.get('force'))
        try:
            ai_metadata = music_analysis_service.enrich_release(release_id, force=force)
        except RuntimeError as error:
            return jsonify({'error': str(error)}), 503
        if ai_metadata is None:
            return jsonify({'error': RELEASE_NOT_FOUND}), 404
        return jsonify(ai_metadata), 200

    @ai_api.route('/ai/enrich-all', methods=['POST'])
    def enrich_all():
        force = _truthy(request.args.get('force'))
        limit = request.args.get('limit')
        try:
            parsed_limit = int(limit) if limit else None
        except ValueError:
            return jsonify({'error': 'limit must be an integer'}), 400
        return jsonify(music_analysis_service.enrich_all(force=force, limit=parsed_limit)), 200

    return ai_api


def _truthy(value) -> bool:
    return str(value or '').lower() in ('1', 'true', 'yes')