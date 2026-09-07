# TD5 TP1: Recorte consciente de audio

Trabajo práctico 1 de Tecnología Digital V (Diseño de Algoritmos, UTDT, segundo semestre 2026).
Dada una grabación representada como una secuencia de pulsos con un vector de características por
pulso, el problema pide conservar exactamente k pulsos (incluyendo el primero y el último) de modo
que la suma de los costos de los saltos sea mínima.

Integrantes: Sofía Parisi, Luz Alba Posse y Victoria Schenone Fernández.

## Estructura

```
enunciado/          consigna del trabajo
TP1/
  source/           implementación en C++ (fuerza bruta, backtracking y programación dinámica)
  python/           reimplementación en Python de BT y PD, scripts de extracción y reconstrucción
  input/            instancias de prueba
  audio/            grabaciones usadas en la experimentación (no se versionan)
  output/           selecciones y mediciones generadas por las corridas
  Makefile
```

## Compilación y ejecución

```
cd TP1
make
./radioedit --instancia input/ejemplo.txt --algoritmo pd
```

Los algoritmos disponibles son `fb`, `bt` y `pd`. Con `--csv <archivo>` se registra el tiempo de cada
corrida y con `--salida <archivo>` se elige dónde guardar la selección.
