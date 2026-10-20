import sys
import time
import SocketTCP

server_address = ('localhost', 8000)

# Verificamos parámetro por línea de comando: 1 (con CC) o 2 (sin CC)
if len(sys.argv) > 1:
    mode_arg = sys.argv[1].strip()
else:
    print("Uso: python3 client.py <1 o 2>")
    print("  1: Go-Back-N CON Control de Congestion")
    print("  2: Go-Back-N SIN Control de Congestion")
    mode_arg = input("Seleccione modo (1 o 2): ").strip()

use_cc = (mode_arg == "1")

# Mensaje de prueba de 100 Bytes exactos
# (100 caracteres ASCII = 100 bytes en UTF-8)
message: bytes = b"A" * 100

print(f"\n--- Iniciando envio (100 Bytes) | CC = {use_cc} ---")

client = SocketTCP.SocketTCP()
client.timeout = 0.5            # Timeout de 0.5s para las pruebas
client.set_congestion_control(use_cc)
client.set_debug(True)          # Modo debug activado para ver la ventana

client.connect(server_address)

start_time = time.time()
client.send(message, mode="go_back_n")
end_time = time.time()

client.close()

elapsed_time = end_time - start_time
segments_sent = client.number_of_sent_segments

print("\n" + "="*50)
print(f"Modo: {'CON' if use_cc else 'SIN'} Control de Congestion")
print(f"Tiempo total: {elapsed_time:.4f} segundos")
print(f"Segmentos enviados: {segments_sent}")
print("="*50 + "\n")