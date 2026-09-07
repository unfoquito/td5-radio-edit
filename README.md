# TD5 TP1: Recorte consciente de audio

Trabajo práctico 1 de Tecnología Digital V (Diseño de Algoritmos, UTDT, segundo semestre 2026).
Dada una grabación representada como una secuencia de pulsos con un vector de características por
pulso, el problema pide conservar exactamente k pulsos (incluyendo el primero y el último) de modo
que la suma de los costos de los saltos sea mínima.

Integrantes: Sofía Parisi, Luz Alba Posse y Victoria Schenone Fernández.

## Estructura

```
enunciado/          consigna del trabajo
informe/            informe en LaTeX (informe.tex) y sus figuras
TP1/
  source/           implementación en C++ (fuerza bruta, backtracking y programación dinámica)
  python/           reimplementación en Python de BT y PD, generador de instancias, verificador
                    cruzado y scripts de extracción y reconstrucción de audio
  input/            instancias de prueba: ejemplo.txt del enunciado y input/real/ con las reales
  audio/            grabaciones usadas en la experimentación (no se versionan, ver audio/FUENTES.md)
  output/           selecciones y mediciones generadas por las corridas
  Makefile
```

## Requisitos

- C++: g++ o clang con soporte de C++17 y make. No hay dependencias externas.
- Python 3.8 o superior. Los algoritmos, el generador y el verificador usan solo la biblioteca
  estándar. Solo extraer.py y el backend mp3 de reconstruir.py necesitan librosa, numpy y
  soundfile (ver `TP1/python/requirements.txt`).

## C++: compilación y ejecución

```
cd TP1
make                 # genera el binario radioedit (compila sin warnings con -Wall -Wextra)
make run-ejemplo     # corre pd sobre input/ejemplo.txt
make clean           # borra el binario
make clean-output    # borra las salidas de output/ (conserva los .gitkeep)
```

Uso del binario:

```
./radioedit --instancia <archivo> --algoritmo <fb|bt|pd> [--salida <archivo>] [--csv <archivo>]
            [--sin-poda-factibilidad] [--sin-poda-optimalidad]
```

- `--algoritmo`: `fb` (fuerza bruta), `bt` (backtracking) o `pd` (programación dinámica, valor por
  defecto).
- `--salida`: archivo donde se escribe la selección, una sola línea con los k índices en base 1
  separados por espacio. Por defecto `output/numericos/seleccion_<algoritmo>.txt`; el directorio se
  crea si no existe.
- `--csv`: agrega una fila `algoritmo,n,d,k,costo,ms` al archivo indicado (escribe la cabecera si
  el archivo es nuevo).
- `--sin-poda-factibilidad` y `--sin-poda-optimalidad`: apagan cada poda de `bt` por separado, para
  los experimentos. Con `bt` se imprime además la cantidad de nodos visitados.

Ejemplo:

```
./radioedit --instancia input/ejemplo.txt --algoritmo bt --csv output/numericos/tiempos.csv
```

Por pantalla se muestra la selección, el costo y el tiempo de resolución en milisegundos. Si la
instancia no existe o está mal formada, el programa termina con código 1 y un mensaje que indica
el problema.

Nota sobre el Makefile: se compila con `-ffp-contract=off` para que la norma euclídea dé el mismo
double en todas las plataformas y coincida bit a bit con la versión en Python. Sin esa opción,
clang en arm64 fusiona la multiplicación y la suma en una FMA y los empates pueden resolverse
distinto. En Windows con MinGW usar `mingw32-make` en lugar de `make`.

## Python: reimplementación de BT y PD

`python/algoritmos.py` implementa `bt` y `pd` con la misma interfaz de línea de comandos que el
binario:

```
cd TP1
python3 python/algoritmos.py --instancia input/ejemplo.txt --algoritmo pd
python3 python/algoritmos.py --instancia input/ejemplo.txt --algoritmo bt --sin-poda-optimalidad
```

Las salidas por pantalla, el archivo `--salida` y el CSV tienen el mismo formato que en C++. En la
columna `algoritmo` del CSV se usa la etiqueta `py-bt` o `py-pd`, así se pueden mezclar mediciones
de los dos lenguajes en un mismo archivo. Los scripts `python/backtracking.py` y
`python/programacion_dinamica.py` son atajos que fijan el algoritmo (los usa el verificador).

Para usar el entorno virtual del repositorio (hace falta solo para extraer.py y reconstruir.py):

```
python3 -m venv .venv
.venv/bin/pip install -r TP1/python/requirements.txt
```

## Generador de instancias y verificador cruzado

```
cd TP1/python
python3 generador.py --n 60 --d 12 --k 30 --modo estructura --semilla 1 --salida ../input/e60.txt
python3 verificar.py --binario ../radioedit --solvers fb,bt,pd,py-bt,py-pd --cantidad 100
```

`generador.py` escribe instancias en el formato del enunciado con tres modos: `uniforme`,
`estructura` (secciones repetidas, el caso musical) y `adversarial` (todos los pulsos distintos).
`verificar.py` genera instancias chicas al azar, corre los solvers pedidos, valida cada selección y
compara los costos contra un óptimo calculado en Python por fuerza bruta y entre sí. Las
discrepancias se guardan en `output/discrepancias`; termina con código 0 si no hubo ninguna.
Ambos scripts documentan sus opciones con `--help`.

## Audio: extracción y reconstrucción

Con el entorno virtual instalado (ver arriba):

```
cd TP1
../.venv/bin/python python/extraer.py audio/cancion.mp3 --salida input/real/cancion --duracion 60
./radioedit --instancia input/real/cancion.txt --algoritmo pd --salida output/numericos/cancion.txt
../.venv/bin/python python/reconstruir.py audio/cancion.mp3 output/numericos/cancion.txt \
    --pulsos input/real/cancion_pulsos.txt --salida output/audio/cancion_recorte.wav
```

`python/extraer_todo.sh` regenera todas las instancias de `input/real` a partir del audio que
descarga `audio/descargar.sh` (fuentes y licencias en `audio/FUENTES.md`).

## Experimentación

Toda la experimentación del informe se reproduce desde un único script con subcomandos, que
corre el binario y la versión en Python por subprocess, toma la mediana de tres corridas del
tiempo que imprime cada programa y guarda los resultados en CSV:

```
cd <raíz del repo>
.venv/bin/python TP1/python/experimentos.py --help     # lista los subcomandos
.venv/bin/python TP1/python/experimentos.py todo       # generar + e1 ... e6, unos 25 minutos
.venv/bin/python TP1/python/experimentos.py e3         # un solo experimento
.venv/bin/python TP1/python/experimentos.py figuras    # regenera las figuras desde los CSV
.venv/bin/python TP1/python/experimentos.py todo --rapido   # versión reducida, menos de un minuto
```

- `generar` escribe las instancias sintéticas en `TP1/input/sinteticas/<familia>/` con una semilla
  fija por familia, n, k y d (`semilla_de` en el script), así que las corridas son reproducibles.
  Las familias son `uniforme` (puntos uniformes en [0,1]^d), `estructura` (patrón de secciones
  ABBCBB con ruido gaussiano de desvío 0,05) y `adversarial` (grilla de paso 1 en orden aleatorio),
  todas con d = 12 salvo la serie en d del experimento e3.
- `e1` compara los tres exactos (alcance en n y coincidencia de costos), `e2` mide las podas de
  backtracking, `e3` el escalado de la programación dinámica en n, k y d (con memoria pico),
  `e4` C++ contra Python, `e5` las grabaciones reales de `TP1/input/real` (incluye la
  reconstrucción de audio, que necesita el venv y los mp3 de `TP1/audio`) y `e6` los tres exactos
  sobre prefijos de una grabación real.
- Los CSV quedan en `TP1/output/numericos/` (ignorado por git) y las copias finales en
  `informe/datos/`; las figuras van a `informe/figuras/` en PNG a 200 dpi. Con `--reps` se cambia
  la cantidad de repeticiones y con `--timeout` el límite por corrida (60 s, o 150 s en e3 y e4).
- Si el binario `TP1/radioedit` no existe, el script lo compila con `make`.

La máquina y el compilador con que se midieron los tiempos del informe se describen en la sección
de metodología del informe.

## Informe

`informe/informe.tex` se compila con `pdflatex` (dos pasadas para el índice y las referencias).
