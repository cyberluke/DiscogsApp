from flask import Blueprint, jsonify

try:
    from api.request_json import JsonRequestError, parse_json_body
except ImportError:
    from server.api.request_json import JsonRequestError, parse_json_body


def create_library_api(data_repository) -> Blueprint:
    library_api = Blueprint('library_api', __name__)

    @library_api.route('/releases')
    def get_all_releases():
        return jsonify(data_repository.all_releases()), 200

    @library_api.route('/playlists', methods=['GET'])
    def playlists():
        playlists_data = data_repository.all_playlists()
        playlists_data.append(data_repository.favourite_tracks_playlist())
        return jsonify(playlists_data), 200

    @library_api.route('/save-playlist', methods=['POST'])
    def save_playlist():
        try:
            playlist = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400

        if not isinstance(playlist, dict) or not playlist.get('name'):
            return jsonify({'error': 'Playlist name is required'}), 400

        data_repository.save_playlist(playlist)
        return jsonify({'status': 'Playlist sent'}), 200

    @library_api.route('/favourite', methods=['GET'])
    def get_tracks_with_high_score():
        return jsonify(data_repository.favourite_tracks_playlist()), 200

    @library_api.route('/favourite', methods=['POST'])
    def add_to_favourites():
        try:
            data = parse_json_body()
        except JsonRequestError as error:
            return jsonify({'error': str(error)}), 400

        release = data.get('release') or {}
        track = data.get('track') or {}
        updated_release = data_repository.add_track_to_favourites(release.get('release_id'), track.get('position'))
        if updated_release is None:
            return jsonify({'error': 'Release or track not found'}), 404
        return jsonify(updated_release), 200

    return library_api