import socket 
import random

class ParsedSegmentTCP:
    def __init__(self, seq: bytes, ack: bytes, syn: bytes = b'\x00', ack_flag: bytes = b'\x00', fin: bytes = b'\x00', data: bytes = b""):
        self.seq: bytes = seq
        self.ack: bytes = ack
        self.syn: bytes = syn
        self.ack_flag: bytes = ack_flag
        self.fin: bytes = fin
        self.data: bytes = data

class SocketTCP:
    def __init__(self):
        # Socket UDP subyacente
        self.udp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #Timeout para stop & wait
        self.udp_socket.settimeout(1.0)

        # Acá comenzamos definiendo cada byte
        self.dest_addr: tuple|None = None
        self.seq: int = random.randint(0, 2**16 - 1)  # para handshake y stop & wait
        self.expected_seq: int = 0

        # Buffer de recepción para stop & wait
        self.recv_buffer: bytes = b""
        self.bytes_remaining: int = 0

    # métodos para crear y parsear segmentos

    def create_segment(self, struct: ParsedSegmentTCP) -> bytes:

        # Armamos el byte de flags
        flags = int.from_bytes(struct.syn, "big")*4 + int.from_bytes(struct.ack_flag, "big")*2 + int.from_bytes(struct.fin, "big")
        flags = flags.to_bytes(1, "big")
        
        # to_bytes convierte enteros a bytes
        header: bytes = struct.seq + struct.ack + flags
        return header + struct.data 

    def parse_segment(self, segment: bytes) -> ParsedSegmentTCP:

        seq: bytes = segment[0:2]
        ack: bytes = segment[2:3]
        flags: int = int.from_bytes(segment[3:4], "big")

        syn = b'\x01' if flags & 0b100 > 0b000 else b'\x00'
        ack_flag = b'\x01' if flags & 0b010 > 0b000 else b'\x00'
        fin = b'\x01' if flags & 0b001 > 0b000 else b'\x00'

        data: bytes = segment[4:]
        
        return ParsedSegmentTCP(seq, ack, syn, ack_flag, fin, data)

mi_socket = SocketTCP()

test_1 = b'\x00\x20\x05\x06Este es un mensaje'
print(test_1)
parsed_segment_tcp: ParsedSegmentTCP = mi_socket.parse_segment(test_1)

print(parsed_segment_tcp.seq)
print(parsed_segment_tcp.ack)
print(parsed_segment_tcp.syn)
print(parsed_segment_tcp.ack_flag)
print(parsed_segment_tcp.fin)
print(parsed_segment_tcp.data)

test_2 = mi_socket.create_segment(parsed_segment_tcp)
print("Nuevo segmento:", test_2)
print(test_1 == test_2)