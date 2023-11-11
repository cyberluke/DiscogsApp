from flask import Flask, request, jsonify, abort, send_from_directory
from flask_cors import CORS
from pysondb import db
from ratelimit import limits, sleep_and_retry
from ratelimit.exception import RateLimitException
import requests
import csv
import re
from io import BytesIO, StringIO
import logging
from dotenv import load_dotenv
import os
from PIL import Image
import cgi

app = Flask(__name__)
CORS(app)

# These two lines enable debugging at httplib level (requests->urllib3->http.client)
# You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
# The only thing missing will be the response.body which is not logged.
try:
    import http.client as http_client
except ImportError:
    # Python 2
    import httplib as http_client
http_client.HTTPConnection.debuglevel = 1


# You must initialize logging, otherwise you'll not see debug output.
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

DISCOGS_API_URL = "https://api.discogs.com/releases/"
# Replace 'your_personal_access_token' with your actual Discogs PAT
load_dotenv()  # This loads the environment variables from .env
DISCOGS_TOKEN = os.getenv('DISCOGS_TOKEN')
SONY_SLINK_SERVER = os.getenv('SONY_SLINK_SERVER')
json_db = db.getDb("discogs_data_all.json")
playlist_db = db.getDb("playlists.json")

# Constants for rate limiting
CALLS = 55
PERIOD = 60

@sleep_and_retry
@limits(calls=CALLS, period=PERIOD)
def call_discogs_api(url, stream:False):
    headers = {
        'Authorization': f'Discogs token={DISCOGS_TOKEN}',
        'User-Agent': 'My Sony CDP-CX smart internet jukebox over Sony Control A1 SLink/1.0'  # Replace with your app's user-agent
    }
    response = requests.get(url, stream=stream, headers=headers)

    if response.status_code != 200:
        raise Exception('API response: {}'.format(response.status_code))
    return response.json()

@sleep_and_retry
@limits(calls=CALLS, period=PERIOD)
def call_discogs_api_binary(url, stream:False):
    headers = {
        'Authorization': f'Discogs token={DISCOGS_TOKEN}',
        'User-Agent': 'My Sony CDP-CX smart internet jukebox over Sony Control A1 SLink/1.0'  # Replace with your app's user-agent
    }
    response = requests.get(url, stream=stream, headers=headers)

    if response.status_code != 200:
        raise Exception('API response: {}'.format(response.status_code))
    return response

@app.route('/import-csv', methods=['POST'])
def import_csv():
    print(request.files)
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    csv_file = StringIO(file.read().decode('utf-8'))
    csv_reader = csv.reader(csv_file)

    last_discogs_url = None
    cd_position = 0

    for line_number, row in enumerate(csv_reader, start=1):
        #if line_number == 1:  # Skip header row if present
        #    continue
        discogs_url = row[0]

        # Check if the current line is a duplicate of the last one
        if discogs_url == last_discogs_url:
            print(f"Duplicate URL found and skipped: {discogs_url}")
            continue

        # Increment cd_position since it's a new, non-duplicate line
        cd_position += 1

        # Update the last processed URL
        last_discogs_url = discogs_url

        match = re.search(r'/release/(\d+)', discogs_url)
        if match:
            release_id = int(match.group(1))
            #try:
            release_data = get_or_create_release(cd_position, release_id)
            #except Exception as e:
            #    print(f"Failed to process release ID {release_id}: {e}")
            #    continue
        else:
            print(f"No release ID found in URL {discogs_url}")

    return jsonify({"status": "Import completed"}), 200

@app.route('/releases')
def get_all_releases():
    releases = json_db.getAll()
    
    # Return the release data from JSON storage
    return jsonify(releases), 200

def get_release_from_discogs(release_id):
    try:
        release_data = call_discogs_api(f"{DISCOGS_API_URL}{release_id}")
        return release_data
    except RateLimitException as e:
        print("Rate limit exceeded: {}".format(e))
    except Exception as e:
        print("Error during API call: {}".format(e))

def get_or_create_release(cd_position, release_id):
    # Check if the release is in the database
    release = json_db.getByQuery({"id": release_id})
    
    if not release:
        # If not in the database, fetch from Discogs API
        release_data = get_release_from_discogs(release_id)
        if release_data:
            # Store the release data in the database
            release_data['id'] = release_id
            release_data['cd_position'] = cd_position

            # Define the schema based on the first entry's keys
            if not json_db.getAll():  # If the database is empty, the first entry defines the schema
                json_db.add(release_data)
            else:
                # Get the schema from the first entry in the database
                schema = json_db.getAll()[0].keys()
                
                # Ensure the new data conforms to the schema
                data_to_add = {key: release_data.get(key, None) for key in schema}
                
                # Add the data to the database
                json_db.add(data_to_add)
        return release_data
    return release[0]

@app.route('/download-image', methods=['POST'])
def download_image():
    # Get the JSON data sent to the endpoint
    data = request.get_json()
    image_url = data.get('image_url')
    image_name = data.get('rename') + ".jpeg"
    local_folder = 'downloaded_images'

    if not image_url:
        return jsonify({"error": "No image URL provided."}), 400

    # Ensure the local_folder exists
    if not os.path.exists(local_folder):
        os.makedirs(local_folder)

    # Extract the image name from the URL
    #image_name = image_url.split('/')[-1]
    #header = response.info().getheader('Content-Disposition')
    #value, params = cgi.parse_header(header)
    #image_name = params['filename']

    # Create the path for the local image
    local_image_path = os.path.join(local_folder, image_name)

    # Check if the image already exists to avoid re-downloading
    if not os.path.isfile(local_image_path):
        # Get the image data using requests
        response = call_discogs_api_binary(image_url, stream=True)

        # Check if the request was successful
        if response.status_code == 200:
            # Open the local file for writing in binary mode
            i = Image.open(BytesIO(response.content))
            i.save(local_image_path)
        else:
            return jsonify({"error": "Failed to retrieve image."}), response.status_code

    # Return the path to the local image file
    local_image_url = f'http://localhost:5000/images/{image_name}'
    return jsonify({"url": local_image_url})

@app.route('/playlists', methods=['GET'])
def playlists():
    playlist = playlist_db.getAll()
    return jsonify(playlist), 200

@app.route('/playlist', methods=['POST'])
def playlist():
    print(request)
    playlist = playlist_db.getByQuery({"name": request.name})
    if not playlist:
        playlist_db.add(playlist)
        slinkPlay(playlist)
    else:
        #playlist_db.updateById(playlist[0]["id"], playlist)
        playlist_db.updateByQuery({"name": request.name}, playlist)
        slinkPlaylist(playlist)

    return jsonify({"status": "Playlist sent"}), 200

def slinkSend(slink_data):
    # Convert the data to a JSON string
    #json_data = json.dumps(playlist)

    # Set the headers to inform the server that you are sending JSON
    headers = {'Content-Type': 'text/plain'}

    # Send the POST request
    return requests.post(f"{SONY_SLINK_SERVER}", data=slink_data, headers=headers)    

def slinkPlaylist(playlist):
    slink_data = "PLAYLIST\r\n"
    cd_player_id = 60
    cd_operation_play = 50

    for track in playlist.tracks:
        slink_data += f"{cd_player_id}{cd_operation_play}" + f"{track.cd_position:02d}" + f"{track.position:02d}" + "\r\n"


    response = slinkSend(slink_data)
    # Check the response
    if response.status_code == 200:
        return jsonify({"status": "Playlist sent successfully"}), 200
    else:
        return jsonify(error=f"Failed to send playlist: {response.status_code} - {response.text}"), 500

@app.route('/track', methods=['POST'])
def track():
    print(request)

    slinkPlaylist(request)

    return jsonify({"status": "Track sent"}), 200

def slinkTrack(track):
    slink_data = ""
    cd_player_id = 60
    cd_operation_play = 50

    slink_data += f"{cd_player_id}{cd_operation_play}" + f"{track.cd_position:02d}" + f"{track.position:02d}" + "\r\n"

    response = slinkSend(slink_data)
    # Check the response
    if response.status_code == 200:
        return jsonify({"status": "Track sent successfully"}), 200
    else:
        return jsonify(error=f"Failed to send track: {response.status_code} - {response.text}"), 500

@app.route('/images/<filename>', methods=['GET'])
def uploaded_file(filename):
    return send_from_directory('../downloaded_images', filename)


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(error="rate limit exceeded"), 429

@app.errorhandler(500)
def internal_error_handler(e):
    return jsonify(error="internal server error"), 500

@app.errorhandler(Exception)
def global_exception_handler(e):
    return jsonify(error=str(e)), 500
