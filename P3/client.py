import socket

# cliente que se comunica con udp
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_host = 'localhost'
server_port = 8000

adress = (server_host, server_port)

client_socket.connect(adress)

client_socket.sendto(b'Hola, servidor!', adress)