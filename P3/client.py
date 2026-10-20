import socket, SocketTCP, sys

server_host = 'localhost'
server_port = 8000

address = (sys.argv[1], int(sys.argv[2]))

message = sys.stdin.buffer.read()

client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.connect(address)

print("Sending message...")
client_socketTCP.send(message)
print("Message sent successfully")
client_socketTCP.close()
print("Connection closed successfully")