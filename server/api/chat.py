from flask import Blueprint, jsonify, request

try:
    from api.request_json import JsonRequestError, parse_json_body
    from services.ai import ChatService, ConversationContextBuilder, MusicRecommendationService, PlaylistActionService
except ImportError:
    from server.api.request_json import JsonRequestError, parse_json_body
    from server.services.ai import ChatService, ConversationContextBuilder, MusicRecommendationService, PlaylistActionService


def create_chat_api(data_repository, playback_runtime, ai_client=None, spotify_store=None) -> Blueprint:
    chat_api = Blueprint('chat_api', __name__, url_prefix='/api')
    context_builder = ConversationContextBuilder(data_repository, playback_runtime)
    recommendation_service = MusicRecommendationService(data_repository, spotify_store=spotify_store)
    playlist_action_service = PlaylistActionService(data_repository, playback_runtime)
    chat_service = ChatService(context_builder, recommendation_service, ai_client=ai_client, playlist_action_service=playlist_action_service)

    @chat_api.route('/chat/context', methods=['GET'])
    def chat_context():
        return jsonify(chat_service.context()), 200

    @chat_api.route('/chat', methods=['POST'])
    def chat():
        try:
            payload = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        try:
            return jsonify(chat_service.chat(payload)), 200
        except RuntimeError as error:
            return jsonify({'error': str(error), 'context': chat_service.context()}), 503

    @chat_api.route('/recommendations/current', methods=['GET'])
    def recommendations_current():
        limit = _limit_from_request()
        return jsonify(chat_service.recommendations_for_current(limit=limit)), 200

    @chat_api.route('/recommend/current', methods=['GET'])
    def recommend_current():
        limit = _limit_from_request()
        return jsonify(chat_service.recommendations_for_current(limit=limit)), 200

    @chat_api.route('/recommend', methods=['POST'])
    def recommend():
        try:
            payload = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400
        try:
            return jsonify(chat_service.chat(payload)), 200
        except RuntimeError as error:
            return jsonify({'error': str(error), 'context': chat_service.context()}), 503

    @chat_api.route('/play', methods=['POST'])
    def play_recommendation():
        try:
            payload = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error), 'playback': playback_runtime.status()}), 400
        track = payload.get('track') or payload
        if not isinstance(track, dict):
            return jsonify({'error': 'track recommendation is required', 'playback': playback_runtime.status()}), 400
        try:
            return jsonify(playlist_action_service.play(track)), 200
        except Exception as error:
            return jsonify({'error': str(error), 'playback': playback_runtime.status()}), 500

    return chat_api


def _limit_from_request() -> int:
    try:
        return max(1, min(25, int(request.args.get('limit') or 5)))
    except ValueError:
        return 5