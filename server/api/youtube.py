from flask import Blueprint, jsonify, request


def create_youtube_api(youtube_search_service, youtube_sync_service) -> Blueprint:
    youtube_api = Blueprint('youtube_api', __name__)

    @youtube_api.route('/youtube/best-video', methods=['GET'])
    def best_video():
        artist = request.args.get('artist', '')
        title = request.args.get('title', '')
        duration = request.args.get('duration', type=int)
        video = youtube_search_service.find_best_video(artist=artist, title=title, duration=duration)
        return jsonify({
            'video': video,
            'message': None if video else 'No suitable music video found.',
        }), 200

    @youtube_api.route('/youtube/sync', methods=['GET'])
    def youtube_sync():
        return jsonify(youtube_sync_service.current_state()), 200

    return youtube_api
