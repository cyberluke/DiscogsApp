import csv
import logging
import re
from io import StringIO

from flask import Blueprint, jsonify, request


DISCOGS_API_URL = 'https://api.discogs.com/releases/'


def create_imports_api(data_repository, fetch_release) -> Blueprint:
    imports_api = Blueprint('imports_api', __name__)
    schema = None

    def insert_to_db(release_data):
        nonlocal schema
        if schema is None:
            schema = data_repository.all_releases()[0].keys()
        data_to_add = {key: release_data.get(key, None) for key in schema}
        data_repository.releases.add(data_to_add)

    def get_release_from_discogs(release_id):
        try:
            return fetch_release(f'{DISCOGS_API_URL}{release_id}')
        except Exception as exc:
            logging.warning(f'Error during Discogs API call: {exc}')
            return None

    def get_or_create_release(deck_number, cd_position, release_id):
        release = data_repository.find_release_by_id(release_id)
        if release:
            return release[0]

        release_data = get_release_from_discogs(release_id)
        if release_data:
            release_data['deck_number'] = deck_number
            release_data['release_id'] = release_id
            release_data['cd_position'] = cd_position
            if not data_repository.all_releases():
                data_repository.releases.add(release_data)
            else:
                insert_to_db(release_data)
        return release_data

    @imports_api.route('/import-csv', methods=['POST'])
    def import_csv():
        deck_number = request.args.get('deck_number', type=int, default=1)
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400

        csv_file = StringIO(file.read().decode('utf-8'))
        csv_reader = csv.reader(csv_file, delimiter=';')
        last_discogs_url = None
        cd_position = 1

        for row in csv_reader:
            discogs_url = row[0]
            if discogs_url == last_discogs_url:
                logging.info(f'Duplicate URL found and skipped: {discogs_url}')
                continue

            last_discogs_url = discogs_url
            match = re.search(r'/release/(\d+)', discogs_url)
            if not match:
                logging.warning(f'No release ID found in URL {discogs_url}')
                continue

            release_id = int(match.group(1))
            data = get_or_create_release(deck_number, cd_position, release_id)
            if not data:
                continue

            quantity = data.get('format_quantity', 1)
            if not isinstance(quantity, int):
                quantity = int(quantity)

            if quantity == 1:
                cd_position += 1

            original_title = data['title']
            for index in range(quantity - 1):
                if data.get('tracklist') and data['tracklist'][0]['title'].startswith('DVD'):
                    continue
                cd_position += 1
                data['cd_position'] = cd_position
                data['title'] = original_title + ' (CD ' + str(index + 2) + ')'
                if not data_repository.releases.getByQuery({'title': data['title']}):
                    insert_to_db(data)

            if quantity != 1:
                cd_position += 1

        return jsonify({'status': 'Import completed'}), 200

    return imports_api