import socket, SocketTCP

server_host = 'localhost'
server_port = 8000

address = (server_host, server_port)

client_socketTCP = SocketTCP.SocketTCP()
client_socketTCP.connect(address)

# Opción 1: Tu mensaje harcodeado de prueba
message: bytes = (
                  b'Hola servidor. ' +
                  b'Quiero decirte que este es un mensaje de prueba con mas de 16 caracteres. ' +
                  b'Espero que puedas recibirlo correctamente. ' +
                  b'Nos vemos en la otra terminal. ' +
                  b'(No puedo escribir tildes :c).'
                )

# Opción 2: Si más adelante quieres leer el archivo directamente desde Python sin usar sys:
# with open('archivo.txt', 'rb') as file:
#     message = file.read()

print("Sending message...")
client_socketTCP.send(message)
print("Message sent successfully")
client_socketTCP.close()
print("Connection closed successfully")