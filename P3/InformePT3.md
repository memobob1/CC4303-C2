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
