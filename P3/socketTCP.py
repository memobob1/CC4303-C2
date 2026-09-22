import socket 
import random

class SocketTCP:
    def __init__(self):
        # Socket UDP subyacente
        self.udp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #Timeout para stop & wait
        self.udp_socket.settimeout(1.0)

        # Acá comenzamos definiendo cada byte
        self.dest_addr: tuple|None = None
        self.seq: int = random.randint(0, 100)  # para handshake y stop & wait
        self.expected_seq: int = 0

        # Buffer de recepción para stop & wait
        self.recv_buffer: bytes = b""
        self.bytes_remaining: int = 0

    # métodos para crear y parsear segmentos

    def create_segment(self, seq: int, ack: int, syn: int, ack_flag: int, fin: int, data: bytes = b"") -> bytes:
        # Armamos el byte de flags
        flags = 0
        if syn: flags |= 0b100
        if ack_flag: flags |= 0b010
        if fin: flags |= 0b001
        
        # to_bytes convierte enteros a bytes
        header = seq.to_bytes(1, 'big') + ack.to_bytes(1, 'big') + flags.to_bytes(1, 'big') + b'\x00'
        return header + data 