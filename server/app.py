from flask import Flask, request, jsonify, abort, send_from_directory
import threading
from types import SimpleNamespace
from flask_cors import CORS
from pysondb import db
from ratelimit import limits, sleep_and_retry
from ratelimit.exception import RateLimitException
import requests
from urllib.error import HTTPError
import csv
import re
from pynput import keyboard
from io import BytesIO, StringIO
import logging
from dotenv import load_dotenv
import os
from PIL import Image
import cgi
import json
import time
import websocket
from concurrent.futures import ThreadPoolExecutor

try:
    from html import escape  # python 3.x
except ImportError:
    from cgi import escape  # python 2.x

try:
    from html import unescape  # python 3.4+
except ImportError:
    try:
        from html.parser import HTMLParser  # python 3.x (<3.4)
    except ImportError:
        from HTMLParser import HTMLParser  # python 2.x
    unescape = HTMLParser().unescape
    
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
FRONTEND = os.getenv('FRONTEND')
TV_API = os.getenv('TV_API')
TV_API_HTTP = os.getenv('TV_API_HTTP')
KODI_USER = os.getenv('KODI_USER')
KODI_PASSWORD = os.getenv('KODI_PASSWORD')
KODI_IP = '192.168.1.123'
KODI_PORT = 8080 
KODI_WEBSOCKET_PORT = 9090

kodi_music_videos = []
playlist_db = db.getDb("playlists.json")
json_db = db.getDb("discogs_data_all.json")
video_offsets_db = db.getDb("video_offsets.json")
schema = None

# Constants for rate limiting
CALLS = 55
PERIOD = 60
# Youtube support
# THIS MIGHT BE BUG AS PLAYERID MIGHT BE DIFFERENT
player_id = 1
player_new_video = True

# Event object to signal the thread to stop
stop_event = threading.Event()
file_lock = threading.Lock()
executor = ThreadPoolExecutor(1)  # Create a thread pool with one worker thread

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
    deck_number = request.args.get('deck_number', type=int, default=1)
    print(request.files)
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    csv_file = StringIO(file.read().decode('utf-8'))
    csv_reader = csv.reader(csv_file, delimiter = ';')

    last_discogs_url = None
    cd_position = 1

    for line_number, row in enumerate(csv_reader, start=1):
        #if line_number == 1:  # Skip header row if present
        #    continue
        discogs_url = row[0]

        # Check if the current line is a duplicate of the last one
        if discogs_url == last_discogs_url:
            print(f"Duplicate URL found and skipped: {discogs_url}")
            continue

        # Update the last processed URL
        last_discogs_url = discogs_url

        match = re.search(r'/release/(\d+)', discogs_url)
        if match:
            release_id = int(match.group(1))
            #try:
            data = get_or_create_release(deck_number, cd_position, release_id)
            # Increment cd_position since it's a new, non-duplicate line
            # Assuming 'qty' is a key in the first dictionary of the 'formats' list
            qty = 1
            if 'format_quantity' in data:
                qty = data['format_quantity']
                if not isinstance(qty, int):
                    # Convert qty to integer
                    qty = int(qty)
                    #print(qty)
            else:
                print("qty not found in the data")

            if qty == 1:
                cd_position += 1

            original_title = data['title']

            for i in range(qty - 1):
                if 'tracklist' in data and data['tracklist'] and data['tracklist'][0]['title'].startswith("DVD"):
                    continue
                cd_position += 1
                data['cd_position'] = cd_position
                data['title'] = original_title + " (CD " + str(i+2) + ")"
                if not json_db.getByQuery({"title": data['title']}):
                    insert_to_db(data)

            if qty != 1:
                cd_position += 1    
            #except Exception as e:
            #    print(f"Failed to process release ID {release_id}: {e}")
            #    continue
        else:
            print(f"No release ID found in URL {discogs_url}")

    return jsonify({"status": "Import completed"}), 200

def custom_object_hook(d):
    """
    Recursively convert dictionary objects to SimpleNamespace objects.
    """
    for k, v in d.items():
        if isinstance(v, dict):
            d[k] = custom_object_hook(v)
    return SimpleNamespace(**d)

@app.route('/favourite', methods=['POST'])
def add_to_favourites():
    data = json.loads(request.data, object_hook=custom_object_hook)
    in_release = data.release
    in_track = data.track

    print(in_release.release_id)
    print(in_track.position)

    release = json_db.getByQuery({"release_id": in_release.release_id})[0]

    print(release['tracklist'])

    if release:
        # Find the track by position
        track = next((t for t in release['tracklist'] if t['position'] == in_track.position), None)

        if track:
            # Update the _score of the track
            track['_score'] = 1

            # Update the release in the database
            json_db.updateById(release['id'], release)

    # Return the release data from JSON storage
    return jsonify(release), 200

@app.route('/releases')
def get_all_releases():
    releases = json_db.getAll()
    
    # Return the release data from JSON storage
    return jsonify(releases), 200

def get_release_from_discogs(release_id):
    try:
        release_data = call_discogs_api(url=f"{DISCOGS_API_URL}{release_id}", stream=False)
        return release_data
    except RateLimitException as e:
        print("Rate limit exceeded: {}".format(e))
    except Exception as e:
        print("Error during API call: {}".format(e))

def insert_to_db(release_data):
    # Get the schema from the first entry in the database
    global schema
    if (schema == None):
        schema = json_db.getAll()[0].keys()
    
    # Ensure the new data conforms to the schema
    data_to_add = {key: release_data.get(key, None) for key in schema}
    
    # Add the data to the database
    json_db.add(data_to_add)            

def get_or_create_release(deck_number, cd_position, release_id):
    # Check if the release is in the database
    release = json_db.getByQuery({"release_id": release_id})
    
    if not release:
        # If not in the database, fetch from Discogs API
        release_data = get_release_from_discogs(release_id)
        if release_data:
            # Store the release data in the database
            release_data['deck_number'] = deck_number
            release_data['release_id'] = release_id
            release_data['cd_position'] = cd_position

            # Define the schema based on the first entry's keys
            if not json_db.getAll():  # If the database is empty, the first entry defines the schema
                json_db.add(release_data)
            else:
                insert_to_db(release_data)
        return release_data
    return release[0]

@app.route('/download-image', methods=['POST'])
def download_image():
    # Get the JSON data sent to the endpoint
    data = request.get_json()
    image_url = data.get('image_url')
    image_name = data.get('rename').replace('#','-csharp-') + ".jpeg"
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
        print("Downloading image...")
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
    local_image_url = f'{FRONTEND}/images/{image_name}'
    return jsonify({"url": escape(local_image_url)})

def send_request_with_retries(url, data, headers, max_retries=20, backoff_factor=1):
    retries = 0
    while retries < max_retries:
        try:
            response = requests.post(url, data=data, headers=headers)
            response.raise_for_status()  # This will raise an HTTPError if the HTTP request returned an unsuccessful status code
            return response
        except (HTTPError, ConnectionError, OSError) as e:
            retries += 1
            #wait_time = backoff_factor * (2 ** retries)
            wait_time = 0.1
            print(f"Connection error: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    raise Exception("Failed to send request after multiple retries.")    

@app.route('/playlists', methods=['GET'])
def playlists():
    playlist = playlist_db.getAll()
    return jsonify(playlist), 200

@app.route('/save-playlist', methods=['POST'])
def save_playlist():
    data = json.loads(request.data, object_hook=lambda d: SimpleNamespace(**d))
    print(data.name)

    playlist = playlist_db.getByQuery(query={"name": f"{data.name}"})
    if not playlist:
        playlist_db.add(json.loads(request.data))
    else:
        #playlist_db.updateById(playlist[0]["id"], playlist)
        playlist_db.updateByQuery({"name": data.name}, json.loads(request.data))

    return jsonify({"status": "Playlist sent"}), 200

@app.route('/playlist', methods=['POST'])
def playlist():
    data = json.loads(request.data)

    slinkPlaylist(data)
    slinkPlaylist(data)
    return jsonify({"status": "Playlist sent"}), 200    

def slinkSend(slink_data):
    # Convert the data to a JSON string
    #json_data = json.dumps(playlist)

    # Set the headers to inform the server that you are sending JSON
    headers = {'Content-Type': 'text/plain'}

    # Send the POST request
    #time.sleep(0.01)
    return send_request_with_retries(url=f"{SONY_SLINK_SERVER}", data=slink_data, headers=headers)    

def slinkPlaylist(playlist):
    slink_data = "PLAYLIST\r\n"
    cd_player_id = 90
    cd_operation_play = 50

    for track in playlist["tracks"]:
        
        track['position'] = process_position(track['position'])

        if 'deck_number' in track and track['deck_number'] == 2:
            cd_player_id = 92
        else:
            cd_player_id = 90

        if track['cd_position'] < 100:
            slink_data += f"{cd_player_id}{cd_operation_play}"
            slink_data += format_with_padding(track['cd_position'])
            slink_data += format_with_padding(track['position'])
        elif track['cd_position'] <= 200:
            slink_data += f"{cd_player_id}{cd_operation_play}"
            track['cd_position'] = hex(0x9A + (track['cd_position'] - 100))[2:]
            slink_data += format_with_padding(track['cd_position'])
            slink_data += format_with_padding(track['position'])
        else:    
            slink_data += f"{(cd_player_id+3)}{cd_operation_play}"
            track['cd_position'] = hex(int(track['cd_position']) - 200)[2:]
            slink_data += format_with_padding(track['cd_position'])
            slink_data += format_with_padding(track['position'])
            slink_data += format_with_padding(track["position"])

        slink_data += "\r\n"

    response = slinkSend(slink_data)
    # Check the response
    if response.status_code == 200:
        return jsonify({"status": "Playlist sent successfully"}), 200
    else:
        return jsonify(error=f"Failed to send playlist: {response.status_code} - {response.text}"), 500

@app.route('/track', methods=['POST'])
def track():
    # Parse the JSON data received from Angular
    track = json.loads(request.data, object_hook=lambda d: SimpleNamespace(**d))

    # Process the track as needed
    # Example: print track details
    print(f"! Received track: {track.title}, duration {track.duration}")

    slinkTrack(track)

    return jsonify({"status": "Track sent"}), 200

def convert_duration_to_seconds(duration):
    if duration == "":
        return 200
    minutes, seconds = map(int, duration.split(':'))
    total_seconds = minutes * 60 + seconds
    return total_seconds

def format_with_padding(value, pad_length=2):
    if isinstance(value, int):
        return f"{value:0{pad_length}d}"
    elif isinstance(value, str) and value.isdigit():
        return f"{int(value):0{pad_length}d}"
    elif isinstance(value, str) and len(value) == 1:
        return '0' + value    
    else:
        return value

def process_position(position):
    # Split by '-' and take the second number if '-' is present
    if '-' in position:
        position = position.split('-')[1]

    # Remove non-numeric characters
    position = re.sub(r'\D', '', position)
    
    return position

def slinkTrack(track):
    slink_data = ""
    cd_player_id = 90
    cd_operation_play = 50

    slink_data = ""

    track.position = process_position(track.position)

    if hasattr(track, 'deck_number') and track.deck_number == 2:
        cd_player_id += 2

    if track.cd_position < 100:
        slink_data += f"{cd_player_id}{cd_operation_play}"
        slink_data += format_with_padding(track.cd_position)
        slink_data += format_with_padding(track.position)
    elif track.cd_position <= 200:
        slink_data += f"{cd_player_id}{cd_operation_play}"
        track.cd_position = hex(0x9A + (track.cd_position - 100))[2:]
        slink_data += format_with_padding(track.cd_position)
        slink_data += format_with_padding(track.position)
    else:    
        slink_data += f"{(cd_player_id+3)}{cd_operation_play}"
        track.cd_position = hex(int(track.cd_position) - 200)[2:]
        slink_data += format_with_padding(track.cd_position)
        slink_data += format_with_padding(track.position)
 
    slink_data += "\r\n"

    print(slink_data)

    response = slinkSend(slink_data)
    # Check the response
    if response.status_code == 200:
        return jsonify({"status": "Track sent successfully"}), 200
    else:
        return jsonify(error=f"Failed to send track: {response.status_code} - {response.text}"), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print(data)

    status = data.get('status', '')

    if status == 'PLAY':
        headers = {'Content-Type': 'application/json'}
        track = int(data.get('track', 1), 16)
        duration = int(data.get('duration', 0))
        cd = int(data.get('cd', 1), 16)
        device = int(data.get('device', 98), 16)
        
        if (cd == 147):
            cd_position = cd+200
        elif (cd >= 201):
            cd_position = cd-54
        else:
            cd_position = cd    
        track_position = track

        print(f"Playing track {track} from CD {cd} on device {device} with duration {duration} seconds.")

        deck_number = 1
        if (device == 146):
            deck_number = 2

        print('CD position:', cd_position)
        print('Track position:', track_position)
        print('Deck number:', deck_number)
        try:
            matching_track = json_db.getByQuery({"cd_position": cd_position, "deck_number":deck_number})
            if (matching_track):
                matching_track = matching_track[0]
                # Extract the number from the title if it ends with "(CD X)"
                search_track = str(track_position)
                if 'format_quantity' in matching_track:
                    qty = matching_track['format_quantity']
                    if not isinstance(qty, int):
                        # Convert qty to integer
                        qty = int(qty)
                        print(qty)
                    if (qty > 1):    
                        search_track = str(1) + "-" + str(track_position)    
                    match = re.search(r'\(CD (\d+)\)$', matching_track['title'])
                    if match:
                        cd_number = int(match.group(1))
                        search_track = str(cd_number) + "-" + str(track_position)
                        print('CD Number:', cd_number)
                tracklist_position_match = [track for track in matching_track['tracklist'] if track['position'] == str(search_track)]
                # if match and not tracklist_position_match:
                #     cd_number = int(match.group(1))
                #     search_track = "CD" + str(cd_number) + "-" + str(track_position)
                #     print('CD Number:', cd_number)   
                #     tracklist_position_match = [track for track in matching_track['tracklist'] if track['position'] == str(search_track)]
                # if match and not tracklist_position_match:
                #     cd_number = int(match.group(1))
                #     search_track = str(cd_number) + "." + "{:02}".format(str(track_position))
                #     print('CD Number:', cd_number)   
                #     tracklist_position_match = [track for track in matching_track['tracklist'] if track['position'] == str(search_track)]
                print(matching_track)
                if tracklist_position_match:
                    print('Matching track in tracklist:', tracklist_position_match[0])
                    artist = matching_track['artists_sort']
                    title = tracklist_position_match[0]['title']
                    duration = tracklist_position_match[0]['duration']

                    data = {}
                    data['artist'] = artist
                    data['track'] = title
                    data['duration'] = convert_duration_to_seconds(duration)
                    data['current_time'] = 0
                    #response = requests.post(url=f"{TV_API}/youtube", json=data, headers=headers)
                    response = onCdPlayerStarted(artist, title, convert_duration_to_seconds(duration)) 
                    print(response)
                else:
                    print('No matching track in tracklist.')
        except ConnectionError:
            print('TV API Youtube is offline.')            
        except IndexError:
            print('No matching track found.')
    if status == 'PREPARE_TRACK':
        slink_data = data.get('track', '')
        
        # Split slink_data into pairs of HEX strings
        hex_pairs = [slink_data[i:i+2] for i in range(0, len(slink_data), 2)]
        
        # Decode each HEX pair individually
        decoded_data = [int(pair, 16) for pair in hex_pairs]

        print('Hex data:', hex_pairs)
        print('Dec data:', decoded_data)
        
        if (decoded_data[0] == 147):
            cd_position = decoded_data[2]+200
        elif (decoded_data[2] >= 201):
            cd_position = decoded_data[2]-54
        else:
            cd_position = int(hex_pairs[2])    
        track_position = int(hex_pairs[3])

        deck_number = 1
        if (decoded_data[0] == 146):
            deck_number = 2

        print('CD position:', cd_position)
        print('Track position:', track_position)
        print('Deck number:', deck_number)
        try:
            matching_track = json_db.getByQuery({"cd_position": cd_position, "deck_number":deck_number})
            if (matching_track):
                matching_track = matching_track[0]
                # Extract the number from the title if it ends with "(CD X)"
                search_track = str(track_position)
                if 'format_quantity' in matching_track:
                    qty = matching_track['format_quantity']
                    if not isinstance(qty, int):
                        # Convert qty to integer
                        qty = int(qty)
                        print(qty)
                    if (qty > 1):    
                        search_track = str(1) + "-" + str(track_position)    
                    match = re.search(r'\(CD (\d+)\)$', matching_track['title'])
                    if match:
                        cd_number = int(match.group(1))
                        search_track = str(cd_number) + "-" + str(track_position)
                        print('CD Number:', cd_number)
                tracklist_position_match = [track for track in matching_track['tracklist'] if track['position'] == str(search_track)]
                #print(matching_track)
                if tracklist_position_match:
                    print('=====================================')
                    print('Matching track in tracklist:', tracklist_position_match[0])
                    artist = matching_track['artists_sort']
                    title = tracklist_position_match[0]['title']
                    duration = tracklist_position_match[0]['duration']
                    headers = {'Content-Type': 'application/json'}
                    data = {}
                    data['artist'] = artist
                    data['track'] = title
                    data['duration'] = convert_duration_to_seconds(duration)
                    data['current_time'] = 0
                    #response = requests.post(url=f"{TV_API}/youtube", json=data, headers=headers)
                    # LOAD VIDEO AND PAUSE

                    response = tryToPlayMusicVideoOnKodi(artist, title, convert_duration_to_seconds(duration)) 
                    print(response)
                else:
                    print('No matching track in tracklist.')
        except ConnectionError:
            print('TV API Youtube is offline.')            
        except IndexError:
            print('No matching track found.')
    return 'OK', 200

def printAllMusicVideos():
    global kodi_music_videos

    # Step 1: Fetch Music Videos
    payload = {
        "jsonrpc": "2.0",
        "method": "VideoLibrary.GetMusicVideos",
        "params": {
            "properties": ["title", "artist", "year", "file"]
        },
        "id": 1
    }
    headers = {
        'Content-Type': 'application/json',
    }
    auth = (KODI_USER, KODI_PASSWORD)
    response = requests.post(url=f"{TV_API_HTTP}/jsonrpc", headers=headers, auth=auth, data=json.dumps(payload))

    kodi_music_videos = response.json().get('result', {}).get('musicvideos', [])

    # Step 2: Print Music Videos on Console
    for video in kodi_music_videos:
        print(f"id: {video['musicvideoid']}, Title: {video['title']}, Artist: {video['artist'][0] if video['artist'] else 'Unknown'}, Year: {video.get('year', 'Unknown')}")

    #return jsonify(kodi_music_videos)

# Function to send JSON-RPC requests to Kodi
def send_jsonrpc_request(method, params={}, id=1):
    url = "http://{}:{}/jsonrpc".format(KODI_IP, KODI_PORT)
    headers = {'content-type': 'application/json'}    
    auth = (KODI_USER, KODI_PASSWORD)
    # Prepare the payload to play the YouTube video
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": id
    }

    response = requests.post(url, data=json.dumps(payload), headers=headers, auth=auth)
    #response = requests.post(url, json=payload)
    return response.json()

def play():
    result = send_jsonrpc_request("Player.PlayPause", {
        "playerid": player_id,
        "play": True
    }) 
    print(jsonify(result)) 

def pause():
    result = send_jsonrpc_request("Player.PlayPause", {
        "playerid": player_id,
        "play": False
    })  

def onCdPlayerStarted(artist, title, duration):
    global player_new_video

    #if player_new_video == False:
    player_new_video = True
    play()

    return 'OK', 200   

def jumpToZero():
    new_time = {
        "time": {
            "hours": 0,
            "minutes": 0,
            "seconds": 0,
            "milliseconds": 0
        }
    }  

    # Seek to new time
    result = send_jsonrpc_request("Player.Seek", {
        "playerid": player_id,
        "value": new_time
    })    
    if "error" in result:
        # Seek to new time
        result = send_jsonrpc_request("Player.Seek", {
            "playerid": player_id,
            "value": new_time
        })  

def jumpToStart(selectedVideo):
    # Check if the video already exists in the database
    existing_video = video_offsets_db.getBy({"title": selectedVideo['title'], "artist": selectedVideo['artist']})

    if not existing_video:
        # If the video does not exist, insert a new record
        video_offsets_db.add({
            'title': selectedVideo['title'],
            'artist': selectedVideo['artist'],
            'videos_offsets': [0, 0, 0],
            'alias': ''
        })

    # Get the updated video record
    updated_video = video_offsets_db.getBy({"title": selectedVideo['title'], "artist": selectedVideo['artist']})[0]

    new_time = {
        "time": {
            "hours": 0,
            "minutes": updated_video['videos_offsets'][0],
            "seconds": updated_video['videos_offsets'][1],
            "milliseconds": updated_video['videos_offsets'][2]
        }
    }  

    # Seek to new time
    result = send_jsonrpc_request("Player.Seek", {
        "playerid": player_id,
        "value": new_time
    })    
    if "error" in result:
        # Seek to new time
        result = send_jsonrpc_request("Player.Seek", {
            "playerid": player_id,
            "value": new_time
        })  


def tryToPlayMusicVideoOnKodi(artist, title, duration):
    global kodi_music_videos

    # Step 1: Find the Music Video
    musicvideoid = None
    selectedVideo = None
    for video in kodi_music_videos:
        video_title = video['title'].lower()
        video_artist = video['artist'][0].lower()
        input_title = title.lower()
        input_artist = artist.lower()

        # override by alias if needed
        print(f"Searching by alias: {input_title}")
        existing_video = video_offsets_db.getBy({"alias": input_title})
        if existing_video:
            input_title = existing_video['title'].lower()
            input_artist = existing_video['artist'].lower()

        video_title_words = video_title.split()
        video_artist_words = video_artist.split()
        input_title_words = input_title.split()
        input_artist_words = input_artist.split()

        title_similarity = len(set(video_title_words) & set(input_title_words))
        artist_similarity = len(set(video_artist_words) & set(input_artist_words))

        #if title_similarity >= len(video_title_words) * 0.5 and artist_similarity >= len(video_artist_words) * 0.5:
      
        if title_similarity >= len(video_title_words):
            selectedVideo = video
            musicvideoid = video['musicvideoid']
            break

    # Step 2: Play the Music Video
    if musicvideoid:
        headers = {'Content-Type': 'application/json'}
        play_payload = {
            "jsonrpc": "2.0",
            "method": "Player.Open",
            "params": {
                "item": {"musicvideoid": musicvideoid}
            },
            "id": 1
        }
        headers = {'Content-Type': 'application/json'}
        auth = (KODI_USER, KODI_PASSWORD)
        print(f"Playing music video: {title} by {artist} with duration {duration} seconds.")
        print(f"Music Video ID: {musicvideoid}")
        player_new_video = False
        response = requests.post(url=f"{TV_API_HTTP}/jsonrpc", headers=headers, auth=auth, data=json.dumps(play_payload))
        jumpToZero()

        jumpToStart(selectedVideo)
        pause()
        #jumpToStart(selectedVideo)
        #pause()

        return jsonify(response.json()), 200
    else:
        return jsonify(error="Music video not found on Kodi"), 404

@app.route('/load_music_videos', methods=['GET'])
def loadMusicVideoOnKodi(musicvideoid):
    global kodi_music_videos

    headers = {'Content-Type': 'application/json'}

    play_payload = {
        "jsonrpc": "2.0",
        "method": "Player.Open",
        "params": {
            "item": {"musicvideoid": musicvideoid},
            "options": {"startoffset": 1}
        },
        "id": 1
    }
    response = requests.post(url=f"{TV_API_HTTP}/jsonrpc", headers=headers, auth=auth, data=json.dumps(play_payload))
 
    return jsonify(response.json()), 200

@app.route('/images/<filename>', methods=['GET'])
def uploaded_file(filename):
    return send_from_directory('../downloaded_images', unescape(filename.replace('-csharp-','#')), as_attachment=False)


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify(error="rate limit exceeded"), 429

@app.errorhandler(500)
def internal_error_handler(e):
    return jsonify(error="internal server error"), 500

@app.errorhandler(Exception)
def global_exception_handler(e):
    return jsonify(error=str(e)), 500

def getPlayerId():
    global player_id

    if player_id == -1:
        result = send_jsonrpc_request("Player.GetActivePlayers")
        print("getPlayerId")
        print(unidecode.unidecode(json.dumps(result,ensure_ascii = False)))
        player_id = result['result'][0]['playerid']        

def on_message(ws, message):
    global player_id, player_new_video

    data = json.loads(message)

    if 'method' in data:
        print(data['method'])
        if data['method'] == 'Playlist.OnAdd' or data['method'] == 'Player.onAVStart':
            print(f"pausing new video if player_new_video is true: player_new_video={player_new_video}")
            if player_new_video:
                player_new_video = False
                getPlayerId()
                #time.sleep(1)
                result = send_jsonrpc_request("Player.PlayPause", {
                    "playerid": player_id,
                    "play": False
                }) 

                """new_time = {
                    "time": {
                        "hours": 0,
                        "minutes": 0,
                        "seconds": 1,
                        "milliseconds": 0
                    }
                }  

                result = send_jsonrpc_request("Player.Seek", {
                    "playerid": player_id,
                    "value": new_time
                })    

                result = send_jsonrpc_request("Player.Seek", {
                    "playerid": player_id,
                    "value": new_time
                })   """


# Start WebSocket in separate function
def start_websocket():
    ws = websocket.WebSocketApp("ws://{}:{}/jsonrpc".format(KODI_IP, KODI_WEBSOCKET_PORT),
                            on_message=on_message)

    printAllMusicVideos()                        
    while not stop_event.is_set():
        ws.run_forever()
        if not stop_event.is_set():
            time.sleep(10)  # Wait 10 seconds before attempting to reconnect
            print("WebSocket disconnected. Reconnecting...")
    print("WebSocket thread stopping")

def on_press(key):

    try:
        if key.char == 'q':
            stop_event.set()
    except AttributeError:
        pass


if __name__ == '__main__':


    # Initialize the keyboard listener
    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    t1 = None
    t2 = None

    try:
        # Start the continuous recording thread
        #t1 = threading.Thread(target=continuous_recording, daemon=False)
        #t1.start()

        t2 = threading.Thread(target=start_websocket, daemon=True)
        t2.start()

        # Run the Flask server
        app.run(host='0.0.0.0', port=5000)

        
        t1.join()
        #t2.join()
        # Start the key monitoring thread
        #t2= threading.Thread(target=key_monitor, daemon=True).start()
    except KeyboardInterrupt:
        print("CTRL+C pressed. Stopping all threads and listeners.")
    except Exception as e:
        print("An exception occurred: %g. Stopping all threads and listeners.", e)
    finally:
        # Stop the listener
        listener.stop()
        stop_event.set()
        #t1.join()
        #t2.join()

        print("All threads and listeners stopped.")
    
