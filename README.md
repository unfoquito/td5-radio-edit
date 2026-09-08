# TD5 TP1: Recorte consciente de audio

Trabajo práctico 1 de Tecnología Digital V (Diseño de Algoritmos, UTDT, segundo semestre 2026).
Dada una grabación representada como una secuencia de pulsos con un vector de características por
pulso, el problema pide conservar exactamente k pulsos (incluyendo el primero y el último) de modo
que la suma de los costos de los saltos sea mínima.

Integrantes: Sofía Parisi, Luz Alba Posse y Victoria Schenone Fernández.

## Estructura

```
enunciado/          consigna del trabajo
informe/            informe en LaTeX (informe.tex y secciones/), los CSV finales de la
                    experimentación (datos/) y las figuras (figuras/)
TP1/
  source/           implementación en C++ (fuerza bruta, backtracking y programación dinámica)
  python/           reimplementación en Python de BT y PD (algoritmos.py), generador de
                    instancias, verificador cruzado, experimentos.py con figuras.py y los
                    programas de extracción y reconstrucción de audio
  input/            instancias de prueba. ejemplo.txt es la del enunciado, input/real/ tiene las
                    reales e input/sinteticas/ las 180 sintéticas que usa la experimentación
  audio/            grabaciones usadas en la experimentación (no se versionan, ver audio/FUENTES.md)
                    con descargar.sh y recortar_escenas.sh para obtenerlas
  output/           selecciones y mediciones generadas por las corridas
  Makefile
```

`informe/figuras/` contiene también las figuras auxiliares de cada experimento (series en k y
en d, tiempos de las podas, comparación croma contra MFCC, matrices de los otros dos temas)
que el informe no incluye por el límite de páginas.

## Requisitos

- C++: g++ o clang con soporte de C++17 y make. No hay dependencias externas.
- Python 3.8 o superior. Los algoritmos, el generador y el verificador usan solo la biblioteca
  estándar. experimentos.py necesita matplotlib para las figuras. Solo extraer.py y la lectura
  de mp3 de reconstruir.py necesitan librosa, numpy y soundfile. Los cuatro paquetes están en
  `TP1/python/requirements.txt`.
- Los programas de audio necesitan además curl (descargar.sh) y ffmpeg con ffprobe
  (recortar_escenas.sh y extraer_todo.sh). Nada más los usa.

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
  separados por espacio. Por defecto `output/numericos/seleccion_<algoritmo>.txt`. El directorio
  se crea si no existe.
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

El Makefile compila con `-ffp-contract=off` para que la norma euclídea dé el mismo double en
todas las plataformas y coincida bit a bit con la versión en Python. Sin esa opción, clang en
arm64 fusiona la multiplicación y la suma en una FMA y los empates pueden resolverse distinto.
En Windows con MinGW usar `mingw32-make` en lugar de `make`. El objetivo `clean-output` usa el
`find` de Unix, así que en Windows requiere un shell tipo Unix (Git Bash o MSYS2).

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
de los dos lenguajes en un mismo archivo. Los programas `python/backtracking.py` y
`python/programacion_dinamica.py` son atajos que fijan el algoritmo (los usa el verificador).

Para usar el entorno virtual del repositorio (hace falta para experimentos.py, extraer.py y
reconstruir.py):

```
python3 -m venv .venv
.venv/bin/pip install -r TP1/python/requirements.txt
```

## Generador de instancias y verificador cruzado

```
cd TP1/python
python3 generador.py --n 60 --d 12 --k 30 --modo estructura --semilla 1 --salida ../output/numericos/e60.txt
python3 verificar.py --binario ../radioedit --solvers fb,bt,pd,py-bt,py-pd --cantidad 100
```

`generador.py` escribe instancias en el formato del enunciado en tres modos, `uniforme`,
`estructura` (secciones repetidas, el caso musical) y `adversarial` (todos los pulsos distintos).
`verificar.py` genera instancias chicas al azar, corre los programas pedidos, valida cada
selección y compara los costos contra un óptimo calculado en Python por fuerza bruta y entre sí.
Las discrepancias se guardan en `output/discrepancias`. El verificador termina con código 0 si
no hubo ninguna. Ambos programas documentan sus opciones con `--help`.

## Audio: extracción y reconstrucción

Las grabaciones no se versionan. Se obtienen con los dos programas de `TP1/audio` (fuentes y
licencias en `audio/FUENTES.md`) y después `python/extraer_todo.sh` regenera todas las
instancias de `input/real`:

```
cd TP1/audio && ./descargar.sh && ./recortar_escenas.sh && cd ..
python/extraer_todo.sh
```

`descargar.sh` baja los mp3 con curl y `recortar_escenas.sh` corta con ffmpeg las escenas de
*His Girl Friday* y el tramo de *Suspense* que usa `extraer_todo.sh`. Con el entorno virtual
instalado (ver arriba) y el audio ya descargado, la cadena para una grabación es la siguiente
(la salida va a `output/`, ignorado por git, para no pisar la instancia versionada de
`input/real/action.txt`):

```
cd TP1
../.venv/bin/python python/extraer.py audio/macleod_action.mp3 --salida output/numericos/action_demo --duracion 60
./radioedit --instancia output/numericos/action_demo.txt --algoritmo pd --salida output/numericos/action_demo_sel.txt
../.venv/bin/python python/reconstruir.py audio/macleod_action.mp3 output/numericos/action_demo_sel.txt \
    --pulsos output/numericos/action_demo_pulsos.txt --salida output/audio/action_demo_recorte.wav
```

## Experimentación

Toda la experimentación del informe se reproduce desde un único programa con subcomandos, que
corre el binario y la versión en Python como subprocesos, toma la mediana de tres corridas del
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
  fija por familia, n, k y d (`semilla_de` en el programa), así que las corridas son reproducibles.
  Las familias son `uniforme` (puntos uniformes en [0,1]^d), `estructura` (patrón de secciones
  ABBCBB con ruido gaussiano de desvío 0,05) y `adversarial` (grilla de paso 1 en orden aleatorio),
  todas con d = 12 salvo la serie en d del experimento e3.
- `e1` compara los tres exactos (alcance en n y coincidencia de costos), `e2` mide las podas de
  backtracking, `e3` el escalado de la programación dinámica en n, k y d (con memoria pico),
  `e4` C++ contra Python, `e5` las grabaciones reales de `TP1/input/real` (incluye la
  reconstrucción de audio, que necesita el entorno virtual y los mp3 de `TP1/audio`) y `e6` los
  tres exactos sobre prefijos de una grabación real.
- Los CSV quedan en `TP1/output/numericos/` (ignorado por git) y las copias finales en
  `informe/datos/`. Las figuras van a `informe/figuras/` en PNG a 200 dpi. Con `--reps` se cambia
  la cantidad de repeticiones y con `--timeout` el límite por corrida (60 s, o 150 s en e3 y e4).
- `todo`, cada `eN` y `figuras` reemplazan los CSV de `informe/datos/` y las figuras de
  `informe/figuras/` que usa el informe entregado. Se vuelve a la versión entregada con
  `git checkout -- informe/datos informe/figuras`. Con `--rapido` no se toca `informe/`. Los CSV
  van a `TP1/output/numericos/rapido/` y las figuras a `TP1/output/numericos/rapido/figuras/`.
- Si el binario `TP1/radioedit` no existe, el programa lo compila con `make`.

La máquina y el compilador con que se midieron los tiempos del informe se describen en la sección
de metodología del informe.

## Informe

`informe/informe.tex` se compila con `pdflatex` (dos pasadas para el índice y las referencias).
