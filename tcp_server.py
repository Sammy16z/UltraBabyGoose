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
        
        try:
            while True:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                print(f"Received data: {data.decode('utf-8')}")
        except Exception as e:
            print(f"Error receiving data from client: {e}")

        client_socket.close()

if __name__ == "__main__":
    start_tcp_server()
