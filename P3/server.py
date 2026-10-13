import socket, SocketTCP

address = ('localhost', 8000)
buffer_size = 32

server_socketTCP = SocketTCP.SocketTCP()
server_socketTCP.bind(address)
print(f"Servidor escuchando en {address}...")

while True:
    print("Waiting for a message...")
    connection_socketTCP, new_address = server_socketTCP.accept()
    
    data: bytes = connection_socketTCP.recv(buffer_size)
    while connection_socketTCP.bytes_remaining > 0:
        data += connection_socketTCP.recv(buffer_size)
    
    print(f"Received message from {new_address}:")
    print(data.decode(errors='replace'))
    
    connection_socketTCP.recv_close()
    print(f"Connection with {new_address} closed successfully")