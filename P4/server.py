import SocketTCP

address = ('localhost', 8000)

server_socketTCP = SocketTCP.SocketTCP()
server_socketTCP.bind(address)
print(f"=== Servidor iniciado escuchando en {address} ===")

while True:
    print("\n[Servidor] Esperando nueva conexion...")
    connection_socketTCP, new_address = server_socketTCP.accept()
    print(f"[Servidor] Cliente conectado desde {new_address}")
    
    # Recibimos el mensaje usando el modo go_back_n
    data: bytes = connection_socketTCP.recv(4096, mode="go_back_n")
    
    print(f"[Servidor] Mensaje recibido con exito ({len(data)} bytes):")
    print("--------------------------------------------------")
    print(data.decode(errors='replace'))
    print("--------------------------------------------------")
    
    connection_socketTCP.recv_close()
    print(f"[Servidor] Conexion con {new_address} finalizada correctamente.")