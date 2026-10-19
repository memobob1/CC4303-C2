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
        self.number_of_sent_segments: int = 0

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
            # Se espera a recibir un mensaje ACK del socket cliente con el número de secuencia original
            while True:
                try:
                    self.udp_socket.settimeout(self.timeout)
                    third_handshake_step, _ = self.udp_socket.recvfrom(self.buffer_size)
                    third_segment_struct = self.parse_segment(third_handshake_step)

                    if third_segment_struct.seq == other_seq + 2 and third_segment_struct.ack:
                        try:
                            self.udp_socket.stop_timer(0)
                        except Exception:
                            pass
                        break
                    
                    # Si el ACK se perdió en la red pero nos llega un fragmento de datos
                    elif third_segment_struct.seq > other_seq + 2:
                        try:
                            self.udp_socket.stop_timer(0)
                        except Exception:
                            pass
                        break

                except (socket.timeout, TimeoutError, ConnectionResetError):
                    # Evita el RuntimeError de los hilos
                    try:
                        self.udp_socket.stop_timer(0)
                    except Exception:
                        pass
                    
                    # Retransmitimos el SYN+ACK
                    self.udp_socket.sendto(second_handshake_step, other_address)
                    continue

            # Se crea el nuevo socket que podrá enviar mensajes a la dirección del socket cliente.
            new_socket: SocketTCP = SocketTCP()
            new_socket.dest_addr = other_address
            new_socket.seq = other_seq
            new_socket.expected_seq = other_seq + 3

            new_address = ('localhost', new_port)
            new_socket.bind(new_address)
            return new_socket, new_address



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
        '''Envía un mensaje a un socket destino.
            Atributos:
                message: Un mensaje en bytes que se desea enviar.
                mode: El modo de envío, puede ser "stop_and_wait" o "go_back_n".
        '''
        if mode == "stop_and_wait":
            self.send_using_stop_and_wait(message)
        elif mode == "go_back_n":
            self.send_using_go_back_n(message)

    def recv(self, buff_size: int, mode="stop_and_wait") -> bytes:
        '''Recibe un mensaje de un socket destino.
            Atributos:
                buff_size: Un entero que representa la cantidad máxima de bytes que se pueden recibir.
                mode: El modo de recepción, puede ser "stop_and_wait" o "go_back_n".
            
            Retorna:
                Un mensaje en bytes recibido desde el socket destino.
        '''
        if mode == "stop_and_wait":
            return self.recv_using_stop_and_wait(buff_size)
        elif mode == "go_back_n":
            return self.recv_using_go_back_n(buff_size)

    def send_using_go_back_n(self, message: bytes) -> None:
        MSS = 8 
        # Si el control de congestión está activado, se inicializa un objeto CongestionControl y se obtiene el tamaño de la ventana de congestión (cwnd) en términos de MSS. 
        # Si no está activado, se establece un tamaño de ventana fijo de 8.
        if self.congestion_control_on:
            self.congestion_controler = CongestionControl(MSS)
            window_size = self.congestion_controler.get_MSS_in_cwnd()
        else:
            window_size = 8
        
        message_length_str = str(len(message)).encode() # Sacamos el largo del mensaje
        data_list = [message_length_str] + [message[i:i+MSS] for i in range(0, len(message), MSS)] # Creamos la lista de datos a enviar, incluyendo el largo del mensaje como primer elemento
        data_window = SlidingWindowCC(window_size, data_list, self.seq) # Instanciamos la ventana de datos con el tamaño de ventana y la lista de datos a enviar, junto con el número de secuencia inicial.
        
        # Se establece un tiempo de espera para el socket UDP subyacente 
        self.udp_socket.settimeout(self.timeout)
        # Se establece la longitud de la lista de temporizadores del socket UDP subyacente en 1
        self.udp_socket.set_timer_list_length(1)
            
        def send_segment_at_index(idx: int) -> None:
            ''' Función auxiliar que envía un segmento de datos en la posición idx de la ventana de datos. 
                Si no hay datos en esa posición, no hace nada.
                
                Atributos:
                    idx: Un entero que representa la posición de la ventana de datos.'''
            data = data_window.get_data(idx)
            if data is not None:
                seq = data_window.get_sequence_number(idx)
                segment = self.create_segment(ParsedSegmentTCP(seq, data=data))
                self.udp_socket.sendto(segment, self.dest_addr, timer_index=0)
                self.number_of_sent_segments += 1

        def send_elements_in_window(start_index: int, end_index: int) -> None:
            ''' Función auxiliar que envía todos los segmentos de datos en la ventana de datos desde start_index hasta end_index (exclusivo).
                Si no hay datos en alguna posición, no hace nada.
                
                Atributos:
                    start_index: Un entero que representa la posición inicial de la ventana de datos.
                    end_index: Un entero que representa la posición final (exclusiva) de la ventana de datos.'''
            for i in range(start_index, end_index):
                send_segment_at_index(i)

        if self.debug:
            print(f"[DEBUG GBN] Ventana inicial (size={window_size}):")
            print(data_window)

        send_elements_in_window(0, window_size) # Enviamos los primeros elementos de la ventana de datos
        elements_sent = window_size # Mantenemos un contador de los elementos enviados para saber cuántos elementos de la ventana se han enviado y cuántos quedan por enviar.
        
        while data_window.get_data(0) is not None: # Mientras hayan datos en la ventana por enviar
            try:
                answer, address = self.udp_socket.recvfrom(self.buffer_size) # se espera a recibir un ACK del socket destino
                ack_struct = self.parse_segment(answer) # se paresea para saber si es un ACK válido y cuál es el número de secuencia que confirma.
                if ack_struct.ack: # si tiene un ack
                    ack_seq = ack_struct.seq # se saca su secuencia
                    
                    while data_window.get_data(0) is not None:
                        last_idx = -1
                        for idx in range(window_size - 1, -1, -1): # Recorremos de la última posición de la ventana hacia la primera para encontrar el último índice que tenga datos en la ventana.
                            if data_window.get_data(idx) is not None:
                                last_idx = idx # Guarda el último índice que tiene datos en la ventana
                                break
                        if last_idx == -1: # Si no hay datos en la ventana, se rompe el bucle
                            break
                            
                        last_seq = data_window.get_sequence_number(last_idx) # Se obtiene el número de secuencia del último índice que tiene datos en la ventana
                        
                        # Caso borde: ack_seq es estrictamente mayor que el último seq en la ventana
                        if ack_seq > last_seq:
                            # Avanzamos la ventana desde el el ultimo indice que recibió el ack (+1 para enviar nuevos segmentos)
                            # Ya que asumimos que si ack_seq es mayor que el último seq en la ventana, 
                            # entonces todos los segmentos anteriores de la ventana han sido recibidos por el destinatario.
                            steps = last_idx + 1
            
                            try:
                                self.udp_socket.stop_timer(0)
                            except Exception:
                                pass

                            data_window.move_window(steps) # movemos la ventana steps posiciones hacia adelante
                            
                            # Si se tiene el congestion control activado
                            # se actualiza la ventana de congestión y se envían los nuevos segmentos que entran en la ventana.
                            if self.congestion_control_on:
                                for _ in range(steps):
                                    self.congestion_controler.event_ack_received()
                                new_window_size = self.congestion_controler.get_MSS_in_cwnd() # aca se guarda el nuevo tamaño de la ventana
                                
                                # si la nueva ventana es diferente a la anterior
                                # hay que actualizar los datos
                                if new_window_size != window_size:
                                    old_w = window_size
                                    data_window.update_window_size(new_window_size)
                                    window_size = new_window_size
                                    if new_window_size > old_w: # si la ventana creció
                                        for i in range(old_w, new_window_size):
                                            send_segment_at_index(i) # enviamos inmediatamente los nuevos segmentos que entran en la ventana
                
                            elements_sent = max(0, elements_sent - steps)
                            send_elements_in_window(elements_sent, window_size) # Enviamos los elementos que quedan en la ventana después de moverla
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

                            # si el dato en la posición i de la ventana no es None y el número de secuencia en esa posición es menor que ack_seq
                            # entonces se puede avanzar la ventana.
                            if d is not None and s is not None and ack_seq > s: 
                                steps = i + 1
                            else: # si no, se rompe porque ya no hay más datos que puedan ser confirmados por el ACK recibido.
                                break

                        # si se avanzó la ventana, se detiene el timer del socket UDP,
                        # se mueve la ventana y se actualiza el tamaño de la ventana de congestión si está activado.    
                        if steps > 0:
                            
                            try:
                                self.udp_socket.stop_timer(0)
                            except Exception:
                                pass

                            data_window.move_window(steps)
                            
                            # caso congestion control esta activado
                            if self.congestion_control_on:
                                for _ in range(steps):
                                    self.congestion_controler.event_ack_received() # recibimos un ACK, se actualiza el estado
                                new_window_size = self.congestion_controler.get_MSS_in_cwnd() # aca se guarda el nuevo tamaño de la ventana
                                if new_window_size != window_size:
                                    old_w = window_size 
                                    data_window.update_window_size(new_window_size)
                                    window_size = new_window_size
                                    # si la nueva ventana es mayor
                                    if new_window_size > old_w: 
                                        for i in range(old_w, new_window_size):
                                            send_segment_at_index(i) # enviamos inmediatamente los nuevos segmentos que entran en la ventana
                            
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
                    
                    # Caso ayuda con IA: si quedan elementos por enviar pero no hay timers corrriendo
                    # entonces se inicia un timer para el primer elemento de la ventana.
                    if data_window.get_data(0) is not None:
                        if self.udp_socket.timer_list[0] is None:
                            from threading import Timer
                            self.udp_socket.timer_list[0] = Timer(self.timeout, self.udp_socket._time_up_function, args=(0,))
                            self.udp_socket.timer_list[0].start()

            
            # Si ocurre timeout en el primer elemento de la ventana, entonces tenemos que hacer go-back-n
            # y reenviar todos los elementos de la ventana desde el primero hasta el último.      
            except (socket.timeout, TimeoutError, ConnectionResetError):

                try:
                    self.udp_socket.stop_timer(0)
                except Exception:
                    pass

                # si el congestion control está activado  
                if self.congestion_control_on:
                    self.congestion_controler.event_timeout()
                    new_window_size = self.congestion_controler.get_MSS_in_cwnd() # se actualiza el tamaño de la ventana
                    if new_window_size != window_size:
                        data_window.update_window_size(new_window_size)
                        window_size = new_window_size
                
                if self.debug:
                    print(f"[DEBUG GBN] TIMEOUT! cwnd={self.congestion_controler.get_cwnd()}, ssthresh={self.congestion_controler.get_ssthresh()}, state={self.congestion_controler.current_state}")
                    print(data_window)

                elements_sent = 0
                send_elements_in_window(0, window_size) # enviamos todos los elementos de la ventana desde el primero hasta el último (go-back-n)
                elements_sent = window_size


    def recv_using_go_back_n(self, buff_size: int) -> bytes:
        # Primer recepción de un mensaje nuevo que contiene la longitud del mensaje
        if self.bytes_remaining == 0 and len(self.recv_buffer) == 0:
            while True:
                # Recibimos el mensaje y lo parseamos
                segment, _ = self.udp_socket.recvfrom(self.buffer_size)
                segment_struct: ParsedSegmentTCP = self.parse_segment(segment) 

                # si el número de secuencia del segmento recibido es el esperado, entonces se procesa el segmento
                if segment_struct.seq == self.expected_seq: 
                    
                    self.bytes_remaining = int(segment_struct.data.decode()) # Guardamos la cantidad de bytes que se van a recibir
                        
                    self.expected_seq += len(segment_struct.data) # Actualizamos el número de secuencia esperado para el siguiente segmento

                    # creamos un ACK para mandarsela al emisor, con el número de secuencia esperado
                    ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1) 
                    self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
                    break
                else: # si no, se envía un ACK con el número de secuencia esperado para que el emisor reenvíe el segmento correcto
                    ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1)
                    self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
        
        # Una vez que se ha recibido el mensaje con la longitud del mensaje
        # se procede a recibir los fragmentos de datos
        while len(self.recv_buffer) < buff_size and self.bytes_remaining > 0:
            # recibimos el segmento del emisor
            segment, _ = self.udp_socket.recvfrom(self.buffer_size)
            segment_struct: ParsedSegmentTCP = self.parse_segment(segment)

            # si el segmento coincide con el esperado, se procesa
            if segment_struct.seq == self.expected_seq:
                self.recv_buffer += segment_struct.data
                self.bytes_remaining -= len(segment_struct.data) # disminuimos los bytes restantes

                self.expected_seq += len(segment_struct.data)

                ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1)
                self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr) # le mandamos el ACK

            else: # si no coincide, lo ignoramos y volvemos a mandar el último ACK
                ack_segment: ParsedSegmentTCP = ParsedSegmentTCP(self.expected_seq, ack=1)
                self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)
        
        # Finalmente guardamos en el buffer los segmentos unificados 
        # y lo que queda fuera del tamaño del buffer se guarda como resto en él
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
                    #Detener timer en caso de éxito
                    try:
                        self.udp_socket.stop_timer(0)
                    except Exception:
                        pass
                    break
            except (socket.timeout, TimeoutError, ConnectionResetError):
                # Detener timer antes de reintentar
                try:
                    self.udp_socket.stop_timer(0)
                except Exception:
                    pass
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
                    
                    # Estado TIME_WAIT.
                    # No cerramos al instante. Esperamos por si el servidor perdió nuestro 
                    # último ACK y retransmite su FIN.
                    try:
                        self.udp_socket.settimeout(self.timeout * 3) # Esperar 3 ciclos
                        while True:
                            extra_bytes, _ = self.udp_socket.recvfrom(self.buffer_size)
                            extra_seg = self.parse_segment(extra_bytes)
                            if extra_seg.fin == 1:
                                self.udp_socket.sendto(self.create_segment(last_ack), self.dest_addr)
                    except (socket.timeout, TimeoutError, ConnectionResetError):
                        # Si ocurre timeout aquí, significa que el servidor no insistió más 
                        # y recibió el ACK con éxito. Podemos cerrar seguros.
                        pass 
                    
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
                else:
                    # Si llega un segmento sin FIN, el cliente probablemente
                    # perdió el último ACK de los datos. Reenviamos el ACK.
                    ack_segment = ParsedSegmentTCP(self.expected_seq, ack=1)
                    self.udp_socket.sendto(self.create_segment(ack_segment), self.dest_addr)

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
                    try:
                        self.udp_socket.stop_timer(0)
                    except Exception:
                        pass
                    break
                # El cliente retransmitió su FIN porque perdió nuestro ACK.
                elif ack_segment.fin == 1:
                    ack_to_client = ParsedSegmentTCP(ack_segment.seq + 1, ack=1)
                    self.udp_socket.sendto(self.create_segment(ack_to_client), self.dest_addr)

            except (socket.timeout, TimeoutError, ConnectionResetError):
                try:
                    self.udp_socket.stop_timer(0)
                except Exception:
                    pass
                continue

        # Liberamos los recursos asociados al socket UDP subyacente.
        self.udp_socket.close()
        

