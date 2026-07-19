from html import escape, unescape
from io import BytesIO
import os
import time

from flask import Blueprint, abort, current_app, jsonify, redirect, request, send_from_directory
from PIL import Image


def public_url(frontend_url: str | None, path: str) -> str:
    if not frontend_url:
        return path
    return frontend_url.rstrip('/') + path


def image_response(frontend_url: str | None, image_name: str):
    return jsonify({'url': escape(public_url(frontend_url, f'/images/{image_name}'))})


def default_image_response(data_repository, frontend_url: str | None):
    if os.path.isfile(data_repository.default_image_path):
        return jsonify({'url': escape(public_url(frontend_url, '/assets/default.png'))})
    return jsonify({'error': 'Image not found and default image unavailable'}), 404


def save_remote_image(fetch_binary, image_url: str, local_image_path: str) -> bool:
    response = fetch_binary(image_url, stream=True)
    if response.status_code != 200:
        current_app.logger.warning(f'Failed to download image from Discogs: {response.status_code}')
        return False

    image = Image.open(BytesIO(response.content))
    image.save(local_image_path)
    return True


def existing_image_filename(data_repository, filename: str) -> str | None:
    images_dir = data_repository.absolute_images_dir()
    filename_candidates = [
        unescape(filename),
        unescape(filename.replace('-csharp-', '#')),
    ]
    return next(
        (candidate for candidate in filename_candidates if os.path.isfile(os.path.join(images_dir, candidate))),
        None,
    )


def serve_default_image(data_repository, frontend_url: str | None):
    if os.path.isfile(data_repository.default_image_path):
        return redirect(public_url(frontend_url, '/assets/default.png'))

    assets_dir = data_repository.default_assets_dir()
    if os.path.isdir(assets_dir):
        for file_name in os.listdir(assets_dir):
            if file_name.lower().endswith('.png'):
                return redirect(public_url(frontend_url, f'/assets/{file_name}'))

    abort(404)


def handle_download_image(data_repository, frontend_url: str | None, fetch_binary):
    try:
        data = request.get_json() or {}
        if not data.get('rename'):
            return jsonify({'error': 'No image name provided.'}), 400

        image_name = data.get('rename').replace('#', '-csharp-') + '.jpeg'
        local_image_path = data_repository.image_path(image_name)

        if os.path.isfile(local_image_path):
            return image_response(frontend_url, image_name)

        if data.get('image_url'):
            data_repository.ensure_images_dir()
            try:
                if save_remote_image(fetch_binary, data['image_url'], local_image_path):
                    return image_response(frontend_url, image_name)
            except Exception as download_error:
                current_app.logger.error(f'Error downloading image from Discogs: {str(download_error)}')

        return default_image_response(data_repository, frontend_url)
    except Exception as exc:
        current_app.logger.error(f'Error in download_image: {str(exc)}')
        return jsonify({'error': f'Error processing image: {str(exc)}'}), 500


def handle_uploaded_file(data_repository, frontend_url: str | None, filename: str):
    try:
        images_dir = data_repository.absolute_images_dir()
        if not os.path.isdir(images_dir):
            return serve_default_image(data_repository, frontend_url)

        processed_filename = existing_image_filename(data_repository, filename)
        if processed_filename is None:
            return serve_default_image(data_repository, frontend_url)

        retry_delay = 0.1
        for attempt in range(3):
            try:
                return send_from_directory(images_dir, processed_filename, as_attachment=False)
            except OSError:
                if attempt == 2:
                    return serve_default_image(data_repository, frontend_url)
                time.sleep(retry_delay)
                retry_delay *= 2
    except Exception as exc:
        current_app.logger.error(f'Error in uploaded_file: {str(exc)}')

    return serve_default_image(data_repository, frontend_url)


def create_images_api(data_repository, frontend_url: str | None, fetch_binary) -> Blueprint:
    images_api = Blueprint('images_api', __name__)

    @images_api.route('/download-image', methods=['POST'])
    def download_image():
        return handle_download_image(data_repository, frontend_url, fetch_binary)

    @images_api.route('/images/<filename>', methods=['GET'])
    def uploaded_file(filename):
        return handle_uploaded_file(data_repository, frontend_url, filename)

    return images_api