import socket, SocketTCP

address = ('localhost', 8000)

server_socketTCP = SocketTCP.SocketTCP()
server_socketTCP.bind(address)
connection_socketTCP, new_address = server_socketTCP.accept()

while True:
    data, addr = connection_socketTCP.udp_socket.recvfrom(2 + 1 + 16)
    print(f"Received message: {data.decode()} from {addr}")
    