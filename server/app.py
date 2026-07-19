from flask import Flask, request, jsonify
import importlib
import importlib.util
import threading
import sys
from flask_cors import CORS
from ratelimit import limits, sleep_and_retry
import requests
import re
try:
    import keyboard as kb
    KEYBOARD_AVAILABLE = True
except (ImportError, OSError) as e:
    print(f"Warning: keyboard module not available: {e}")
    print("Keyboard shortcuts will be disabled.")
    kb = None
    KEYBOARD_AVAILABLE = False
import logging
from dotenv import load_dotenv
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor

try:
    from api.ai import create_ai_api
    from api.chat import create_chat_api
    from api.compat import create_compat_api
    from api.images import create_images_api
    from api.imports import create_imports_api
    from api.library import create_library_api
    from api.playback import create_playback_api
    from playback.runtime import PlaybackRuntime
    from repository.local import LocalDataRepository
    from recommendation.engine import RecommendationEngine
    from services.ai import MusicAnalysisService
    from sony.slink import SLinkClient, duration_to_seconds as slink_duration_to_seconds
except ImportError:
    from server.api.ai import create_ai_api
    from server.api.chat import create_chat_api
    from server.api.compat import create_compat_api
    from server.api.images import create_images_api
    from server.api.imports import create_imports_api
    from server.api.library import create_library_api
    from server.api.playback import create_playback_api
    from server.playback.runtime import PlaybackRuntime
    from server.repository.local import LocalDataRepository
    from server.recommendation.engine import RecommendationEngine
    from server.services.ai import MusicAnalysisService
    from server.sony.slink import SLinkClient, duration_to_seconds as slink_duration_to_seconds

try:
    from server.websocket.routes import create_playback_socket
except ImportError:
    websocket_routes_path = os.path.join(os.path.dirname(__file__), 'websocket', 'routes.py')
    websocket_routes_spec = importlib.util.spec_from_file_location('discogs_runtime_websocket_routes', websocket_routes_path)
    websocket_routes_module = importlib.util.module_from_spec(websocket_routes_spec)
    websocket_routes_spec.loader.exec_module(websocket_routes_module)
    create_playback_socket = websocket_routes_module.create_playback_socket

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

def load_environment():
    server_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(server_dir)
    for env_path in (os.path.join(repo_root, '.env'), os.path.join(server_dir, '.env')):
        load_dotenv(env_path, override=False)


load_environment()
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
USE_KODI = False
PLAYBACK_ADVANCE_LEAD_SECONDS = int(os.getenv('PLAYBACK_ADVANCE_LEAD_SECONDS', '3'))
CHANGER_LOAD_BASE_SECONDS = float(os.getenv('CHANGER_LOAD_BASE_SECONDS', '4'))
CHANGER_LOAD_SECONDS_PER_SLOT = float(os.getenv('CHANGER_LOAD_SECONDS_PER_SLOT', '0.08'))
CHANGER_LOAD_MAX_SECONDS = float(os.getenv('CHANGER_LOAD_MAX_SECONDS', '35'))
PLAYBACK_START_OFFSET_SECONDS = float(os.getenv('PLAYBACK_START_OFFSET_SECONDS', '1'))
PLAYBACK_STATE_PATH = os.getenv('PLAYBACK_STATE_PATH', os.path.join('server', 'playback_state.json'))
CHANGER_INITIAL_DECK = os.getenv('CHANGER_INITIAL_DECK')
CHANGER_INITIAL_CD = os.getenv('CHANGER_INITIAL_CD')

slink_client = SLinkClient(SONY_SLINK_SERVER)
data_repository = LocalDataRepository()
playback_runtime = PlaybackRuntime(
    slink_client,
    advance_lead_seconds=PLAYBACK_ADVANCE_LEAD_SECONDS,
    changer_load_base_seconds=CHANGER_LOAD_BASE_SECONDS,
    changer_load_seconds_per_slot=CHANGER_LOAD_SECONDS_PER_SLOT,
    changer_load_max_seconds=CHANGER_LOAD_MAX_SECONDS,
    playback_start_offset_seconds=PLAYBACK_START_OFFSET_SECONDS,
    persistence_path=PLAYBACK_STATE_PATH,
    adjacent_track_resolver=lambda current_track, direction: resolve_adjacent_release_track(current_track, direction),
    changer_initial_deck=CHANGER_INITIAL_DECK,
    changer_initial_cd=CHANGER_INITIAL_CD,
)
music_analysis_service = MusicAnalysisService(data_repository)

kodi_music_videos = []
recommendation_engine = RecommendationEngine(data_repository.all_releases())
app.register_blueprint(create_library_api(data_repository))
app.register_blueprint(create_ai_api(data_repository, music_analysis_service))
app.register_blueprint(create_chat_api(data_repository, playback_runtime))
app.register_blueprint(create_compat_api(lambda: playback_runtime))
app.register_blueprint(create_playback_api(playback_runtime, recommendation_engine))
create_playback_socket(app, playback_runtime, playback_runtime.event_hub)

# Constants for rate limiting
CALLS = 55
PERIOD = 60
# Youtube support
# THIS MIGHT BE BUG AS PLAYERID MIGHT BE DIFFERENT
player_id = 1
player_new_video = True

# Event object to signal the thread to stop
stop_event = threading.Event()
webhookExecutor = ThreadPoolExecutor(max_workers=2)

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

app.register_blueprint(create_imports_api(data_repository, lambda url: call_discogs_api(url, stream=False)))
app.register_blueprint(create_images_api(data_repository, FRONTEND, call_discogs_api_binary))

def slinkSend(slink_data):
    return slink_client.send(slink_data)

def slinkPlaylist(playlist):
    response = slink_client.send_playlist(playlist)
    # Check the response
    if response.status_code == 200:
        return jsonify({"status": "Playlist sent successfully"}), 200
    else:
        return jsonify(error=f"Failed to send playlist: {response.status_code} - {response.text}"), 500

def convert_duration_to_seconds(duration):
    return slink_duration_to_seconds(duration)

def slinkTrack(track):
    response = slink_client.send_track(track)
    # Check the response
    if response.status_code == 200:
        return jsonify({"status": "Track sent successfully"}), 200
    else:
        return jsonify(error=f"Failed to send track: {response.status_code} - {response.text}"), 500

def process_webhook(data):
    data = data or {}
    print(data)

    status = data.get('status', '')
    if status:
        if status == 'PLAY':
            observed_track = resolve_observed_play_track(data)
            if observed_track:
                playback_runtime.observe_track(observed_track)
            else:
                playback_runtime.handle_transport_status(status, data)
        else:
            playback_runtime.handle_transport_status(status, data)

    if not USE_KODI:
        print('Kodi is disabled.')
        return 'OK', 200

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
            #cd_position = cd 
            cd_position =  int(data.get('cd', 1), 0)   
        track_position = track

        print(f"Playing track {track} from CD {cd} on device {device} with duration {duration} seconds.")

        deck_number = 1
        if (device == 146):
            deck_number = 2
        if (device == 340):
            deck_number = 2    

        print('CD position:', cd_position)
        print('Track position:', track_position)
        print('Deck number:', deck_number)
        try:
            matching_track = data_repository.find_releases_by_deck_cd(deck_number, cd_position)
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
            matching_track = data_repository.find_releases_by_deck_cd(deck_number, cd_position)
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

def resolve_observed_play_track(data):
    try:
        device = parse_slink_byte(data.get('device'), 0x98)
        encoded_cd = parse_slink_byte(data.get('cd'), 1)
        track_position = decode_bcd_byte(parse_slink_byte(data.get('track'), 1))
        cd_position = decode_disc_position(device, encoded_cd)
        deck_number = decode_deck_number(device)
    except (TypeError, ValueError):
        return None

    releases = data_repository.find_releases_by_deck_cd(deck_number, cd_position)
    if not releases:
        return None

    release = releases[0]
    matching_track = find_release_track(release, track_position)
    if matching_track is None:
        return None

    return release_track_payload(release, matching_track, deck_number, cd_position)

def resolve_adjacent_release_track(current_track, direction):
    try:
        deck_number = int(current_track.get('deck_number') or 1)
        cd_position = int(current_track.get('cd_position'))
    except (AttributeError, TypeError, ValueError):
        return None

    releases = data_repository.find_releases_by_deck_cd(deck_number, cd_position)
    if not releases:
        return None

    release = releases[0]
    tracks = [track for track in release.get('tracklist') or [] if track.get('type_', 'track') == 'track']
    current_position = str(current_track.get('position'))
    current_index = next((index for index, track in enumerate(tracks) if str(track.get('position')) == current_position), None)
    if current_index is None:
        return None

    target_index = current_index + (1 if direction == 'next' else -1)
    if target_index < 0 or target_index >= len(tracks):
        return None
    return release_track_payload(release, tracks[target_index], deck_number, cd_position)

def release_track_payload(release, track, deck_number, cd_position):
    artist = release.get('artists_sort', 'Unknown Artist')
    if artist == 'Various' and track.get('artists'):
        artist = track['artists'][0].get('name', artist)

    payload = dict(track)
    payload['release_id'] = release.get('release_id')
    payload['deck_number'] = deck_number
    payload['cd_position'] = cd_position
    payload['artist'] = artist
    payload['full_name'] = f"{artist} - {payload.get('title', '')}"
    payload['album_title'] = release.get('title')
    payload['artwork_url'] = primary_image_url(release)
    return payload

def primary_image_url(release):
    images = release.get('images') or []
    image = next((item for item in images if item.get('type') == 'primary'), None)
    if image is None:
        image = next((item for item in images if item.get('type') == 'secondary'), None)
    if image is None and images:
        image = images[0]
    if image is None:
        return None
    return image.get('primary_image') or image.get('uri')

def parse_slink_byte(value, default):
    if value is None or value == '':
        return default
    if isinstance(value, int):
        return value
    return int(str(value), 16)

def decode_bcd_byte(value):
    return ((value >> 4) * 10) + (value & 0x0F)

def decode_disc_position(device, encoded_cd):
    if device in (0x9B, 0x9C, 0x9D):
        return encoded_cd + 200
    if encoded_cd >= 0x9A:
        return encoded_cd - 54
    return decode_bcd_byte(encoded_cd)

def decode_deck_number(device):
    if device in (0x99, 0x9C, 0x91, 0x94):
        return 2
    if device in (0x9A, 0x9D, 0x92, 0x95):
        return 3
    return 1

def find_release_track(release, track_position):
    search_positions = [str(track_position)]
    if release.get('format_quantity', 1) and int(release.get('format_quantity', 1)) > 1:
        search_positions.append(f"1-{track_position}")

    match = re.search(r'\(CD (\d+)\)$', release.get('title', ''))
    if match:
        search_positions.append(f"{int(match.group(1))}-{track_position}")

    for search_position in search_positions:
        for track in release.get('tracklist') or []:
            if track.get('position') == search_position:
                return track
    return None

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json() or {}
    webhookExecutor.submit(process_webhook, data)
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
    try:
        response = requests.post(url=f"{TV_API_HTTP}/jsonrpc", headers=headers, auth=auth, data=json.dumps(payload))
        response.raise_for_status()  # Raises a HTTPError if the response was unsuccessful
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
    else:
        kodi_music_videos = response.json().get('result', {}).get('musicvideos', [])

        # Step 2: Print Music Videos on Console
        for video in kodi_music_videos:
            try:
                print(f"id: {video['musicvideoid']}, Title: {video['title']}, Artist: {video['artist'][0] if video['artist'] else 'Unknown'}, Year: {video.get('year', 'Unknown')}")
            except KeyError as e:
                print(f"KeyError: {e} not found in video")
               

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
    updated_video = data_repository.ensure_video_offset(selectedVideo['title'], selectedVideo['artist'])

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
        existing_video = data_repository.find_video_offset_by_alias(input_title)
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
def loadMusicVideoOnKodi():
    global kodi_music_videos

    musicvideoid = request.args.get('musicvideoid', type=int)
    if musicvideoid is None:
        printAllMusicVideos()
        return jsonify({'musicvideos': kodi_music_videos}), 200

    headers = {'Content-Type': 'application/json'}
    auth = (KODI_USER, KODI_PASSWORD)

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
    websocket_client = load_kodi_websocket_client()
    printAllMusicVideos()                        
    while not stop_event.is_set():  
        socket_app = websocket_client.WebSocketApp(
            "ws://{}:{}/jsonrpc".format(KODI_IP, KODI_WEBSOCKET_PORT),
            on_message=on_message,
        )
        socket_app.run_forever()
        if not stop_event.is_set():
            print("KODI WebSocket disconnected. Reconnecting...")
            time.sleep(10)  # Wait 10 seconds before attempting to reconnect
    print("KODI WebSocket thread stopping")

def load_kodi_websocket_client():
    server_dir = os.path.abspath(os.path.dirname(__file__))
    original_path = list(sys.path)
    try:
        sys.path = [path for path in sys.path if os.path.abspath(path or os.getcwd()) != server_dir]
        return importlib.import_module('websocket')
    finally:
        sys.path = original_path

def on_press(event):
    if event is not None and getattr(event, 'name', None) == 'q':
        stop_event.set()


if __name__ == '__main__':

    # Initialize the keyboard hook (only if available)
    if KEYBOARD_AVAILABLE:
        try:
            kb.on_press(on_press)
            print("Keyboard hook initialized. Press 'q' to stop.")
        except Exception as e:
            print(f"Warning: Could not initialize keyboard hook: {e}")
            KEYBOARD_AVAILABLE = False
    else:
        print("Keyboard hook disabled. Use Ctrl+C to stop.")
    t1 = None
    t2 = None

    try:
        # Start the continuous recording thread
        #t1 = threading.Thread(target=continuous_recording, daemon=False)
        #t1.start()

        if USE_KODI:
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
        # Unhook keyboard listener (only if it was initialized)
        if KEYBOARD_AVAILABLE:
            try:
                kb.unhook_all()
            except Exception:
                pass
        stop_event.set()
        #t1.join()
        #t2.join()

        print("All threads and listeners stopped.")
    
