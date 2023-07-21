# tcp_server.py

import socket

def start_tcp_server():
    # Create a TCP socket
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.bind(("localhost", 12345))
    tcp_socket.listen(1)

    print("TCP server started. Listening on port 12345.")

    # Accept incoming connections and receive data
    while True:
        client_socket, client_address = tcp_socket.accept()
        print(f"Connection from {client_address}")
        data = client_socket.recv(1024)
        print(f"Received data: {data.decode('utf-8')}")
        client_socket.close()

if __name__ == "__main__":
    start_tcp_server()
