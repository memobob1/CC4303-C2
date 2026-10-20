class CongestionControl:
    def __init__(self, MSS: int):
        self.current_state: str = "slow start" # Estado actual: "slow start" o "congestion avoidance"
        self.MSS = MSS
        self.cwnd = float(MSS)
        self.ssthresh = None

    def get_cwnd(self) -> int:
        """
        Devuelve el tamaño actual de la ventana de congestión.

        Returns:
            int: Tamaño actual de la ventana de congestión (cwnd).
        """
        return int(self.cwnd)

    def get_MSS_in_cwnd(self) -> int:
        """
        Devuelve el número de paquetes MSS que caben en la ventana de congestión.

        Returns:
            int: Número de paquetes MSS en la ventana de congestión.
        """
        return int(self.cwnd) // self.MSS

    def event_ack_received(self):
        """
        Maneja el evento de recepción de un ACK.
        Actualiza el tamaño de la ventana de congestión (cwnd) según el estado actual.
        """

        # Hay 2 casos, si estamos en slow start o si estamos en congestion avoidance
        if self.is_state_slow_start(): # Caso 1: Slow Start
            
            # Aumentamos 1 MSS por cada ACK recibido
            self.cwnd += self.MSS 

            # Si ssthresh no es None y cwnd >= ssthresh, cambiamos a congestion avoidance
            if self.ssthresh is not None and self.cwnd >= self.ssthresh:
                self.current_state = "congestion avoidance"

        elif self.is_state_congestion_avoidance(): # Caso 2: Congestion Avoidance
            # Obtenemos los paquetes MSS que caben en la ventana de congestión
            mss_in_cwnd = self.get_MSS_in_cwnd()

            self.cwnd += self.MSS * (1/mss_in_cwnd) # Aumento en 1/mss_in_cwn

    def event_timeout(self):
        """
        Maneja el evento de timeout.
        Actualiza ssthresh, cwnd y el estado de control de congestión.
        """
        # 1. Actualizamos/inicializamos el ssthresh 
        self.ssthresh = int(self.cwnd / 2)

        # 2. Reseteo de la ventana de congestión a 1 MSS
        self.cwnd = float(self.MSS)

        # 3. Si el estado actual es "congestion avoidance", volvemos a "slow start"
        if self.is_state_congestion_avoidance():
            # Si estábamos en Congestion Avoidance, volvemos a Slow Start
            self.current_state = "slow start"
        

    def is_state_slow_start(self) -> bool:
        """
        Verifica si el estado actual es "slow start".

        Returns:
            bool: True si el estado actual es "slow start", False en caso contrario.
        """
        return self.current_state == "slow start"

    def is_state_congestion_avoidance(self) -> bool:
        """
        Verifica si el estado actual es "congestion avoidance".

        Returns:
            bool: True si el estado actual es "congestion avoidance", False en caso contrario.
        """
        return self.current_state == "congestion avoidance"

    def get_ssthresh(self) -> float:
        """
        Devuelve el valor actual de ssthresh.

        Returns:
            float: Valor actual de ssthresh.
        """
        return self.ssthresh
