import socket 
import random

SEQ_NBYTES: int = 2
FREE_PORT: int = 8001

def get_new_port() -> int:
    global FREE_PORT
    new_port = FREE_PORT
    FREE_PORT += 1
    return new_port


class ParsedSegmentTCP:
    """Almacena de forma organizada la información de un segmento TCP.
    
    Atributos:
        seq:
            Un entero que contiene el número de secuencia escrito en el segmento.
        syn:
            Representa si el segmento envía un mensaje de sincronización. Su valor es 0 o 1.
        ack:
            Representa si el segmento envía un mensaje de confirmación. Su valor es 0 o 1.
        fin:
            Representa si el segmento envía un mensaje de término de comunicación. Su valor es 0 o 1.
        data:
            Los contenidos, de algún archivo, que se quieren enviar al receptor. Se guarda en bytes.
    
    """
    def __init__(self, seq: int, syn: int = 0, ack: int = 0, fin: int = 0, data: bytes = b""):
        self.seq: int = seq
        self.syn: int = syn
        self.ack: int = ack
        self.fin: int = fin
        self.data: bytes = data

class SocketTCP:
    def __init__(self):
        # Socket UDP subyacente
        self.udp_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #Timeout para stop & wait
        self.udp_socket.settimeout(1.0)

        # Acá comenzamos definiendo cada byte
        self.dest_addr: tuple[str, int] | None = None
        self.seq: int = random.randint(0, 100)  # para handshake y stop & wait
        self.expected_seq: int = 0

        # Buffer de recepción para stop & wait
        self.buffer_size: int = SEQ_NBYTES + 1 + 16
        self.recv_buffer: bytes = b""
        self.bytes_remaining: int = 0

    @staticmethod
    def create_segment(segment_struct: ParsedSegmentTCP) -> bytes:
        """Transforma la información de una estructura ParsedSegmentTCP en un segmento TCP escrito en bytes."""

        # Armamos el byte de flags. Los 3 bits menos significativos representan los valores de SYN, ACK y FIN
        flags = segment_struct.syn * 4 + segment_struct.ack * 2 + segment_struct.fin
        flags = flags.to_bytes(1, "big")
        
        header: bytes = segment_struct.seq.to_bytes(SEQ_NBYTES, "big") + flags
        return header + segment_struct.data 

    @staticmethod
    def parse_segment(segment: bytes) -> ParsedSegmentTCP:
        """Retorna un ParsedSegmentTCP con información organizada extraída de un segmento TCP escrito en bytes.
        
        Cada segmento TCP válido se escribe de la siguiente forma:
            * Los primeros SEQ_NBYTES bytes guardan el número de secuencia del segmento.
            * El byte (SEQ_NBYTES + 1) representa si el segmento incluye un mensaje SYN, ACK y/o FIN:
                * Su tercer bit menos significativo indica el valor de SYN.
                * Su segundo bit menos significativo indica el valor de ACK.
                * Su bit menos significativo indica el valor de FIN.
                * Un valor 0 representa NO, mientras que un valor 1 representa SÍ.
            * El resto de bytes del segmento almacenan los contenidos que se desean enviar al receptor.
        """
        seq: int = int.from_bytes(segment[0:SEQ_NBYTES], "big")

        flags: int = int.from_bytes(segment[SEQ_NBYTES:SEQ_NBYTES + 1], "big")
        syn = 1 if flags & 0b100 > 0b000 else 0
        ack = 1 if flags & 0b010 > 0b000 else 0
        fin = 1 if flags & 0b001 > 0b000 else 0

        data: bytes = segment[SEQ_NBYTES + 1:]
        
        return ParsedSegmentTCP(seq, syn, ack, fin, data)

    def bind(self, address: tuple[str, int]):
        """Establece que el socket escuche en la dirección entregada.

        Atributos:
            address: Una tupla (IP, puerto) que representa una dirección.
        """
        self.udp_socket.bind(address)

    def connect(self, address: tuple[str, int]):
        """Inicia una conexión con un socket que esté escuchando en la dirección entregada.
        
        Atributos:
            address: Una tupla (IP, puerto) que representa una dirección.
        """

        # Envía el mensaje SYN junto con el número de secuencia al socket servidor.
        first_handshake_step: bytes = self.create_segment(ParsedSegmentTCP(self.seq, syn=1))
        self.udp_socket.sendto(first_handshake_step, address)

        # Espera a recibir un mensaje SYN + ACK del socket servidor.
        second_handshake_step, _ = self.udp_socket.recvfrom(self.buffer_size)
        segment_struct: ParsedSegmentTCP = self.parse_segment(second_handshake_step)

        # El contenido de este mensaje incluye la dirección del nuevo socket que se usará
        # para comunicarse con este socket. Guardamos la dirección.
        self.dest_addr = ('localhost', int.from_bytes(segment_struct.data, "big"))

        # Revisamos que el mensaje recibido efectivamente contenga SYN, ACK y el
        # número de secuencia esperado (self.seq + 1).
        if segment_struct.seq == self.seq + 1 and segment_struct.syn and segment_struct.ack:

            # Se envía el mensaje ACK al socket servidor, junto con el número de secuencia + 2.
            third_handshake_step: bytes = self.create_segment(ParsedSegmentTCP(self.seq + 2, ack=1))
            self.udp_socket.sendto(third_handshake_step, address)

        # Si el mensaje no fue el esperado, entonces no se pudo establecer un canal de comunicación.
        # Invalidamos la dirección recibida previamente.
        else:
            self.dest_addr = None

    def accept(self):
        """Espera una petición de tipo SYN para iniciar una comunicación con otro socket.
        
        Retorna:
            Un nuevo socket TCP (con otra dirección) que establece un canal de
            comunicación con el socket que envío la petición de tipo SYN.
        """

        # Espera a recibir un mensaje SYN con un número de secuencia.
        first_handshake_step, other_address = self.udp_socket.recvfrom(self.buffer_size)
        first_segment_struct: ParsedSegmentTCP = self.parse_segment(first_handshake_step)
        other_seq: int = first_segment_struct.seq

        if first_segment_struct.syn:

            # Después de recibir el mensaje SYN, el socket debe enviar un mensaje SYN + ACK al
            # socket cliente, junto con el número de secuencia recibido incrementado en 1.
            segment: ParsedSegmentTCP = ParsedSegmentTCP(other_seq + 1, syn=1, ack=1)

            # Además, el segmento incluirá la dirección del nuevo socket que se usará
            # para establecer el canal de comunicación.
            new_port: int = get_new_port()
            segment.data = new_port.to_bytes(SEQ_NBYTES, "big")

            second_handshake_step: bytes = self.create_segment(segment)
            self.udp_socket.sendto(second_handshake_step, other_address)

            # Se espera a recibir un mensaje ACK del socket cliente con el número de secuencia
            # original incrementado en 2.
            third_handshake_step, _ = self.udp_socket.recvfrom(self.buffer_size)
            third_segment_struct = self.parse_segment(third_handshake_step)

            if third_segment_struct.seq == other_seq + 2 and third_segment_struct.ack:

                # Se crea el nuevo socket que podrá enviar mensajes a la dirección del socket cliente.
                # Este socket contendrá el número de secuencia recibido en el primer segmento del socket cliente.
                new_socket: SocketTCP = SocketTCP()
                new_socket.dest_addr = other_address
                new_socket.seq = other_seq

                # Este nuevo socket estará escuchando en la dirección generada previamente, y que además
                # ya es conocida por el socket cliente.
                new_address = ('localhost', new_port)
                new_socket.bind(new_address)
                return new_socket

mi_socket = SocketTCP()

test_1 = b'\x00\x20\x05\x06Este es un mensaje'
print(test_1)
parsed_segment_tcp: ParsedSegmentTCP = mi_socket.parse_segment(test_1)

print(parsed_segment_tcp.seq)
print(parsed_segment_tcp.syn)
print(parsed_segment_tcp.ack)
print(parsed_segment_tcp.fin)
print(parsed_segment_tcp.data)

test_2 = mi_socket.create_segment(parsed_segment_tcp)
print("Nuevo segmento:", test_2)
print(test_1 == test_2)