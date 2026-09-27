import socket, math

# cliente que se comunica con udp
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

server_host = 'localhost'
server_port = 8000

address = (server_host, server_port)

client_socket.connect(address)

## FALTA IMPLEMENTAR CÓMO LEER Y ENVÍAR UN ARCHIVO EN BYTES
message: bytes = (
                  b'Hola servidor. ' +
                  b'Quiero decirte que este es un mensaje de prueba con mas de 16 caracteres.' +
                  b'Espero que puedas recibirlo correctamente.'
                  b'Nos vemos en la otra terminal.'
                  b'(No puedo escribir tildes :c).'
                )

print(len(message))
i = 0
while i < len(message):
    fragment_to_send: bytes = b'\x00\x40\x04\x06' + message[i:i+16]
    client_socket.sendto(fragment_to_send, address)
    i += 16