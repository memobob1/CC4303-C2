import time
import SocketTCP

server_address = ('localhost', 8000)

def menu():
    print("\n========================================================")
    print("      SUITE DE PRUEBAS GO-BACK-N Y CONGESTION CONTROL   ")
    print("========================================================")
    print("1. [GBN + CC] Timeout en Slow Start")
    print("2. [GBN + CC] Timeout en Congestion Avoidance")
    print("3. [GBN sin CC] Caso borde: ACK mayor al esperado (acumulativo)")
    print("4. [GBN sin CC] Timeout y retransmision Go-Back-N (paquetes 0..N)")
    print("5. Ejecutar todas las pruebas en secuencia")
    print("0. Salir")
    print("========================================================")



# =====================================================================
# CASO 1: GBN + CC -> Timeout en Slow Start
# =====================================================================
def test_timeout_in_slow_start():
    print("\n------------------------------------------------------------")
    print(">>> TEST 1: GBN + Congestion Control -> Timeout en Slow Start")
    print("------------------------------------------------------------")
    print("[Explicacion] Al inicio estamos en Slow Start con ssthresh=None.")
    print("Se descarta el 1er ACK en el receptor para forzar el Timeout:")
    print("  - Vence el timer en Slow Start.")
    print("  - ssthresh se fija en int(cwnd / 2).")
    print("  - cwnd se resetea a 1 MSS y continúa en Slow Start.")
    print("------------------------------------------------------------\n")

    client = SocketTCP.SocketTCP()
    client.timeout = 0.8
    client.set_congestion_control(True)
    client.set_debug(True)
    client.connect(server_address)

    real_recvfrom = client.udp_socket.recvfrom
    ack_dropped = False

    def drop_ack_recvfrom(buffer_size):
        nonlocal ack_dropped
        while True:
            ans, addr = real_recvfrom(buffer_size)
            parsed = client.parse_segment(ans)
            if parsed.ack and not ack_dropped:
                print(f"\n[SIMULADOR DE RED] >>> Descartando ACK seq={parsed.seq} en Slow Start <<<")
                print("[SIMULADOR DE RED] Esperando a que el Timer venza y dispare TimeoutError...")
                ack_dropped = True
                continue
            return ans, addr

    client.udp_socket.recvfrom = drop_ack_recvfrom

    msg = b"Mensaje para probar Timeout en Slow Start con TCP Tahoe. 1234567"
    client.send(msg, mode="go_back_n")
    client.udp_socket.recvfrom = real_recvfrom # Restauramos antes del close
    client.close()
    print("\n[TEST 1] Concluido con exito.\n")


# =====================================================================
# CASO 2: GBN + CC -> Timeout en Congestion Avoidance
# =====================================================================
def test_timeout_in_congestion_avoidance():
    print("\n------------------------------------------------------------")
    print(">>> TEST 2: GBN + Congestion Control -> Timeout en Congestion Avoidance")
    print("------------------------------------------------------------")
    print("[Explicacion] Se envia un archivo largo:")
    print("1) En Slow Start se descarta el primer ACK para forzar un 1er Timeout (ssthresh = 4).")
    print("2) La ventana crece y entra en 'congestion avoidance'.")
    print("3) Estando en 'congestion avoidance', se descartan los ACKs en vuelo para forzar el 2do Timeout:")
    print("   - ssthresh se actualiza a la mitad de la nueva cwnd (ej. ssthresh = 16).")
    print("   - cwnd se resetea a 1 MSS = 8.")
    print("   - El estado regresa a 'slow start'.")
    print("------------------------------------------------------------\n")

    client = SocketTCP.SocketTCP()
    client.timeout = 0.5
    client.set_congestion_control(True)
    client.set_debug(True)
    client.connect(server_address)

    real_recvfrom = client.udp_socket.recvfrom
    events = {'first': False, 'second': False}

    def drop_ack_recvfrom(buffer_size):
        while True:
            ans, addr = real_recvfrom(buffer_size)
            parsed = client.parse_segment(ans)
            
            # 1er Timeout: en Slow Start (para fijar ssthresh inicial bajo)
            if parsed.ack and not events['first']:
                print(f"\n[SIMULADOR] >>> 1er TIMEOUT: Descartando ACK={parsed.seq} en Slow Start <<<")
                events['first'] = True
                continue
                
            # 2do Timeout: cuando estemos en Congestion Avoidance y la ventana ya haya crecido
            if parsed.ack and events['first'] and not events['second'] and client.congestion_controler.is_state_congestion_avoidance() and client.congestion_controler.get_cwnd() >= 24:
                print(f"\n[SIMULADOR] >>> 2do TIMEOUT: Descartando ACKs en vuelo para forzar TIMEOUT EN CONGESTION AVOIDANCE (cwnd={client.congestion_controler.get_cwnd()}, ssthresh={client.congestion_controler.get_ssthresh()}) <<<")
                events['second'] = True
                # Esperamos descartando ACKs en vuelo hasta que venza el timer de SocketUDP
                while True:
                    if True in client.udp_socket.announce_timeout:
                        timer_idx = client.udp_socket.announce_timeout.index(True)
                        client.udp_socket.announce_timeout[timer_idx] = False
                        raise TimeoutError(f"Timer {timer_idx}")
                    try:
                        client.udp_socket.socket_udp.recvfrom(buffer_size)
                        continue
                    except BlockingIOError:
                        continue
                
            return ans, addr

    client.udp_socket.recvfrom = drop_ack_recvfrom

    # Mensaje suficientemente largo (200 bytes)
    msg = b"Mensaje largo para Congestion Avoidance: 0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF"
    client.send(msg, mode="go_back_n")
    client.udp_socket.recvfrom = real_recvfrom # Restauramos antes del close
    client.close()
    print("\n[TEST 2] Concluido con exito.\n")


# =====================================================================
# CASO 3: GBN sin CC -> Caso borde: ACK mayor al esperado (acumulativo)
# =====================================================================
def test_ack_greater_than_expected():
    print("\n------------------------------------------------------------")
    print(">>> TEST 3: GBN SIN CC -> ACK acumulativo mayor al esperado")
    print("------------------------------------------------------------")
    print("[Explicacion] Se simula la perdida de los primeros 3 ACKs que")
    print("envia el receptor. Al llegar el 4to ACK (acumulativo), su seq")
    print("es mucho mayor al esperado en la base. Go-Back-N debe avanzar")
    print("la ventana directamente al siguiente paquete confirmado.")
    print("------------------------------------------------------------\n")

    client = SocketTCP.SocketTCP()
    client.set_congestion_control(False) # Ventana fija de 8
    client.set_debug(True)
    client.connect(server_address)

    real_recvfrom = client.udp_socket.recvfrom
    acks_dropped = 0

    def drop_acks_recvfrom(buffer_size):
        nonlocal acks_dropped
        while True:
            ans, addr = real_recvfrom(buffer_size)
            parsed = client.parse_segment(ans)
            # Descartamos los primeros 3 ACKs de datos que lleguen
            if parsed.ack and acks_dropped < 3:
                acks_dropped += 1
                print(f"[SIMULADOR] *** Descartando ACK seq={parsed.seq} ({acks_dropped}/3) ***")
                continue
            if acks_dropped == 3 and parsed.ack:
                print(f"\n[SIMULADOR] *** Llego ACK acumulativo mayor (seq={parsed.seq})! La ventana debe saltar varios pasos ***\n")
                acks_dropped += 1
            return ans, addr

    client.udp_socket.recvfrom = drop_acks_recvfrom

    msg = b"Probando ACK acumulativo en Go-Back-N sin control de congestion."
    client.send(msg, mode="go_back_n")
    client.udp_socket.recvfrom = real_recvfrom # Restauramos antes del close
    client.close()
    print("\n[TEST 3] Concluido con exito.\n")


# =====================================================================
# CASO 4: GBN sin CC -> Falla Timeout y ocurre retransmisión Go-Back-N
# =====================================================================
def test_timeout_and_go_back_n():
    print("\n------------------------------------------------------------")
    print(">>> TEST 4: GBN SIN CC -> Timeout y Retransmision Go-Back-N")
    print("------------------------------------------------------------")
    print("[Explicacion] Se transmiten 8 paquetes en ventana fija.")
    print("Se simula que se pierde el paquete 0 de la ventana.")
    print("Al vencer el timeout, el emisor debe retransmitir TODOS")
    print("los paquetes de la ventana actual (Go-Back-N).")
    print("------------------------------------------------------------\n")

    client = SocketTCP.SocketTCP()
    client.set_congestion_control(False) # Ventana fija = 8
    client.set_debug(True)
    client.connect(server_address)

    real_sendto = client.udp_socket.sendto
    dropped_packet = False

    def drop_first_data_sendto(data, addr, timer_index=-1):
        nonlocal dropped_packet
        parsed = client.parse_segment(data)
        # Descartamos el primer paquete con payload de datos
        if not dropped_packet and parsed.data and parsed.data != b"80":
            print(f"\n[SIMULADOR] *** Perdiendo paquete base seq={parsed.seq} ***")
            print("[SIMULADOR] Los demas paquetes de la ventana seguiran saliendo, pero provocara Timeout!")
            dropped_packet = True
            if timer_index != -1 and client.udp_socket.timeout > 0:
                from threading import Timer
                client.udp_socket.timer_list[timer_index] = Timer(
                    client.udp_socket.timeout, client.udp_socket._time_up_function, args=(timer_index,)
                )
                client.udp_socket.timer_list[timer_index].start()
            return len(data)
            
        if timer_index != -1:
            return real_sendto(data, addr, timer_index)
        return real_sendto(data, addr)

    client.udp_socket.sendto = drop_first_data_sendto

    msg = b"01234567" * 10 # 80 bytes = 10 paquetes de 8 bytes
    client.send(msg, mode="go_back_n")
    client.udp_socket.sendto = real_sendto # Restauramos antes del close
    client.close()
    print("\n[TEST 4] Concluido con exito.\n")


if __name__ == "__main__":
    while True:
        menu()
        choice = input("Seleccione una opcion (0-5): ").strip()
        if choice == "1":
            test_timeout_in_slow_start()
        elif choice == "2":
            test_timeout_in_congestion_avoidance()
        elif choice == "3":
            test_ack_greater_than_expected()
        elif choice == "4":
            test_timeout_and_go_back_n()
        elif choice == "5":
            test_timeout_in_slow_start()
            time.sleep(1)
            test_timeout_in_congestion_avoidance()
            time.sleep(1)
            test_ack_greater_than_expected()
            time.sleep(1)
            test_timeout_and_go_back_n()
        elif choice == "0":
            print("Saliendo...")
            break
        else:
            print("Opcion no valida.")