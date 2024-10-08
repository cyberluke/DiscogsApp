#!/usr/bin/env python
import sys
sys.path.insert(0, '/usr/lib/python2.7/bridge')
import socket
import time
from bridgeclient import BridgeClient as bridgeclient
import subprocess

class PlaylistHandler():
    client = bridgeclient()
    playlist = []
    current_index = 0
    start_time = None
    duration = None    

    def do_POST(self, lines):   
        print(lines[0])   
        if lines[0] == 'PLAYLIST':
            self.playlist = lines[1:]
            self.current_index = 0
            self.send_to_arduino(self.playlist[self.current_index])
            #self.current_index += 1
        else:
            self.playlist = []
            self.current_index = 0
            self.start_time = None
            self.duration = None    
            self.send_to_arduino(lines[0])


    def send_to_arduino(self, track):
        print("sending track to Arduino2")
        # bug
        self.client.put('playlist', track)
        self.client.put('playlist', track)

        self.send_webhook_prepare_next(track)

    def send_socket(self, json_body):    
        server_address = '192.168.1.122'
        server_port = 5000
        # Manually crafting the HTTP GET request with a body (unconventional use)
        request = "POST /webhook HTTP/1.1\r\n"
        request += "Host: 192.168.1.122:5000\r\n"
        request += "Content-Type: application/json\r\n"
        request += "Content-Length: " + str(len(json_body)) + "\r\n"
        request += "\r\n"  # Header and body should be separated by an extra newline
        request += json_body
        
        # Create a socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        try:
            # Connect to server
            sock.connect((server_address, server_port))
            
            # Send data
            sock.sendall(request.encode('utf-8'))
            
            # Look for the response
            response = sock.recv(4096)
            print("Response from server:", response.decode('utf-8'))
        
        except socket.error as e:
            print("Socket error:", e)
        
        finally:
            # Close the socket to clean up
            sock.close()    

    def send_webhook_prepare_next(self, track):
        # Convert the data dictionary to a JSON string
        json_body = '{"status":"PREPARE_TRACK", "track":"%s"}' % track.replace('"', '\\"')
        self.send_socket(json_body)

    def prepare_next_track(self, duration):
        print("prepare for next track")
        self.start_time = time.time()
        self.duration = duration

    def check_next_track(self):
        if self.start_time is not None:
            print(time.time() - self.start_time)
            if (time.time() - self.start_time) >= self.duration:
                self.next_track()       

    def next_track(self):
        print("next track check...timer works")
        if not self.playlist:
            return
        if self.current_index < len(self.playlist) - 1:
            print("next track check....ok")
            self.current_index += 1
        else:    
            self.current_index = 0

        self.start_time = None
        self.duration = None   
        self.send_to_arduino(self.playlist[self.current_index])

    def prev_track(self):
        print("prev track check...")
        if not self.playlist:
            return
        if self.current_index > 0:
            print("prev track check....ok")
            self.current_index -= 1  
        else:
            self.current_index = len(self.playlist) - 1

        self.start_time = None
        self.duration = None     
        self.send_to_arduino(self.playlist[self.current_index])
          

    def do_GET(self, path):
        path = path.split('/')
        print(path[1])
        print(len(path))
        if path[1] == 'playButton' and len(path) == 6:   
            print("play button")          
            # Convert the data dictionary to a JSON string
            json_body = '{"status":"PLAY", "device":"%s", "cd":"%s", "track":"%s", "duration":"%s"}' % (path[2].replace('"', '\\"'), path[3].replace('"', '\\"'), path[4].replace('"', '\\"'), path[5].replace('"', '\\"'))
            self.send_socket(json_body)
            subprocess.call(["reset-mcu"])
        elif path[1] == 'stop' and len(path) == 2:
            self.playlist = []
            self.current_index = 0
            self.start_time = None
            self.duration = None    
            print("stop")   
            json_body = '{"status":"STOP"}'
            self.send_socket(json_body) 
        elif path[1] == 'nextTrack' and len(path) == 2:
            print("nextTrack")
            self.next_track()
            json_body = '{"status":"NEXT_TRACK"}'
            self.send_socket(json_body) 
        elif path[1] == 'prevTrack' and len(path) == 2:     
            print("prevTrack")
            self.prev_track()      
            json_body = '{"status":"PREV_TRACK"}'
            self.send_socket(json_body)  
        elif path[1] == 'nextTrack' and len(path) == 3:
            print("nextTrack with duration")
            json_body = '{"status":"NEXT_TRACK_IN", "duration":"%s"}' % path[2].replace('"', '\\"')
            self.send_socket(json_body) 
            try:
                duration = int(path[2])
                print("found duration")
                print(duration)
                self.prepare_next_track(duration)
            except ValueError:
                print("valueerror")



playlistHandler = PlaylistHandler()

def get_headers(data):
    """Parse headers from HTTP request"""
    try:
        header_data = data.split('\r\n\r\n')[0]
        headers = {}
        for header_line in header_data.split('\r\n'):
            if ': ' in header_line:
                key, value = header_line.split(': ', 1)
                headers[key] = value
        return headers
    except IndexError:
        return {}

def receive_request(sock):
    """Receive the full request from the socket"""
    request_data = ''
    sock.settimeout(10)  # Set timeout to stop receiving if no data sent

    while True:
        try:
            part = sock.recv(1024)
            request_data += part
            if len(part) < 1024:
                # Either 0 or end of data
                break
        except socket.timeout:
            # No more data
            break

    return request_data

def parse_request_line(request_data):
    """Parse the request line from HTTP request"""
    request_line = request_data.split('\r\n')[0]
    parts = request_line.split(' ')
    if len(parts) >= 3:
        method, path, version = parts
        return method, path, version
    return None, None, None

def handle_client(client_socket):
    request_data = receive_request(client_socket)

    print("Received Request:")

    method, path, version = parse_request_line(request_data)
    print("Method:", method, "Path:", path, "Version:", version)

    headers = get_headers(request_data)
    print(headers)
    content_length = int(headers.get('Content-Length', 0))

    # Find the start of the body
    body_start = request_data.find('\r\n\r\n') + 4
    body = request_data[body_start:body_start+content_length]

    print("Received Body2:")
    print(len(body))

    http_response = "HTTP/1.1 200 OK\r\n"
    http_response += "Content-Type: text/plain\r\n"
    http_response += "Connection: close\r\n\r\n"

    if (body and len(body) > 0):
        # Here you would add the code to send the data to the Arduino Bridge
        # For example:
        #if path == '/':
        playlistHandler.do_POST(str(body).split('\r\n'))
        # bridge.put('playlist', str(body))
        http_response += "Playlist received and sent to Arduino."
    else:
        playlistHandler.do_GET(path)
        http_response += "Prepare next track for Arduino."
        
    client_socket.sendall(http_response)

    client_socket.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', 8080))
    server_socket.listen(5)
    print("Listening on port 8080...")

    while True:
        playlistHandler.check_next_track()
        # Non-blocking accept call
        server_socket.settimeout(0.1)
        try:
            client_socket, addr = server_socket.accept()
            print("Accepted connection from: {}:{}".format(addr[0], addr[1]))
            handle_client(client_socket)
        except socket.timeout:
            # No connection was made, continue the loop
            continue

if __name__ == '__main__':
    main()