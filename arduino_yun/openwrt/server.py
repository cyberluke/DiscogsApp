#!/usr/bin/env python
import sys
sys.path.insert(0, '/usr/lib/python2.7/bridge')
import socket
from bridgeclient import BridgeClient as bridgeclient

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

def handle_client(client_socket):
    request_data = receive_request(client_socket)
    print("Received Request:")
    print(request_data)

    headers = get_headers(request_data)
    content_length = int(headers.get('Content-Length', 0))

    # Find the start of the body
    body_start = request_data.find('\r\n\r\n') + 4
    body = request_data[body_start:body_start+content_length]

    print("Received Body:")
    print(body)

    # Here you would add the code to send the data to the Arduino Bridge
    # For example:
    bridge = bridgeclient()
    bridge.put('playlist', body)

    http_response = "HTTP/1.1 200 OK\r\n"
    http_response += "Content-Type: text/plain\r\n"
    http_response += "Connection: close\r\n\r\n"
    http_response += "Playlist received and sent to Arduino."
    
    client_socket.sendall(http_response)
    client_socket.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('', 8080))
    server_socket.listen(5)
    print("Listening on port 8080...")

    while True:
        client_socket, addr = server_socket.accept()
        print("Accepted connection from: {}:{}".format(addr[0], addr[1]))
        handle_client(client_socket)

if __name__ == '__main__':
    main()
