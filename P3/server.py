import socket

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(('localhost', 8000))

while True:
    data, addr = server_socket.recvfrom(1024)
    print(f"Received message: {data.decode()} from {addr}")
    