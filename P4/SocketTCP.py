import socket 
import random
from CongestionControl import CongestionControl
from socketUDP import SocketUDP
from slidingWindowCC import SlidingWindowCC

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
        self.udp_socket = SocketUDP()
        #Timeout para stop & wait
        self.timeout: float = 5 #segundos

        # Acá comenzamos definiendo cada byte
        self.dest_addr: tuple[str, int] | None = None
        self.seq: int = random.randint(0, 100)  # para handshake y stop & wait
        self.expected_seq: int = 0

        # Buffer de recepción para stop & wait
        self.buffer_size: int = SEQ_NBYTES + 1 + 16
        self.recv_buffer: bytes = b""
        self.bytes_remaining: int = 0
        
        self.congestion_control_on: bool = False
        self.congestion_controler: CongestionControl = CongestionControl(MSS=8)
        self.debug: bool = False

    def set_congestion_control(self, on: bool):
        self.congestion_control_on = on

    def set_debug(self, debug: bool):
        self.debug = debug

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

            self.seq = self.seq + 3

        # Si el mensaje no fue el esperado, entonces no se pudo establecer un canal de comunicación.
        # Invalidamos la dirección recibida previamente.
        else:
            self.dest_addr = None

    def accept(self) -> tuple["SocketTCP", tuple[str, int]]:
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

                new_socket.expected_seq = other_seq + 3

                # Este nuevo socket estará escuchando en la dirección generada previamente, y que además
                # ya es conocida por el socket cliente.
                new_address = ('localhost', new_port)
                new_socket.bind(new_address)
                return new_socket, new_address
            
            elif third_segment_struct.seq != other_seq + 2 or not third_segment_struct.ack:
                raise ConnectionError("El mensaje recibido no es un ACK válido.")



    def send_using_stop_and_wait(self, message: bytes) -> None:
        """Envía un mensaje a un socket destino.
        
        Atributos:
            message: Un mensaje en bytes que se desea enviar.
        """
        
        total_length: int = len(message)
        length_bytes: bytes = total_length.to_bytes(4, "big")
        lenght_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.seq, data=length_bytes)

        # Stop & Wait para el pimer segmento (largo)
        while True:
            try:
                self.udp_socket.settimeout(self.timeout)
            except AttributeError:
                pass
            self.udp_socket.sendto(self.create_segment(lenght_segment), self.dest_addr)
            try:
                ack_segment, _ = self.udp_socket.recvfrom(self.buffer_size)
                ack_segment_struct: ParsedSegmentTCP = self.parse_segment(ack_segment)
                if ack_segment_struct.seq == self.seq + 1 and ack_segment_struct.ack:
                    try:
                        self.udp_socket.stop_timer(0)
                    except Exception:
                        pass
                    self.seq += 1
                    break
            except (socket.timeout, TimeoutError, ConnectionResetError): 
                try:
                    self.udp_socket.stop_timer(0)
                except Exception:
                    pass
                continue
        
        # Enviamos el mensaje en fragmentos de 16 bytes, cada uno con su propio número de secuencia.
        i = 0
        while i < len(message):
            fin: int = min(i + 16, len(message))
            block: bytes = message[i:fin]
            parsed_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.seq, data=block)
            
            # Implementamos Stop & Wait
            while True:
                try:
                    self.udp_socket.settimeout(self.timeout)
                except AttributeError:
                    pass
                self.udp_socket.sendto(self.create_segment(parsed_segment), self.dest_addr)
                try:
                    ack_segment, _ = self.udp_socket.recvfrom(self.buffer_size)
                    ack_segment_struct: ParsedSegmentTCP = self.parse_segment(ack_segment)

                    if ack_segment_struct.seq == self.seq + 1 and ack_segment_struct.ack:
                        try:
                            self.udp_socket.stop_timer(0)
                        except Exception:
                            pass
                        self.seq += 1
                        i += 16
                        break
                
                except (socket.timeout, TimeoutError, ConnectionResetError):
                    try:
                        self.udp_socket.stop_timer(0)
                    except Exception:
                        pass
                    continue

    def send(self, message: bytes, mode="stop_and_wait") -> None:
        if mode == "stop_and_wait":
            self.send_using_stop_and_wait(message)
        elif mode == "go_back_n":
            self.send_using_go_back_n(message)

    def recv(self, buff_size: int, mode="stop_and_wait") -> bytes:
        if mode == "stop_and_wait":
            return self.recv_using_stop_and_wait(buff_size)
        elif mode == "go_back_n":
            return self.recv_using_go_back_n(buff_size)

    def send_using_go_back_n(self, message: bytes) -> None:
        MSS = 8
        if self.congestion_control_on:
            self.congestion_controler = CongestionControl(MSS)
            window_size = self.congestion_controler.get_MSS_in_cwnd()
        else:
            window_size = 8
            
        message_length_str = str(len(message)).encode()
        data_list = [message_length_str] + [message[i:i+MSS] for i in range(0, len(message), MSS)]
        data_window = SlidingWindowCC(window_size, data_list, self.seq)
        
        try:
            self.udp_socket.settimeout(self.timeout)
            self.udp_socket.set_timer_list_length(1)
        except AttributeError:
            pass
            
        def send_segment_at_index(idx):
            data = data_window.get_data(idx)
            if data is not None:
                seq = data_window.get_sequence_number(idx)
                segment = self.create_segment(ParsedSegmentTCP(seq, data=data))
                self.udp_socket.sendto(segment, self.dest_addr, timer_index=0)

        def send_elements_in_window(start_index, end_index):
            for i in range(start_index, end_index):
                send_segment_at_index(i)

        if self.debug:
            print(f"[DEBUG GBN] Ventana inicial (size={window_size}):")
            print(data_window)

        send_elements_in_window(0, window_size)
        elements_sent = window_size
        
        while data_window.get_data(0) is not None:
            try:
                answer, address = self.udp_socket.recvfrom(self.buffer_size)
                ack_struct = self.parse_segment(answer)
                if ack_struct.ack:
                    ack_seq = ack_struct.seq
                    
                    while data_window.get_data(0) is not None:
                        last_idx = -1
                        for idx in range(window_size - 1, -1, -1):
                            if data_window.get_data(idx) is not None:
                                last_idx = idx
                                break
                        if last_idx == -1:
                            break
                            
                        last_seq = data_window.get_sequence_number(last_idx)
                        
                        # Caso borde: ack_seq es estrictamente mayor que el último seq en la ventana
                        if ack_seq > last_seq:
                            steps = last_idx + 1
                            try:
                                self.udp_socket.stop_timer(timer_index=0)
                            except Exception:
                                pass
                                
                            data_window.move_window(steps)
                            
                            if self.congestion_control_on:
                                for _ in range(steps):
                                    self.congestion_controler.event_ack_received()
                                new_window_size = self.congestion_controler.get_MSS_in_cwnd()
                                if new_window_size != window_size:
                                    old_w = window_size
                                    data_window.update_window_size(new_window_size)
                                    window_size = new_window_size
                                    if new_window_size > old_w:
                                        for i in range(old_w, new_window_size):
                                            send_segment_at_index(i)
                                            
                            elements_sent = max(0, elements_sent - steps)
                            send_elements_in_window(elements_sent, window_size)
                            elements_sent = window_size
                            
                            if self.debug:
                                print(f"[DEBUG GBN] Caso borde (ack={ack_seq} > last={last_seq}). Movidos {steps} pasos. cwnd={self.congestion_controler.get_cwnd()}:")
                                print(data_window)
                            continue
                        
                        # Caso normal: ack_seq cae dentro de la ventana
                        steps = 0
                        for i in range(window_size):
                            d = data_window.get_data(i)
                            s = data_window.get_sequence_number(i)
                            if d is not None and s is not None and ack_seq > s:
                                steps = i + 1
                            else:
                                break
                                
                        if steps > 0:
                            try:
                                self.udp_socket.stop_timer(timer_index=0)
                            except Exception:
                                pass
                                
                            data_window.move_window(steps)
                            
                            if self.congestion_control_on:
                                for _ in range(steps):
                                    self.congestion_controler.event_ack_received()
                                new_window_size = self.congestion_controler.get_MSS_in_cwnd()
                                if new_window_size != window_size:
                                    old_w = window_size
                                    data_window.update_window_size(new_window_size)
                                    window_size = new_window_size
                                    if new_window_size > old_w:
                                        for i in range(old_w, new_window_size):
                                            send_segment_at_index(i)
                            
                            first_data = data_window.get_data(0)
                            if first_data is not None:
                                self.seq = data_window.get_sequence_number(0)
                            else:
                                self.seq = ack_seq
                                
                            elements_sent = max(0, elements_sent - steps)
                            send_elements_in_window(elements_sent, window_size)
                            elements_sent = window_size
                            
                            if self.debug:
                                print(f"[DEBUG GBN] ACK recibido ({ack_seq}), avanzados {steps} pasos. cwnd={self.congestion_controler.get_cwnd()}, state={self.congestion_controler.current_state}:")
                                print(data_window)
                                
                        break
                        
                    if data_window.get_data(0) is not None:
                        try:
                            if self.udp_socket.timer_list[0] is None:
                                from threading import Timer
                                self.udp_socket.timer_list[0] = Timer(self.timeout, self.udp_socket._time_up_function, args=(0,))
                                self.udp_socket.timer_list[0].start()
                        except (AttributeError, IndexError):
                            pass
                            
            except (socket.timeout, TimeoutError, ConnectionResetError):
                try:
                    self.udp_socket.stop_timer(timer_index=0)
                except Exception:
                    pass
                    
                if self.congestion_control_on:
                    self.congestion_controler.event_timeout()
                    new_window_size = self.congestion_controler.get_MSS_in_cwnd()
                    if new_window_size != window_size:
                        data_window.update_window_size(new_window_size)
                        window_size = new_window_size
                
                if self.debug:
                    print(f"[DEBUG GBN] TIMEOUT! cwnd={self.congestion_controler.get_cwnd()}, ssthresh={self.congestion_controler.get_ssthresh()}, state={self.congestion_controler.current_state}")
                    print(data_window)

                elements_sent = 0
                send_elements_in_window(0, window_size)
                elements_sent = window_size

    def recv_using_go_back_n(self, buff_size: int) -> bytes:
        if self.bytes_remaining == 0 and len(self.recv_buffer) == 0:
            while True:
                segment, _ = self.udp_socket.recvfrom(self.buffer_size)
                segment_struct: ParsedSegmentTCP = self.parse_segment(segment)

                if segment_struct.seq == self.expected_seq:
                    try:
                        self.bytes_remaining = int(segment_struct.data.decode())
                    except ValueError:
                        self.bytes_remaining = int.from_bytes(segment_struct.data, "big")
                        
                    self.expected_seq += len(segment_struct.data)

                    ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1)
                    self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
                    break
                else:
                    ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1)
                    self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
        
        while len(self.recv_buffer) < buff_size and self.bytes_remaining > 0:
            segment, _ = self.udp_socket.recvfrom(self.buffer_size)
            segment_struct: ParsedSegmentTCP = self.parse_segment(segment)

            if segment_struct.seq == self.expected_seq:
                self.recv_buffer += segment_struct.data
                self.bytes_remaining -= len(segment_struct.data)

                self.expected_seq += len(segment_struct.data)

                ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1)
                self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)

            else:
                ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1)
                self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
        
        return_data = self.recv_buffer[:buff_size]
        self.recv_buffer = self.recv_buffer[buff_size:]
        return return_data


    def recv_using_stop_and_wait(self, buff_size: int) -> bytes:
        """Recibe un mensaje de un socket destino.
        
        Atributos:
            buff_size: Un entero que representa la cantidad máxima de bytes que se pueden recibir.
        
        Retorna:
            Un mensaje en bytes recibido desde el socket destino.
        """
        # Si es un mensaje nuevo, se espera a recibir el primer segmento que contiene la longitud del mensaje.
        if self.bytes_remaining == 0 and len(self.recv_buffer) == 0:
            while True:
                segment, _ = self.udp_socket.recvfrom(self.buffer_size)
                segment_struct: ParsedSegmentTCP = self.parse_segment(segment)

                if segment_struct.seq == self.expected_seq:
                    self.bytes_remaining = int.from_bytes(segment_struct.data, "big")

                    # Enviamos mensaje ACK
                    ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq + 1, ack=1)
                    self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
                    self.expected_seq += 1
                    break
                else: # Caso borde
                    # Si llega algo fuera de seq
                    ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1)
                    self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
        
        
        # Recibimos los fragmentos de data
        while len(self.recv_buffer) < buff_size and self.bytes_remaining > 0:
            segment, _ = self.udp_socket.recvfrom(self.buffer_size)
            segment_struct: ParsedSegmentTCP = self.parse_segment(segment)

            # Si el número de secuencia del segmento recibido es el esperado, entonces se procesa el segmento.
            if segment_struct.seq == self.expected_seq:
                # Agregamos el bloque de datos del segmento recibido al buffer de recepción y actualizamos la cantidad de bytes restantes por recibir.
                self.recv_buffer += segment_struct.data
                self.bytes_remaining -= len(segment_struct.data)

                # Se envía un mensaje ACK con el número de secuencia incrementado en 1.
                ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq + 1, ack=1)
                self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)

                # Se incrementa el número de secuencia esperado para el siguiente segmento.
                self.expected_seq += 1

            elif segment_struct.seq < self.expected_seq: # Caso borde
                # Si el numero de secuencia no coincide,
                # probablemente el mensaje no llegó y se volvió a enviar (por parte del emisor)
                # Entonces se envía un mensaje ACK con el número de secuencia esperado.
                ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1)
                self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
        
        # Solo retornamos la cantidad de bytes solicitada, y dejamos el resto en el buffer para la próxima llamada a recv
        return_data = self.recv_buffer[:buff_size]
        self.recv_buffer = self.recv_buffer[buff_size:]
        return return_data


    def close(self):
        """Cierra el socket TCP y libera los recursos asociados a él."""
        if self.dest_addr is None:
            self.udp_socket.close()
            return

        # Creamos un segmento con el flag fin activado y el número de secuencia actual.
        fin_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.seq, fin=1)
        
        # Implementamos Stop & Wait para enviar el segmento FIN y esperar un ACK del socket destino.
        while True:
            self.udp_socket.sendto(self.create_segment(fin_segment), self.dest_addr)
            try:
                self.udp_socket.settimeout(self.timeout)
                ack_bytes, _ = self.udp_socket.recvfrom(self.buffer_size)
                ack_segment: ParsedSegmentTCP = self.parse_segment(ack_bytes)

                # Comprobamos si el mensaje recibido es un ACK con el número de secuencia esperado (self.seq + 1).
                if ack_segment.seq == self.seq + 1 and ack_segment.ack:
                    break
            except (socket.timeout, TimeoutError, ConnectionResetError):
                continue

        # Esperamos el mensaje fin del receptor
        while True:
            try:
                self.udp_socket.settimeout(self.timeout)
                fin_bytes, _ = self.udp_socket.recvfrom(self.buffer_size)
                fin_segment: ParsedSegmentTCP = self.parse_segment(fin_bytes)

                if fin_segment.fin == 1:
                    last_ack = ParsedSegmentTCP(fin_segment.seq + 1, ack=1)
                    self.udp_socket.sendto(self.create_segment(last_ack), self.dest_addr)
                    break
            except (socket.timeout, TimeoutError, ConnectionResetError):
                continue

        # Liberamos los recursos asociados al socket UDP subyacente.
        self.udp_socket.close()

    def recv_close(self):
        """Maneja el fin de conexión desde el lado del receptor."""     
        other_seq: int = 0

        # receptor espera recibir el mensaje fin del emisor
        while True:
            try:
                self.udp_socket.settimeout(self.timeout)
                fin_bytes, other_addr = self.udp_socket.recvfrom(self.buffer_size)
                fin_segment: ParsedSegmentTCP = self.parse_segment(fin_bytes)

                if fin_segment.fin == 1:
                    other_seq = fin_segment.seq
                    ack_segment = ParsedSegmentTCP(other_seq + 1, ack=1)
                    self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
                    break
            except (socket.timeout, TimeoutError, ConnectionResetError):
                continue

        # Ahora el receptor envía su propio mensaje fin al emisor
        fin_segment = ParsedSegmentTCP(self.seq, fin=1)

        while True:
            self.udp_socket.sendto(self.create_segment(fin_segment), self.dest_addr)
            try:
                self.udp_socket.settimeout(self.timeout)
                ack_bytes, _ = self.udp_socket.recvfrom(self.buffer_size)
                ack_segment: ParsedSegmentTCP = self.parse_segment(ack_bytes)

                if ack_segment.seq == self.seq + 1 and ack_segment.ack:
                    break
            except (socket.timeout, TimeoutError, ConnectionResetError):
                continue

        # Liberamos los recursos asociados al socket UDP subyacente.
        self.udp_socket.close()
        


if __name__ == "__main__":

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