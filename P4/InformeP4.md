# Informe Actividad: Control de Congestión (P4)

**Curso:** Redes (CC4303)  
**Integrantes:** César Barrueto, Jaime Sepúlveda.

**Profesora:** Ivana Bachmann
**Auxiliar:** Julián Ferreira 
**Ayudantes:** 

_Disclaimer Uso de IA_: Se utilizó inteligencia artificial como herramienta de apoyo para depurar el código y solucionar errores en casos borde, específicamente para gestionar la expiración de timeouts y agregar bloques try...except que previenen fallos de RuntimeError con los hilos.

## 1. Preguntas Previas (Parte 2)

### (1) ¿Por qué le puede servir usar como base para Go Back-N el código de Stop & Wait de la sección anterior? ¿Qué similitud tiene Go Back-N con Stop & Wait?

Stop & Wait es en realidad un caso particular de Go-Back-N donde el tamaño de la ventana de transmisión es $N = 1$. Ambos protocolos comparten la misma estructura:
- Manejo de números de secuencia y timeouts sobre paquetes no confirmados.
- Uso de ACKs acumulativos para saber hasta qué byte ha recibido el destino.
- Si ocurre un timeout antes de recibir confirmación, se retransmite desde la base de la ventana.

La única diferencia es que en Go-Back-N puede tener más de un segmento enviándose simultáneamente ($N > 1$), requiriendo avanzar la ventana deslizante conforme llegan los ACKs y retransmitir los $N$ elementos si ocurre un timeout.

### (2) En la sección anterior solo se muestra la función send de Stop & Wait, ¿Qué ocurre con la función recv? ¿Esta función cambia con el uso de SocketUDP y SlidingWindowCC?
No cambia en su lógica realmente. En Go-Back-N el receptor sigue la misma lógica donde solo acepta el segmento cuyo número de secuencia coincida exactamente con `expected_seq`. Si llega un paquete duplicado o fuera de orden, simplemente lo descarta y reenvía un ACK con el último `expected_seq` válido. Por lo tanto, la lógica de recepción de Stop & Wait basada en entregar datos en orden estricto se mantiene prácticamente idéntica.



## 2. Implementación de Go-Back-N y Control de Congestión (TCP Tahoe)

Se implementó el mecanismo de TCP Tahoe mediante la clase `CongestionControl`, interactuando con `SlidingWindowCC` y `SocketUDP` dentro de `SocketTCP`:

1. **Estado Inicial (Slow Start):**
   - Comienza con $\text{cwnd} = 1\text{ MSS} = 8\text{ bytes}$ y $\text{ssthresh} = \text{None}$.
   - Cada ACK exitoso recibido incrementa `cwnd` en $+1\text{ MSS}$ (la ventana va creciendo de forma exponencial).
2. **Congestion Avoidance (AIMD):**
   - Si `cwnd >= ssthresh`, el estado pasa a Congestion Avoidance.
   - Cada ACK recibido aumenta la ventana en una fracción $\frac{1}{\text{MSS\_in\_cwnd}}$, aumentando $+1\text{ MSS}$ sólo tras una ronda completa de ACKs.
3. **Manejo de Timeout:**
   - Al vencer el timer del segmento base (índice 0):
     - `ssthresh` se fija en $\lfloor \text{cwnd} / 2 \rfloor$.
     - `cwnd` se resetea a $1\text{ MSS} = 8\text{ bytes}$.
     - El estado vuelve a Slow Start.
     - Se retransmiten todos los paquetes pendientes de la ventana actual (`elements_sent = 0` hacia adelante).
4. **Manejo de Casos Borde:**
   - Si tras encogerse la ventana a 1 llega un ACK acumulativo con un número de secuencia mayor al último de la ventana actual, se avanza la ventana de forma iterativa hasta absorber el ACK o vaciar los datos.



## 3. Pruebas y Resultados

### 3.1. Comportamiento del Control de Congestión sin pérdidas
Si no consideramos pérdidas espontáneas:
- La transmisión comienza en **Slow Start** duplicando la ventana en cada RTT ($\text{cwnd}: 8 \to 16 \to 24 \dots$).
- Como no ocurren timeouts espontáneos, `ssthresh` permanece en `None` y la ventana crece hasta transferir hasta que se envíe todo el mensaje completamente.

### 3.2. Comportamiento del Control de Congestión con pérdidas inducidas
- **Timeout en Slow Start:** Se simuló la pérdida del paquete inicial. El timer expiró, fijando `ssthresh = int(cwnd / 2)`, reseteando `cwnd = 8` y retransmitiendo toda la ventana con éxito.
- **Timeout en Congestion Avoidance:** Al superar `ssthresh`, el algoritmo cambió su estado a `congestion avoidance` creciendo de forma más pausada (lineal). Al forzar la pérdida en esta etapa, el timeout redujo nuevamente `ssthresh` a la mitad de la ventana alcanzada, reseteó `cwnd = 8` y devolvió el estado a `slow start`.



## 4. Comparación Experimental: Go-Back-N con CC vs sin CC

**Configuración del experimento:**
- Archivo transmitido: `100 Bytes` (o payload de prueba).
- Tasa de pérdida: `20%` (mediante netem o descarte manual en código).
- Timeout: `0.5 s`.

### Tabla de Mediciones (5 iteraciones):

| Iteración | Modo | Mensajes / Segmentos Enviados | Tiempo Total (s) |
| :---: | :---: | :---: | :---: |
| **1** | Con Congestion Control (Tahoe) | 31 | 5.3244 |
| **2** | Con Congestion Control (Tahoe) | 37 | 5.6530 |
| **3** | Con Congestion Control (Tahoe) | 37 | 4.1193 |
| **4** | Con Congestion Control (Tahoe) | 38 | 8.4457 |
| **5** | Con Congestion Control (Tahoe) | 35 | 7.2733 |
| **Promedio** | **Con CC** | **35.6** | **6.1631** |
| **1** | Sin Congestion Control (Ventana Fija 8) | 19 | 0.5183 |
| **2** | Sin Congestion Control (Ventana Fija 8) | 50 | 2.6005 |
| **3** | Sin Congestion Control (Ventana Fija 8) | 30 | 1.0499 |
| **4** | Sin Congestion Control (Ventana Fija 8) | 40 | 2.0364 |
| **5** | Sin Congestion Control (Ventana Fija 8) | 50 | 2.9271 |
| **Promedio** | **Sin CC** | **37.5** | **1,8264** |

---

### Análisis y Conclusiones:
**¿Cuál toma menos tiempo en transmitir?**  
  Empíricamente, transmitir Sin CC es más rápido (1.82s frente a 6.16s de Tahoe). Al usar una ventana fija de 8 inyecta paquetes agresivamente, compensando las retransmisiones con velocidad bruta. Tahoe es más lento porque castiga cada pérdida reduciendo su ventana a 1, perdiendo segundos valiosos al reiniciar en Slow Start.


## 5. Cómo ejecutar el cliente (client.py) y servidor (server.py)

Para correr el experimento desde la terminal, debes ejecutar el script del cliente pasándole un argumento n (que debe ser 1 o 2):

`python client.py n`

El valor de n determina el modo de funcionamiento:

Si n = 1: Ejecuta el protocolo Go-Back-N con Control de Congestión (TCP Tahoe).

Si n = 2: Ejecuta el protocolo Go-Back-N sin Control de Congestión (usando una ventana de tamaño fijo).

Nota importante: En ambos modos el modo debug está activado por defecto. Esto significa que durante la ejecución verás impreso en la terminal todo el comportamiento interno del protocolo, incluyendo el estado de la ventana en cada instante, los números de secuencia, las retransmisiones y los eventos de timeout.

Del mismo modo para ejjecutar el servidor, basta con correr el `server.py`.