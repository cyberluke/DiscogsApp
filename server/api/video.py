from __future__ import annotations

import os

from flask import Blueprint, abort, jsonify, request, send_from_directory


def create_video_api(video_library_service, video_sync_service) -> Blueprint:
    video_api = Blueprint('video_api', __name__)

    @video_api.route('/video/sync', methods=['GET'])
    def video_sync():
        return jsonify(video_sync_service.current_state()), 200

    @video_api.route('/video/best', methods=['GET'])
    def best_video():
        artist = request.args.get('artist', '')
        title = request.args.get('title', '')
        duration = request.args.get('duration', type=int)
        return jsonify(video_library_service.resolve(artist=artist, title=title, duration=duration)), 200

    @video_api.route('/video/download', methods=['POST'])
    def download_video():
        data = request.get_json(silent=True) or {}
        try:
            result = _download_video_result(video_library_service, video_sync_service, data)
        except Exception as error:
            return jsonify({
                'video': None,
                'candidate': None,
                'can_download': False,
                'message': str(error),
            }), 500
        status = 200 if result.get('video') else 404
        return jsonify(result), status

    @video_api.route('/video/offset', methods=['POST'])
    def save_video_offset():
        data = request.get_json(silent=True) or {}
        try:
            result = _save_video_offset_result(video_sync_service, data)
        except Exception as error:
            return jsonify({'message': str(error)}), 400
        return jsonify(result), 200

    @video_api.route('/video/local/<path:filename>', methods=['GET'])
    def local_video(filename):
        for root in video_library_service.cache.directories:
            path = os.path.abspath(os.path.join(root, filename))
            root_path = os.path.abspath(root)
            if path.startswith(root_path + os.sep) and os.path.isfile(path):
                return send_from_directory(root_path, filename, as_attachment=False, conditional=True)
        abort(404)

    return video_api


def _download_video_result(video_library_service, video_sync_service, data):
    if data.get('artist') or data.get('title'):
        return video_library_service.download(
            artist=data.get('artist', ''),
            title=data.get('title', ''),
            duration=data.get('duration'),
        )
    return video_sync_service.download_current()


def _save_video_offset_result(video_sync_service, data):
    return video_sync_service.save_current_offset_preference(
        data.get('manual_offset_seconds', 0),
        data.get('use_detected_offset', True),
    )