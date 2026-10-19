# CC4303-C2

# Informe parte 3: Stop and Wait

Integrantes: César Barrueto, Jaime Sepúlveda
Fecha: 19/10/2026
Profesora: Ivana Bachmann.
Auxiliar: Julián Ferreira

Enlace de github: https://github.com/memobob1/CC4303-C2/tree/main/P3

### La estructura de datos ParsedSegmentTCP

Para almacenar eficientemente la información de un segmento TCP, se implementó la estructura ParsedSegmentTCP con los siguientes campos:

- seq: Un entero que contiene el número de secuencia escrito en el segmento.
- syn: Un entero cuyo valor es 0 o 1. Representa si el segmento envía un mensaje de sincronización.
- ack: Un entero cuyo valor es 0 o 1. Representa si el segmento envía un mensaje de confirmación.
- fin: Un entero cuyo valor es 0 o 1. Representa si el segmento envía un mensaje de término de comunicación.
- data: Los contenidos, de algún archivo, que se quieren enviar al receptor. Se guarda en bytes y el valor por defecto es la cadena de bytes vacía. 

### La función estática parse_segment

Recibe un segmento TCP escrito en bytes y retorna una instancia de ParsedSegmentTCP.

Un segmento TCP está organizado por una sección de headers, los primeros (SEQ_NBYTES + 1) bytes, y una sección de datos. Así se descompone:
- Los primeros SEQ_NBYTES bytes contienen el número de secuencia del segmento.
- El byte (SEQ_NBYTES + 1) representa si el segmento incluye un mensaje SYN, ACK y/o FIN:
  - Su tercer bit menos significativo indica el valor de SYN.
  - Su segundo bit menos significativo indica el valor de ACK.
  - Su bit menos significativo indica el valor de FIN.
  - Un valor 0 representa NO, mientras que un valor 1 representa SÍ.
- El resto de bytes del segmento (la sección de datos) almacenan los contenidos que se desean enviar al receptor.

Después de extraer la información del segmento, se construye y retorna la instancia de ParsedSegmentTCP.

### La función estática create_segment

Recibe una instancia de ParsedSegmentTCP y convierte su información en una cadena de bytes que representa un segmento TCP.

1) Los primeros SEQ_NBYTES bytes de la cadena son el número de secuencia almacenado en la estructura.
2) El byte (SEQ_NBYTES + 1) se arma de la siguiente forma:
    - Se multiplica por 4 el valor del campo "syn" de ParsedSegmentTCP. Si "syn" es 1,
    entonces se obtiene un 4 que se escribe como "0000 0100" en un byte. Es decir, marca un 1 en el tercer bit menos significativo del byte.
    - Se multiplica por 2 el valor del campo "ack" de ParsedSegmentTCP. Si "ack" es 1,
    entonces se obtiene un 2 que se escribe como "0000 0010" en un byte. Es decir, marca un 1 en el segundo bit menos significativo del byte.
    - Se conserva el valor del campo "fin" de ParsedSegmentTCP. Si "fin" es 1,
    entonces se obtiene un 1 que se escribe como "0000 0001" en un byte. Es decir, marca un 1 en el bit menos significativo del byte.
  
    Como trabajamos con números enteros, simplemente se suman los números para obtener el byte completo. Por ejemplo, al sumar un
    "syn" igual a 1 y "ack" igual a 1 se obtiene el número 6 que equivale al byte "0000 0110". Esto concuerda con la organización del segmento
    TCP definido en la función parse_segment.
    
3) Se concatenan los primeros SEQ_NBYTES con el byte (SEQ_NBYTES + 1) para crear la sección de headers del segmento TCP. Finalmente, a la sección de headers
   se concatenan los bytes almacenados en el campo "data" para obtener el segmento TCP completo.

### Decisiones de diseño

Se decidió crear una clase para

## La clase SocketTCP

Esta es la clase principal de la actividad. Representa un socket orientado a conexión que utiliza Stop and Wait. Sus campos son:

- udp_socket: Un socket UDP que permite enviar y recibir mensajes de un dirección determinada.
- timeout: Un float que indica el tiempo máximo que puede esperar un emisor antes de reenviar un mensaje al receptor.
- dest_addr: La dirección hacia donde el SocketTCP envía mensajes. Es una tupla (IP, puerto). Inicialmente su valor es None.
- seq: Un entero que indica el número de secuencia actual que posee el SocketTCP. Inicialmente es un valor aleatorio entre 0 y 100.
- buffer_size: El tamaño del buffer del socket UDP. Es igual a (SEQ_NBYTES + 1 + 16). En este caso, su valor es 19.
- recv_buffer: Una cadena de bytes. Este buffer almacena los datos entregados desde otro SocketTCP. Inicialmente es una cadena de bytes vacía.
- bytes_remaining: Un entero que indica la cantidad de bytes que faltan por recibir del emisor. Inicialmente su valor es 0.

## El método bind

Recibe una dirección (IP, puerto) y establece que el SocketTCP escuche en esa dirección recibida. Simplemente utiliza la función con el mismo nombre "bind"
implementada por el socket UDP.

## El método connect

Recibe una dirección e inicia una conexión con un SocketTCP que esté escuchando en la dirección entregada. Esta función implementa el three-way handshake de parte del emisor.

### Envío del primer handshake

1) Se utiliza el método create_segment(ParsedSegmentTCP(self.seq, syn=1)) para crear un segmento TCP con el mensaje SYN y el número de secuencia del emisor
2) Como este SocketTCP es emisor, entonces se establece el timeout con la función udp_socket.settimeout(self.timeout). Este timeout estará activo
   en todo momento y nos permitirá implementar el Stop and Wait.
3) El socket UPD del emisor envía el segmento TCP a la dirección recibida donde se ubica el socket receptor.

### Recepción del segundo handshake

4) El socket UDP espera a recibir un segmento TCP del socket receptor.
    - Si transcurre más de "self.timeout" segundos, nos devolvemos al paso 3.
    - Si el emisor recibe un segmento TCP, se revisa que ese segmento tenga el número de secuencia (self.seq + 1) y además incluya
      un SYN y un ACK. De lo contrario, nos devolvemos al paso 3.
5) El mensaje recibido efectivamente es el segundo handshake. En la sección de datos de ese mensaje se guarda la dirección (IP, puerto)
   del nuevo SocketTCP que se utilizará para comunicarse con este socket emisor. Almacenamos la dirección en el campo "dest_addr".

### Envío del tercer handshake
   
6) Se utiliza el método create_segment(ParsedSegmentTCP(self.seq + 2, ack=1)) para crear un segmento TCP con el mensaje ACK y el número de
   secuencia (self.seq + 2).
7) Usando la dirección original que recibió el método, se envía el nuevo segmento TCP al socket receptor original.
8) Finalmente se actualiza el número de secuencia del emisor a (self.seq + 3).

## El método accept

Espera una petición de tipo SYN para iniciar una comunicación con otro socket, y retorna un nuevo SocketTCP junto con su dirección.
El socket que utilice este método se comportará como el socket receptor del three-way handshake, por lo tanto, no utiliza timeouts.

### Recepción del primer handshake

1) El socket UDP espera indefinidamente a recibir un segmento TCP de algún socket emisor.
2) El socket UDP recibe un segmento TCP junto con la dirección del socket emisor.
3) Revisa que el segmento TCP tenga un mensaje SYN. De lo contrario, nos devolvemos al paso 1.
4) Se almacena el número de secuencia del segmento TCP en la variable "other_seq", ese es el número de secuencia actual del socket emisor.

### Creación del nuevo SocketTCP

5) Se crea una nueva instancia de SocketTCP. Se establece que el campo "dest_addr" del nuevo socket es la dirección del socket emisor.
   Ahora el nuevo socket podrá enviar mensajes al socket emisor.
6) Se genera una nueva dirección (IP, puerto) utilizando el puerto 0. Luego, se utiliza el método bind para que el socket UDP del nuevo
   SocketTCP escuche en la dirección generada. Se usa el puerto es 0, ya que esto indica al computador que debe reemplazar el puerto 0 con
   cualquier puerto desocupado.

### Envío del segundo handshake
   
7) Se utiliza el método create_segment(ParsedSegmentTCP(other_seq + 1, syn=1, ack=1)) para crear un segmento TCP con el mensaje SYN + ACK y el número de
   secuencia (other_seq + 1).
8) El socket UDP del socket original envía el segmento TCP a la dirección del socket emisor.

### Recepción del tercer handshake

9) El socket UDP del socket original espera a recibir un segmento TCP del socket emisor.
     - Si se recibe un segmento TCP, se revisa que ese segmento tenga el número de secuencia (other_seq + 2) y además incluya
      un ACK. De lo contrario, nos devolvemos al paso 8.
10) Se establece que el número de secuencia del nuevo SocketTCP es (other_seq + 3).
11) Se retorna el nuevo SocketTCP junto con la dirección de ese nuevo SocketTCP.

## El método send

Recibe una cadena de bytes y las envía al socket receptor con el que estableció un canal de comunicación.

Recordar que existen tres sockets en todo este proceso. El socket emisor, el socket receptor original, y el nuevo socket receptor que fue creado para
comunicarse con el socket emisor. Llamaremos "socket servidor" al socket receptor original.

Por otro lado "len(data)" se refiere al largo de la cadena de bytes que representa la sección de datos de un segmento TCP. Es similar
a "len(block)" que representa el largo de un bloque de bytes (usualmente es 16).

Ahora explicaremos el funcionamiento de send:

### Envío del largo del mensaje

1) Crea un segmento TCP con el número de secuencia del socket emisor y una sección de datos que contiene el largo de la cadena de bytes recibida.
2) Envía el segmento TCP al socket receptor usando el campo "dest_addr".
3) Espera a recibir un segmento TCP de otro SocketTCP. También recibe la dirección de donde proviene el mensaje.
    - Si transcurre más de "self.timeout" segundos, nos devolvemos al paso 2.
    - Es posible que el emisor reciba un segmento TCP cuyo número de secuencia es (self.seq - 2) y además incluye
      un SYN y un ACK. Lo anterior es el formato del segundo handshake. Eso significa que el socket servidor sigue esperando a
      recibir el tercer handshake. Para solucionarlo, se crea un tercer handshake y se envía al socket servidor. Luego, nos devolvemos al paso 2.
    - Si se recibe un segmento TCP cuyo número de secuencia es (self.seq + len(data)) junto con un mensaje ACK, entonces se avanza al paso 4.
      De lo contrario, nos devolvemos al paso 2.
4) Se actualiza el número de secuencia del emisor. Ahora es (self.seq + len(data)).

### Envío del mensaje

Se divide el mensaje en bloques de 16 bytes, a excepción del último bloque que puede tener menos de 16 bytes.

5) Se crea un segmento TCP cuyo número de secuencia es "self.seq" y contiene el bloque i-ésimo en la sección de datos.
6) Se envía el segmento TCP al socket receptor.
7) Espera a recibir otro segmento TCP del socket receptor.
     - Si transcurre más de "self.timeout" segundos, nos devolvemos al paso 6.
     - Si se recibe un segmento TCP, se revisa que su número de secuencia sea (self.seq + len(block)) y contenga el mensaje ACK.
       De lo contrario, se retorna al paso 6
8) Se actualiza el número de secuencia del emisor. Ahora es (self.seq + len(block)).
9) Se actualiza el valor de "i". Ahora es (i + len(block)) y se retorna al paso 5 siempre y cuando "i" sea menor que el largo total
   mensaje (que se obtuvo en el paso 1).

## El método recv

Recibe un mensaje de otro socket. El tamaño del mensaje no puede superar los "buff_size" bytes, donde "buff_size" es un parámetro entregado a esta función.

Este método puede ser ejecutada múltiples veces por el socket receptor. Sin embargo, la primera vez que se ejecuta, siempre
recibe el largo del mensaje completo.

### Recepción del largo del mensaje

1) Si se cumple "self.bytes_remaining == 0 and len(self.recv_buffer) == 0", entonces es la primera vez que el SocketTCP ejecuta recv.
   Avanzamos al paso 2. De lo contrario, se avanza al paso 7.
2) Se espera indefinidamente a recibir un segmento TCP envíado por el socket emisor.
     - Si el número de secuencia del segmento TCP recibido es igual al número de secuencia de este socket receptor, entonces se
       avanza al paso 3. De lo contrario, nos devolvemos al paso 2.
3) Se extrae el largo del mensaje de la sección de datos del segmento TCP. Y se guarda ese valor en "self.bytes_remaining".
4) Se crea un segmento TCP cuyo número de secuencia es "self.seq + len(data)" y contiene un mensaje ACK.
5) Se envía el segmento TCP al socket emisor.
6) Se actualiza el número de secuencia del receptor. Ahora es (self.seq + len(data)).

### Recepción de "buff_size" bytes del mensaje.

7) Si se cumple "len(self.recv_buffer) < buff_size and self.bytes_remaining > 0", es decir, si faltan bytes por recibir y aún
   queda espacio en el buffer, entonces se avanza al paso 8. De lo contrario, pasamos al paso 14.
8) Se espera indefinidamente a recibir un segmento TCP envíado por el socket emisor.
     - Si el número de secuencia del segmento TCP recibido es igual al número de secuencia de este socket receptor, entonces se
       avanza al paso 9.
     - Si el número de secuencia del segmento TCP recibido es MENOR al número de secuencia de este socket receptor, entonces
       es posible que se haya perdido algún ACK. Por ese motivo, se envía un segmento TCP, con el número de secuencia "self.seq"
       y un mensaje ACK, al socket emisor. Finalmente, nos devolvemos al paso 7.
     - En cualquier otro caso, se retorna al paso 7.
9) Se agregan los contenidos del segmento TCP al campo "self.recv_buffer".
10) Se resta el largo de los contenidos recibidos al valor del campo "self.bytes_remaining".
11) Se suma el largo de los contenidos al número de secuencia del receptor.
12) Se envía un segmento TCP con el nuevo número de secuencia "self.seq" y un mensaje ACK.
13) Se retorna al paso 7 para seguir recibiendo bytes.

### Retornar el mensaje recibido

14) Se seleccionan los primeros "buff_size" bytes de "self.recv_buffer" y se guardan en la variable "return_data".
15) Se eliminan los primeros "buff_size" bytes de "self.recv_buffer".
16) Se retorna "return_data".

## El método close



