#!/usr/bin/env python3
"""Experimentación del TP1: un único punto de entrada con subcomandos.

Correr desde cualquier directorio con el Python del entorno virtual del repo
(hace falta matplotlib para las figuras y librosa para reconstruir audio):

  .venv/bin/python TP1/python/experimentos.py <subcomando> [--rapido] [--reps 3]

Subcomandos:
  generar   escribe todas las instancias sintéticas en TP1/input/sinteticas/<familia>/
            (deterministas: semilla fija por familia, n, k y d).
  e1        exactos-chicos: FB, BT y PD sobre instancias chicas, tiempo vs n por
            algoritmo en tres familias y tres regímenes de k; verifica que los
            costos coincidan.
  e2        podas: BT en sus cuatro configuraciones, nodos visitados y tiempo vs n
            y vs k, en las tres familias.
  e3        escalado-pd: PD en C++ sobre instancias grandes, tiempo vs n, vs k y
            vs d, más memoria pico (maxrss).
  e4        lenguajes: BT y PD en C++ y en Python sobre las mismas instancias.
  e5        audio-real: PD sobre las instancias reales con k al 50, 70 y 90 % de n,
            contra truncar y muestreo uniforme; croma vs mfcc; reconstruye audio y
            dibuja la matriz de costos con la selección óptima.
  e6        tiempos-reales: FB, BT y PD sobre prefijos de una instancia real.
  figuras   regenera todas las figuras a partir de los CSV ya calculados.
  todo      generar + e1..e6 en orden.

Cada corrida se hace por subprocess con timeout; si se agota se registra
"timeout" en el CSV y la serie de ese algoritmo no sigue creciendo en n. Los
tiempos son la mediana de --reps corridas (3 por defecto) del tiempo que
imprime el propio programa ("Tiempo: X ms", que mide solo resolver, sin lectura
del archivo). Los resultados van a TP1/output/numericos/ (ignorado por git) y
los CSV finales se copian a informe/datos/. Con --rapido se corre una versión
reducida de cada experimento para probar que todo anda de punta a punta; en ese
modo no se toca informe/: los CSV quedan en TP1/output/numericos/rapido/ y las
figuras en TP1/output/numericos/rapido/figuras/.
"""

import argparse
import csv
import os
import re
import shutil
import statistics
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)                       # TP1
REPO = os.path.dirname(RAIZ)
BINARIO = os.path.join(RAIZ, "radioedit")
ALGORITMOS_PY = os.path.join(AQUI, "algoritmos.py")
RECONSTRUIR_PY = os.path.join(AQUI, "reconstruir.py")
DIR_SINTETICAS = os.path.join(RAIZ, "input", "sinteticas")
DIR_REAL = os.path.join(RAIZ, "input", "real")
DIR_AUDIO = os.path.join(RAIZ, "audio")
DIR_NUMERICOS = os.path.join(RAIZ, "output", "numericos")
DIR_AUDIO_SALIDA = os.path.join(RAIZ, "output", "audio")
DIR_DATOS = os.path.join(REPO, "informe", "datos")
DIR_TMP = os.path.join(DIR_NUMERICOS, "tmp")
DIR_RAPIDO = os.path.join(DIR_NUMERICOS, "rapido")

sys.path.insert(0, AQUI)
import generador  # noqa: E402
from algoritmos import costo_seleccion, leer_instancia  # noqa: E402

FAMILIAS = ["uniforme", "estructura", "adversarial"]
D_DEFECTO = 12

# Parámetros fijos de cada familia (ver generador.py). La familia "estructura" es
# el caso musical (secciones repetidas A B B C B B con ruido); "adversarial" son
# vértices distintos de una grilla en orden aleatorio, sin saltos baratos.
PARAMETROS_FAMILIA = {
    "uniforme": {},
    "estructura": {"patron": "ABBCBB", "ruido": 0.05},
    "adversarial": {"paso": 1.0},
}

# Audio original de cada instancia real (ver audio/FUENTES.md).
AUDIO_DE = {
    "action": "macleod_action.mp3",
    "ascending_the_vale": "macleod_ascending_the_vale.mp3",
    "batty_mcfaddin": "macleod_batty_mcfaddin.mp3",
    "hgf_corta": "hgf_escena_corta.mp3",
    "hgf_media": "hgf_escena_media.mp3",
    "hgf_larga": "hgf_escena_larga.mp3",
    "suspense": "suspense_tramo.mp3",
}

RE_TIEMPO = re.compile(r"^Tiempo: ([0-9.eE+-]+) ms")
RE_COSTO = re.compile(r"^Costo: (\S+)")
RE_NODOS = re.compile(r"^Nodos visitados: (\d+)")
RE_SELECCION = re.compile(r"^Selecci\S+ \(\d+ pulsos\): (.*)$")


# ---------------------------------------------------------------------------
# Utilidades generales
# ---------------------------------------------------------------------------

def asegurar_binario():
    if not os.path.exists(BINARIO):
        print("No existe el binario, compilando con make en " + RAIZ)
        subprocess.run(["make"], cwd=RAIZ, check=True)


def ruta_sintetica(familia, n, k, d=D_DEFECTO):
    return os.path.join(DIR_SINTETICAS, familia, "{}_n{}_k{}_d{}.txt".format(familia, n, k, d))


def semilla_de(familia, n, k, d):
    """Semilla determinista y distinta por instancia."""
    return (FAMILIAS.index(familia) + 1) * 10 ** 8 + n * 10 ** 4 + k * 20 + d


def generar_sintetica(familia, n, k, d=D_DEFECTO):
    """Genera (si hace falta, siempre con la misma semilla) y devuelve la ruta."""
    ruta = ruta_sintetica(familia, n, k, d)
    if not os.path.exists(ruta):
        _, _, _, pulsos = generador.generar(n, d, k, familia, semilla_de(familia, n, k, d),
                                            **PARAMETROS_FAMILIA[familia])
        generador.escribir_instancia(ruta, n, d, k, pulsos)
    return ruta


def escribir_instancia_derivada(ruta, n, d, k, lineas_pulsos):
    """Escribe una instancia a partir de líneas ya formateadas (prefijos y cambios de k)."""
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write("{} {} {}\n".format(n, d, k))
        archivo.write("\n".join(lineas_pulsos) + "\n")


def leer_lineas_pulsos(ruta):
    with open(ruta, encoding="utf-8") as archivo:
        lineas = [l.strip() for l in archivo.read().split("\n")]
    cabecera = lineas[0].split()
    n, d = int(cabecera[0]), int(cabecera[1])
    return n, d, [l for l in lineas[1:] if l][:n]


def comando_cpp(instancia, algoritmo, salida, flags=()):
    return [BINARIO, "--instancia", instancia, "--algoritmo", algoritmo,
            "--salida", salida] + list(flags)


def comando_py(instancia, algoritmo, salida, flags=()):
    return [sys.executable, ALGORITMOS_PY, "--instancia", instancia, "--algoritmo", algoritmo,
            "--salida", salida] + list(flags)


def correr(cmd, timeout):
    """Corre un solver y parsea su salida. estado: ok, timeout o error."""
    resultado = {"estado": "ok", "ms": None, "costo": None, "nodos": None, "seleccion": None}
    inicio = time.time()
    try:
        proceso = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        resultado["estado"] = "timeout"
        resultado["wall_s"] = time.time() - inicio
        return resultado
    resultado["wall_s"] = time.time() - inicio
    if proceso.returncode != 0:
        resultado["estado"] = "error"
        resultado["stderr"] = proceso.stderr.strip()[-300:]
        print("  ERROR en " + " ".join(cmd) + "\n  " + resultado["stderr"])
        return resultado
    for linea in proceso.stdout.splitlines():
        m = RE_TIEMPO.match(linea)
        if m:
            resultado["ms"] = float(m.group(1))
            continue
        m = RE_COSTO.match(linea)
        if m:
            resultado["costo"] = float(m.group(1))
            continue
        m = RE_NODOS.match(linea)
        if m:
            resultado["nodos"] = int(m.group(1))
            continue
        m = RE_SELECCION.match(linea)
        if m:
            resultado["seleccion"] = [int(x) for x in m.group(1).split()]
    if resultado["ms"] is None:
        resultado["estado"] = "error"
        resultado["stderr"] = "no se encontro la linea Tiempo en la salida"
    return resultado


def medir(cmd, reps, timeout):
    """Mediana de `reps` corridas. Si alguna se agota o falla, devuelve ese estado."""
    tiempos = []
    ultimo = None
    for _ in range(reps):
        r = correr(cmd, timeout)
        if r["estado"] != "ok":
            return r
        tiempos.append(r["ms"])
        ultimo = r
    ultimo = dict(ultimo)
    ultimo["ms"] = statistics.median(tiempos)
    ultimo["ms_min"] = min(tiempos)
    ultimo["ms_max"] = max(tiempos)
    ultimo["corridas"] = len(tiempos)
    return ultimo


# Mide la memoria pico (maxrss) del hijo con getrusage, que anda en macOS y Linux
# sin depender de /usr/bin/time. En macOS ru_maxrss viene en bytes, en Linux en KB.
_ENVOLTORIO_MEMORIA = (
    "import resource, subprocess, sys\n"
    "p = subprocess.run(sys.argv[1:], stdout=subprocess.DEVNULL)\n"
    "print('MAXRSS', resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)\n"
    "sys.exit(p.returncode)\n"
)


def medir_memoria_mb(cmd, timeout):
    try:
        proceso = subprocess.run([sys.executable, "-c", _ENVOLTORIO_MEMORIA] + cmd, cwd=RAIZ,
                                 capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    for linea in proceso.stdout.splitlines():
        if linea.startswith("MAXRSS"):
            valor = float(linea.split()[1])
            divisor = 1024.0 ** 2 if sys.platform == "darwin" else 1024.0
            return valor / divisor
    return None


class Csv:
    """CSV incremental: trunca al crear y agrega filas a medida que se calculan."""

    def __init__(self, nombre, columnas):
        os.makedirs(DIR_NUMERICOS, exist_ok=True)
        self.ruta = os.path.join(DIR_NUMERICOS, nombre)
        self.columnas = columnas
        with open(self.ruta, "w", newline="", encoding="utf-8") as archivo:
            csv.writer(archivo).writerow(columnas)

    def fila(self, **valores):
        with open(self.ruta, "a", newline="", encoding="utf-8") as archivo:
            csv.writer(archivo).writerow([formatear(valores.get(c, "")) for c in self.columnas])

    def copiar_a_datos(self):
        destino = os.path.join(DIR_DATOS, os.path.basename(self.ruta))
        if os.path.abspath(destino) == os.path.abspath(self.ruta):
            return  # modo --rapido: los CSV ya están en su directorio final
        os.makedirs(DIR_DATOS, exist_ok=True)
        shutil.copy(self.ruta, destino)


def formatear(valor):
    if valor is None:
        return ""
    if isinstance(valor, float):
        return "{:.10g}".format(valor)
    return str(valor)


def leer_csv(nombre):
    """Lee un CSV de output/numericos (o de informe/datos si no está) a lista de dicts."""
    ruta = os.path.join(DIR_NUMERICOS, nombre)
    if not os.path.exists(ruta):
        ruta = os.path.join(DIR_DATOS, nombre)
    if not os.path.exists(ruta):
        return []
    with open(ruta, newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def filas_ok(filas, **filtro):
    """Filas con estado ok que cumplen los filtros de igualdad dados."""
    salida = []
    for f in filas:
        if f.get("estado", "ok") != "ok":
            continue
        if all(str(f.get(c)) == str(v) for c, v in filtro.items()):
            salida.append(f)
    return salida


def ruta_tmp(nombre):
    os.makedirs(DIR_TMP, exist_ok=True)
    return os.path.join(DIR_TMP, nombre)


def progreso(texto):
    print("[{}] {}".format(time.strftime("%H:%M:%S"), texto), flush=True)


def costos_coinciden(costos, tolerancia=1e-9):
    validos = [c for c in costos if c is not None]
    if len(validos) < 2:
        return ""
    referencia = validos[0]
    return all(abs(c - referencia) <= tolerancia * max(1.0, abs(referencia)) for c in validos)


# ---------------------------------------------------------------------------
# Especificaciones de instancias por experimento
# ---------------------------------------------------------------------------

REGIMENES_K = {
    "n/2": lambda n: max(2, n // 2),
    "n/4": lambda n: max(2, n // 4),
    "3n/4": lambda n: max(2, 3 * n // 4),
}


def especificacion_e1(rapido):
    """(familia, régimen, n, k) para E1. FB con k=n/2 tarda 22 s en n=32 y 89 s en n=34,
    por eso la serie n/2 corta en 32; con k=n/4 o 3n/4 hay menos combinaciones y
    la serie llega más lejos."""
    if rapido:
        rangos = {"n/2": [6, 10, 14], "n/4": [8, 16], "3n/4": [8, 16]}
    else:
        rangos = {"n/2": list(range(6, 33, 2)), "n/4": list(range(8, 41, 4)),
                  "3n/4": list(range(8, 37, 4))}
    especificaciones = []
    for familia in FAMILIAS:
        for regimen, ns in rangos.items():
            for n in ns:
                especificaciones.append((familia, regimen, n, REGIMENES_K[regimen](n)))
    return especificaciones


def especificacion_e2(rapido):
    """(familia, serie, n, k) para E2. Sin podas BT visita sum_{t<k} C(n-1, t) nodos, que con
    k = n/2 es exactamente 2^(n-2): n=28 son 67 millones de nodos y menos de 1 s."""
    if rapido:
        vs_n = [(n, n // 2) for n in [8, 12, 16]]
        vs_k = [(12, k) for k in [2, 4, 6, 8, 10, 12]]
    else:
        vs_n = [(n, n // 2) for n in range(8, 29, 2)]
        vs_k = [(24, k) for k in range(2, 25, 2)]
    especificaciones = []
    for familia in FAMILIAS:
        especificaciones += [(familia, "vs_n", n, k) for n, k in vs_n]
        especificaciones += [(familia, "vs_k", n, k) for n, k in vs_k]
    return especificaciones


def especificacion_e3(rapido):
    """(serie, n, k, d) para E3, familia estructura. PD tarda 19 s en n=3000."""
    if rapido:
        vs_n = [(n, n // 2, D_DEFECTO) for n in [250, 500]]
        vs_k = [(200, k, D_DEFECTO) for k in [2, 50, 100, 150, 200]]
        vs_d = [(200, 100, d) for d in [1, 12]]
    else:
        vs_n = [(n, n // 2, D_DEFECTO) for n in [250, 500, 750, 1000, 1500, 2000, 2500, 3000]]
        vs_k = [(1000, k, D_DEFECTO) for k in
                [2, 10, 25, 50, 100, 150, 200, 250, 300, 350, 400, 500, 600, 700, 800, 900, 950, 990, 1000]]
        vs_d = [(1000, 500, d) for d in [1, 2, 4, 8, 12, 16, 24, 32]]
    return ([("vs_n",) + e for e in vs_n] + [("vs_k",) + e for e in vs_k] +
            [("vs_d",) + e for e in vs_d])


def especificacion_e4(rapido):
    """(algoritmo, n, k) para E4, familia estructura. Python PD tarda 80 s en n=1000."""
    if rapido:
        bt = [25, 50]
        pd = [100, 200]
    else:
        bt = [25, 50, 100, 200, 400, 800]
        pd = [100, 200, 400, 600, 800, 1000]
    return [("bt", n, n // 2) for n in bt] + [("pd", n, n // 2) for n in pd]


PROPORCIONES_E5 = [0.5, 0.7, 0.9]
RECONSTRUIR_E5 = ["action", "ascending_the_vale", "batty_mcfaddin", "hgf_media", "hgf_media_mfcc"]
TEMAS_ESTRUCTURA_E5 = ["action", "ascending_the_vale", "batty_mcfaddin"]
INSTANCIA_E6 = "batty_mcfaddin"


def especificacion_e6(rapido):
    """Prefijos (n, k=0.7 n) de la instancia real. FB tarda 53 s en n=36 (k=25)."""
    if rapido:
        fb = [6, 10, 14, 20]
        resto = [50]
    else:
        fb = list(range(6, 35, 2))
        resto = [40, 50, 75, 100, 150, 200, 250, 300, 350, 400, 450]
    return fb, resto


def instancias_reales():
    """Nombres (sin extension) de las instancias reales, croma y mfcc."""
    nombres = []
    for archivo in sorted(os.listdir(DIR_REAL)):
        if archivo.endswith(".txt") and not archivo.endswith("_pulsos.txt"):
            nombres.append(archivo[:-4])
    return nombres


# ---------------------------------------------------------------------------
# generar
# ---------------------------------------------------------------------------

def cmd_generar(args):
    """Genera las instancias del modo completo y las del modo --rapido (las 180
    versionadas en TP1/input/sinteticas), sin importar con que modo se invoque."""
    inicio = time.time()
    rutas = set()
    for rapido in (False, True):
        for familia, _, n, k in especificacion_e1(rapido) + especificacion_e2(rapido):
            rutas.add(generar_sintetica(familia, n, k))
        for _, n, k, d in especificacion_e3(rapido):
            rutas.add(generar_sintetica("estructura", n, k, d))
        for _, n, k in especificacion_e4(rapido):
            rutas.add(generar_sintetica("estructura", n, k))
    progreso("{} instancias sinteticas en {} ({:.1f} s)".format(
        len(rutas), os.path.relpath(DIR_SINTETICAS), time.time() - inicio))


# ---------------------------------------------------------------------------
# E1: exactos chicos
# ---------------------------------------------------------------------------

COLUMNAS_TIEMPOS = ["ms", "ms_min", "ms_max", "corridas", "estado"]


def cmd_e1(args):
    asegurar_binario()
    tabla = Csv("e1_exactos.csv", ["familia", "regimen", "n", "d", "k", "algoritmo", "costo",
                                   "nodos"] + COLUMNAS_TIEMPOS)
    coincidencias = Csv("e1_coincidencia.csv", ["familia", "regimen", "n", "k", "costo_fb",
                                                "costo_bt", "costo_pd", "coinciden"])
    agotados = set()  # (familia, régimen, algoritmo) que ya dieron timeout
    for familia, regimen, n, k in especificacion_e1(args.rapido):
        instancia = generar_sintetica(familia, n, k)
        costos = {}
        for algoritmo in ["fb", "bt", "pd"]:
            if (familia, regimen, algoritmo) in agotados:
                continue
            r = medir(comando_cpp(instancia, algoritmo, ruta_tmp("e1.txt")), args.reps, args.timeout)
            tabla.fila(familia=familia, regimen=regimen, n=n, d=D_DEFECTO, k=k, algoritmo=algoritmo,
                       **{c: r.get(c) for c in ["costo", "nodos"] + COLUMNAS_TIEMPOS})
            costos[algoritmo] = r.get("costo")
            if r["estado"] != "ok":
                agotados.add((familia, regimen, algoritmo))
        coincidencias.fila(familia=familia, regimen=regimen, n=n, k=k,
                           costo_fb=costos.get("fb"), costo_bt=costos.get("bt"),
                           costo_pd=costos.get("pd"), coinciden=costos_coinciden(list(costos.values())))
        progreso("E1 {} k={} n={}: ".format(familia, regimen, n) + ", ".join(
            "{}={}".format(a, "?" if c is None else "{:.4g}".format(c)) for a, c in costos.items()))
    tabla.copiar_a_datos()
    coincidencias.copiar_a_datos()
    figuras_e1()


def modelo_fb(n, k, d):
    """Cota teórica de fuerza bruta: C(n-2, k-2) combinaciones por k saltos por d."""
    from math import comb
    return comb(n - 2, k - 2) * k * d


def constante_modelo_fb(puntos):
    """Ajusta c en ms = c * modelo_fb por mínimos cuadrados en log, usando solo los
    puntos con ms >= 1 (en los chicos domina el costo fijo de armar la selección)."""
    import math
    grandes = [f for f in puntos if float(f["ms"]) >= 1] or puntos
    logs = [math.log(float(f["ms"]) / modelo_fb(int(f["n"]), int(f["k"]), int(f["d"])))
            for f in grandes]
    return math.exp(sum(logs) / len(logs))


def mediana_familias(filas, regimen, algoritmo, columna="ms"):
    """Mediana entre las tres familias de `columna` para cada n del régimen."""
    import statistics
    por_n = {}
    for f in filas_ok(filas, regimen=regimen, algoritmo=algoritmo):
        por_n.setdefault(int(f["n"]), []).append(f)
    salida = []
    for n in sorted(por_n):
        grupo = por_n[n]
        salida.append((n, int(grupo[0]["k"]), int(grupo[0]["d"]),
                       statistics.median(float(f[columna]) for f in grupo)))
    return salida


def figuras_e1():
    filas = leer_csv("e1_exactos.csv")
    if not filas:
        return
    import figuras as fg

    # Pregunta: hasta qué n llega cada exacto con k = n/2 y cómo crece el tiempo,
    # contrastando FB con su cota C(n-2, k-2) k d (misma constante en los tres paneles).
    # Un solo panel: FB y PD hacen el mismo trabajo en las tres familias, así que se
    # dibujan una vez (familia con estructura) y solo BT lleva un marcador por familia.
    # El ancho físico (3,2 pulgadas) es el que ocupa en el informe, para que las fuentes
    # de 8 a 9 pt se impriman a ese tamaño.
    fig, ejes = fg.figura(paneles=1, ancho=3.2, alto=2.1)
    ax = ejes[0]
    c_fb = constante_modelo_fb(filas_ok(filas, regimen="n/2", algoritmo="fb"))
    manejadores = []
    for algoritmo in ["fb", "pd"]:
        puntos = filas_ok(filas, familia="estructura", regimen="n/2", algoritmo=algoritmo)
        puntos.sort(key=lambda f: int(f["n"]))
        if not puntos:
            continue
        ns = [int(f["n"]) for f in puntos]
        manejadores.append(ax.plot(ns, [float(f["ms"]) for f in puntos], "-", color=fg.PALETA[algoritmo],
                                   label=fg.ETIQUETAS[algoritmo])[0])
        if algoritmo == "fb":
            # La cota va sin entrada en la leyenda: el caption la describe.
            ax.plot(ns, [c_fb * modelo_fb(int(f["n"]), int(f["k"]), int(f["d"])) for f in puntos],
                    "--", color=fg.PALETA["modelo"], linewidth=1.0)
    for familia in FAMILIAS:
        puntos = filas_ok(filas, familia=familia, regimen="n/2", algoritmo="bt")
        puntos.sort(key=lambda f: int(f["n"]))
        if not puntos:
            continue
        linea = ax.plot([int(f["n"]) for f in puntos], [float(f["ms"]) for f in puntos], "-",
                        color=fg.PALETA["bt"], marker=fg.MARCADORES[familia], markersize=3.5, alpha=0.9)[0]
        if familia == FAMILIAS[0]:
            from matplotlib.lines import Line2D
            manejadores.insert(1, Line2D([], [], color=fg.PALETA["bt"], label=fg.ETIQUETAS["bt"]))
    ax.set_yscale("log")
    ax.set_xlabel("n (pulsos), k = n/2")
    ax.set_ylabel("tiempo (ms)")
    fg.leyenda_abajo_manejadores(fig, manejadores + fg.manejadores_familias(), columnas=2)
    fg.guardar(fig, "e1_tiempo_vs_n")

    # Pregunta: cómo cambia el tiempo de FB y de PD con el régimen de k. Se grafica la
    # mediana entre las tres familias porque difieren menos del 5 % entre si.
    fig, ejes = fg.figura(paneles=2, compartir_y=False)
    for ax, algoritmo in zip(ejes, ["fb", "pd"]):
        for regimen in ["n/4", "n/2", "3n/4"]:
            puntos = mediana_familias(filas, regimen, algoritmo)
            if not puntos:
                continue
            ns = [p[0] for p in puntos]
            ax.plot(ns, [p[3] for p in puntos], "-", color=fg.PALETA[algoritmo],
                    marker=fg.MARCADORES_REGIMEN[regimen], label="k = " + regimen)
            if algoritmo == "fb":
                c = constante_modelo_fb(filas_ok(filas, regimen=regimen, algoritmo="fb"))
                ax.plot(ns, [c * modelo_fb(n, k, d) for n, k, d, _ in puntos], "--",
                        color=fg.PALETA["modelo"], linewidth=1.0,
                        label="Modelo FB" if regimen == "3n/4" else None)
        ax.set_yscale("log")
        ax.set_xlabel("n (pulsos)")
        ax.set_ylabel("tiempo (ms)")
        ax.set_title(fg.ETIQUETAS[algoritmo])
    fg.leyenda_abajo(fig, ejes[0], columnas=4)
    fg.guardar(fig, "e1_regimenes_k")

    # Pregunta: cuántos nodos visita BT con ambas podas según familia y régimen de k.
    fig, ejes = fg.figura(paneles=3)
    for ax, regimen in zip(ejes, ["n/4", "n/2", "3n/4"]):
        for familia in FAMILIAS:
            puntos = filas_ok(filas, familia=familia, regimen=regimen, algoritmo="bt")
            puntos.sort(key=lambda f: int(f["n"]))
            if puntos:
                fg.serie(ax, [int(f["n"]) for f in puntos], [int(f["nodos"]) for f in puntos],
                         familia, etiqueta=fg.FAMILIAS_TITULO[familia])
        ax.set_yscale("log")
        ax.set_xlabel("n (pulsos)")
        ax.set_title("k = " + regimen)
    ejes[0].set_ylabel("nodos visitados")
    fg.leyenda_abajo(fig, ejes[0])
    fg.guardar(fig, "e1_bt_nodos")


# ---------------------------------------------------------------------------
# E2: podas de BT
# ---------------------------------------------------------------------------

CONFIGURACIONES_BT = {
    "ninguna": ["--sin-poda-factibilidad", "--sin-poda-optimalidad"],
    "factibilidad": ["--sin-poda-optimalidad"],
    "optimalidad": ["--sin-poda-factibilidad"],
    "ambas": [],
}


def cmd_e2(args):
    asegurar_binario()
    tabla = Csv("e2_podas.csv", ["familia", "serie", "n", "d", "k", "configuracion", "nodos",
                                 "costo"] + COLUMNAS_TIEMPOS)
    agotados = set()
    for familia, serie, n, k in especificacion_e2(args.rapido):
        instancia = generar_sintetica(familia, n, k)
        resumen = []
        for configuracion, flags in CONFIGURACIONES_BT.items():
            if (familia, serie, configuracion) in agotados:
                continue
            r = medir(comando_cpp(instancia, "bt", ruta_tmp("e2.txt"), flags), args.reps, args.timeout)
            tabla.fila(familia=familia, serie=serie, n=n, d=D_DEFECTO, k=k, configuracion=configuracion,
                       **{c: r.get(c) for c in ["costo", "nodos"] + COLUMNAS_TIEMPOS})
            resumen.append("{}={}".format(configuracion, r.get("nodos") if r["estado"] == "ok" else r["estado"]))
            if r["estado"] != "ok":
                agotados.add((familia, serie, configuracion))
        progreso("E2 {} {} n={} k={}: nodos ".format(familia, serie, n, k) + ", ".join(resumen))
    tabla.copiar_a_datos()
    figuras_e2()


def nodos_bt_teoricos(n, k, factibilidad):
    """Nodos que visita BT sin la poda de optimalidad (coincide exacto con lo medido).
    Sin podas se visitan todas las selecciones parciales (1, j_2, ..., j_t) con t <= k, o sea
    sum_{t<k} C(n-1, t), que para k = n/2 es 2^(n-2). Con factibilidad solo se extiende con
    j <= n-(k-t) y la hoja es siempre n: 1 + sum_{t=2}^{k-1} C(n-k+t-1, t-1) + C(n-2, k-2)."""
    from math import comb
    if factibilidad:
        return 1 + sum(comb(n - k + t - 1, t - 1) for t in range(2, k)) + comb(n - 2, k - 2)
    return sum(comb(n - 1, t) for t in range(k))


def resumen_e2(filas):
    """e2_ajustes.csv: por familia y configuración, base por unidad de n de nodos y de tiempo
    (ajuste de log2 contra n en la serie vs_n; el tiempo se ajusta con n >= 16 porque debajo
    lo domina el costo fijo), exponente log-log de nodos, valores en n = 28 con la reducción
    respecto de 'ninguna', tiempo por nodo y media geométrica de nodos en la serie."""
    import math
    tabla = Csv("e2_ajustes.csv", ["familia", "configuracion", "base_nodos", "r2_nodos", "base_ms",
                                   "r2_ms", "exponente_loglog_nodos", "r2_loglog", "nodos_n28",
                                   "ms_n28", "reduccion_nodos_n28", "reduccion_ms_n28",
                                   "ns_por_nodo_n28", "media_geometrica_nodos"])
    for familia in FAMILIAS:
        referencia = filas_ok(filas, familia=familia, serie="vs_n", configuracion="ninguna", n=28)
        for configuracion in CONFIGURACIONES_BT:
            puntos = filas_ok(filas, familia=familia, serie="vs_n", configuracion=configuracion)
            puntos.sort(key=lambda f: int(f["n"]))
            if len(puntos) < 3:
                continue
            ns = [int(f["n"]) for f in puntos]
            nodos = [int(f["nodos"]) for f in puntos]
            ms = [float(f["ms"]) for f in puntos]
            _, b_nodos, r2_nodos = ajuste_lineal(ns, [math.log2(v) for v in nodos])
            grandes = [(n, m) for n, m in zip(ns, ms) if n >= 16]
            _, b_ms, r2_ms = ajuste_lineal([g[0] for g in grandes], [math.log2(g[1]) for g in grandes])
            _, expo, r2_expo = ajuste_lineal([math.log(n) for n in ns], [math.log(v) for v in nodos])
            f28 = [f for f in puntos if int(f["n"]) == 28]
            valores = dict(familia=familia, configuracion=configuracion, base_nodos=2 ** b_nodos,
                           r2_nodos=r2_nodos, base_ms=2 ** b_ms, r2_ms=r2_ms,
                           exponente_loglog_nodos=expo, r2_loglog=r2_expo,
                           media_geometrica_nodos=statistics.geometric_mean(nodos))
            if f28 and referencia:
                n28, ms28 = int(f28[0]["nodos"]), float(f28[0]["ms"])
                valores.update(nodos_n28=n28, ms_n28=ms28,
                               reduccion_nodos_n28=int(referencia[0]["nodos"]) / n28,
                               reduccion_ms_n28=float(referencia[0]["ms"]) / ms28,
                               ns_por_nodo_n28=ms28 * 1e6 / n28)
            tabla.fila(**valores)
    tabla.copiar_a_datos()


def figura_e2_vs_n(filas):
    """Nodos visitados contra n con k = n/2 en un solo panel del ancho que ocupa en el
    informe. Sin podas y con solo factibilidad la cuenta es exacta e igual en las tres
    familias, así que se dibuja una vez; con optimalidad el color da la configuración y
    el marcador la familia."""
    import figuras as fg
    from math import comb
    from matplotlib.lines import Line2D
    pares = sorted({(int(f["n"]), int(f["k"])) for f in filas_ok(filas, serie="vs_n")})
    if not pares:
        return
    fig, ejes = fg.figura(paneles=1, ancho=3.45, alto=2.3)
    ax = ejes[0]
    xs = [p[0] for p in pares]
    ax.plot(xs, [nodos_bt_teoricos(n, k, False) for n, k in pares], "--", color=fg.PALETA["modelo"],
            linewidth=1.0, zorder=1)
    ax.plot(xs, [comb(n - 2, k - 2) for n, k in pares], ":", color=fg.PALETA["modelo"], linewidth=1.2, zorder=1)
    manejadores = []
    for configuracion in CONFIGURACIONES_BT:
        familias = [FAMILIAS[1]] if configuracion in ("ninguna", "factibilidad") else FAMILIAS
        for familia in familias:
            puntos = filas_ok(filas, familia=familia, serie="vs_n", configuracion=configuracion)
            puntos.sort(key=lambda f: int(f["n"]))
            if not puntos:
                continue
            marcador = fg.MARCADORES[familia] if len(familias) > 1 else None
            ax.plot([int(f["n"]) for f in puntos], [int(f["nodos"]) for f in puntos], "-",
                    color=fg.PALETA[configuracion], marker=marcador, markersize=3.5, alpha=0.9)
        manejadores.append(Line2D([], [], color=fg.PALETA[configuracion], label=fg.ETIQUETAS[configuracion]))
    ax.set_yscale("log")
    ax.set_xlabel("n (pulsos), k = n/2")
    ax.set_ylabel("nodos visitados")
    fg.leyenda_abajo_manejadores(fig, manejadores + fg.manejadores_familias(), columnas=3)
    fg.guardar(fig, "e2_nodos_vs_n")


def figuras_e2():
    filas = leer_csv("e2_podas.csv")
    if not filas:
        return
    import figuras as fg
    from math import comb
    resumen_e2(filas)
    # Pregunta: cuántos nodos ahorra cada poda (vs n con k = n/2, y vs k con n = 24) y si
    # depende de la familia. Las referencias son la cuenta exacta de nodos sin podas y la
    # cantidad de hojas factibles C(n-2, k-2), que es lo que enumera fuerza bruta.
    figura_e2_vs_n(filas)
    for serie, variable, nombre in [("vs_k", "k", "e2_nodos_vs_k")]:
        fig, ejes = fg.figura(paneles=3)
        for ax, familia in zip(ejes, FAMILIAS):
            pares = sorted({(int(f["n"]), int(f["k"])) for f in filas_ok(filas, familia=familia, serie=serie)})
            xs = [p[0] if variable == "n" else p[1] for p in pares]
            etiqueta_sin = "$2^{n-2}$ (sin podas, exacto)" if variable == "n" else "sin podas, exacto"
            ax.plot(xs, [nodos_bt_teoricos(n, k, False) for n, k in pares], "--", color=fg.PALETA["modelo"],
                    linewidth=1.0, label=etiqueta_sin, zorder=1)
            ax.plot(xs, [comb(n - 2, k - 2) for n, k in pares], ":", color=fg.PALETA["modelo"],
                    linewidth=1.2, label="hojas factibles $\\binom{n-2}{k-2}$", zorder=1)
            for configuracion in CONFIGURACIONES_BT:
                puntos = filas_ok(filas, familia=familia, serie=serie, configuracion=configuracion)
                puntos.sort(key=lambda f: int(f[variable]))
                if puntos:
                    fg.serie(ax, [int(f[variable]) for f in puntos], [int(f["nodos"]) for f in puntos],
                             configuracion)
            ax.set_yscale("log")
            ax.set_xlabel("n (pulsos)" if variable == "n" else "k (pulsos conservados)")
            ax.set_title(fg.FAMILIAS_TITULO[familia])
        ejes[0].set_ylabel("nodos visitados")
        fg.leyenda_abajo(fig, ejes[0], columnas=3)
        fg.guardar(fig, nombre)
    # Pregunta: cuánto tiempo ahorra cada poda y por qué el ahorro en tiempo es menor que el
    # ahorro en nodos. Se muestra la familia uniforme (la peor para las podas); sin podas y
    # con solo factibilidad el tiempo es el mismo en las tres familias porque los nodos no
    # dependen de los datos. El panel derecho muestra el costo por nodo: con la poda de
    # optimalidad cada nodo recorre candidatos j que se descartan, así que cuesta más.
    familia = "uniforme"
    fig, ejes = fg.figura(paneles=2, compartir_y=False)
    sin_podas = filas_ok(filas, serie="vs_n", configuracion="ninguna")
    # Costo por nodo: mediana sobre las corridas grandes (más de 10^5 nodos), donde no
    # pesa el costo fijo; si no hay ninguna (modo --rapido) se usan todas.
    grandes = [f for f in sin_podas if int(f["nodos"]) >= 1e5] or sin_podas
    ns_por_nodo = statistics.median([float(f["ms"]) * 1e6 / int(f["nodos"]) for f in grandes]) if grandes else 0.0
    for configuracion in CONFIGURACIONES_BT:
        puntos = filas_ok(filas, familia=familia, serie="vs_n", configuracion=configuracion)
        puntos.sort(key=lambda f: int(f["n"]))
        if puntos:
            ns = [int(f["n"]) for f in puntos]
            fg.serie(ejes[0], ns, [float(f["ms"]) for f in puntos], configuracion)
            fg.serie(ejes[1], ns, [float(f["ms"]) * 1e6 / int(f["nodos"]) for f in puntos], configuracion)
    if sin_podas:
        ns = sorted({int(f["n"]) for f in sin_podas})
        ejes[0].plot(ns, [ns_por_nodo * 2 ** (n - 2) / 1e6 for n in ns], "--", color=fg.PALETA["modelo"],
                     linewidth=1.0, zorder=1,
                     label="$2^{{n-2}}$ nodos a {:.1f} ns".format(ns_por_nodo).replace(".", ","))
    for ax in ejes:
        ax.set_yscale("log")
        ax.set_xlabel("n (pulsos)")
    ejes[0].set_ylabel("tiempo (ms)")
    ejes[0].set_title("Tiempo total (" + fg.FAMILIAS_TITULO[familia].lower() + ")")
    ejes[1].set_ylabel("tiempo por nodo (ns)")
    ejes[1].set_title("Tiempo por nodo visitado")
    fg.leyenda_abajo(fig, ejes[0], columnas=3)
    fg.guardar(fig, "e2_tiempo_vs_n")


# ---------------------------------------------------------------------------
# E3: escalado de PD
# ---------------------------------------------------------------------------

def modelo_pd(n, k, d):
    """Operaciones del modelo de costo de la PD implementada: O(n d + (k-2)(n-k+1)^2 d)."""
    return n * d + max(0, k - 2) * (n - k + 1) ** 2 * d


def cmd_e3(args):
    asegurar_binario()
    tabla = Csv("e3_escalado.csv", ["serie", "n", "d", "k", "costo", "maxrss_mb", "modelo_ops"]
                + COLUMNAS_TIEMPOS)
    agotado = False
    for serie, n, k, d in especificacion_e3(args.rapido):
        if serie == "vs_n" and agotado:
            continue
        instancia = generar_sintetica("estructura", n, k, d)
        cmd = comando_cpp(instancia, "pd", ruta_tmp("e3.txt"))
        r = medir(cmd, args.reps, args.timeout)
        memoria = medir_memoria_mb(cmd, args.timeout) if r["estado"] == "ok" else None
        tabla.fila(serie=serie, n=n, d=d, k=k, costo=r.get("costo"), maxrss_mb=memoria,
                   modelo_ops=modelo_pd(n, k, d), **{c: r.get(c) for c in COLUMNAS_TIEMPOS})
        if serie == "vs_n" and r["estado"] != "ok":
            agotado = True
        progreso("E3 {} n={} k={} d={}: {} ms, {} MB".format(
            serie, n, k, d, "{:.1f}".format(r["ms"]) if r["estado"] == "ok" else r["estado"],
            "?" if memoria is None else "{:.1f}".format(memoria)))
    tabla.copiar_a_datos()
    figuras_e3()


def ajuste_lineal(xs, ys):
    """Mínimos cuadrados y = a + b x. Devuelve (a, b, r2)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0.0
    a = my - b * mx
    ss = sum((y - my) ** 2 for y in ys)
    sr = sum((y - a - b * x) ** 2 for x, y in zip(xs, ys))
    return a, b, (1 - sr / ss) if ss else 1.0


def figuras_e3():
    filas = leer_csv("e3_escalado.csv")
    if not filas:
        return
    import math
    import figuras as fg

    def escala_modelo(puntos):
        # Escala del modelo: mediana de ms / operaciones sobre los puntos medidos.
        cocientes = [float(f["ms"]) / float(f["modelo_ops"]) for f in puntos if float(f["modelo_ops"]) > 0]
        return statistics.median(cocientes) if cocientes else 0.0

    def memorias_de(puntos, clave):
        return [(int(f[clave]), float(f["maxrss_mb"])) for f in puntos if numero(f["maxrss_mb"]) is not None]

    def modelo_memoria(puntos):
        # maxrss = base + bytes_por_estado * k (n-k+1): la tabla de predecesores domina.
        xs = [int(f["k"]) * (int(f["n"]) - int(f["k"]) + 1) for f in puntos if numero(f["maxrss_mb"]) is not None]
        ys = [float(f["maxrss_mb"]) for f in puntos if numero(f["maxrss_mb"]) is not None]
        return ajuste_lineal(xs, ys) if len(xs) >= 2 else None

    etiqueta_modelo = "modelo (k-2)(n-k+1)²d ajustado"

    # Pregunta: el tiempo de PD con k = n/2 crece como n^3 (pendiente en log-log) y la
    # memoria pico como k (n-k+1).
    puntos = sorted(filas_ok(filas, serie="vs_n"), key=lambda f: int(f["n"]))
    if len(puntos) >= 2:
        # Ancho físico igual al que ocupa en el informe (0,52 del ancho de texto).
        fig, ejes = fg.figura(paneles=2, compartir_y=False, ancho=3.3, alto=1.6)
        ns = [int(f["n"]) for f in puntos]
        ms = [float(f["ms"]) for f in puntos]
        escala = escala_modelo(puntos)
        _, pendiente, _ = ajuste_lineal([math.log(n) for n in ns], [math.log(m) for m in ms])
        fg.serie(ejes[0], ns, [m / 1000 for m in ms], "pd", etiqueta="medido")
        ejes[0].plot(ns, [escala * float(f["modelo_ops"]) / 1000 for f in puntos], "--",
                     color=fg.PALETA["modelo"], label="modelo ajustado")
        # Ticks en potencias redondas: a este ancho solo entran tres etiquetas.
        fg.eje_x_log(ejes[0], [n for n in ns if n in (250, 1000, 3000)] or ns)
        ejes[0].set_yscale("log")
        ejes[0].set_yticks([0.01, 0.1, 1, 10])
        ejes[0].yaxis.set_major_formatter(fg.formateador_coma())
        ejes[0].set_xlabel("n (pulsos), k = n/2")
        ejes[0].set_ylabel("tiempo (s)")
        # Las curvas ocupan la diagonal de cada panel, así que la leyenda (común a los
        # dos, el caption dice que modelo es cada uno) va debajo de la figura.
        ejes[0].text(0.97, 0.05, "pendiente: {:.2f}".format(pendiente).replace(".", ","),
                     transform=ejes[0].transAxes, ha="right", va="bottom", fontsize=8)
        memorias = memorias_de(puntos, "n")
        if memorias:
            fg.serie(ejes[1], [m[0] for m in memorias], [m[1] for m in memorias], "pd", etiqueta="medido")
            ajuste = modelo_memoria(puntos)
            if ajuste:
                base, por_estado, _ = ajuste
                ejes[1].plot(ns, [base + por_estado * int(f["k"]) * (int(f["n"]) - int(f["k"]) + 1) for f in puntos],
                             "--", color=fg.PALETA["modelo"])
        ejes[1].set_xlabel("n (pulsos)")
        ejes[1].set_ylabel("memoria (MB)")
        ejes[1].set_ylim(bottom=0)
        ejes[1].yaxis.set_major_formatter(fg.formateador_coma())
        fg.leyenda_abajo(fig, ejes[0], columnas=2)
        fg.guardar(fig, "e3_pd_vs_n")

    # Pregunta: el tiempo y la memoria en función de k siguen la forma que predice la
    # poda de estados, (k-2)(n-k+1)^2 y k(n-k+1), y no la cota genérica k n^2 d.
    puntos = sorted(filas_ok(filas, serie="vs_k"), key=lambda f: int(f["k"]))
    if len(puntos) >= 2:
        fig, ejes = fg.figura(paneles=2, alto=3.4, compartir_y=False)
        n, d = int(puntos[0]["n"]), int(puntos[0]["d"])
        ks = [int(f["k"]) for f in puntos]
        ms = [float(f["ms"]) for f in puntos]
        escala = escala_modelo(puntos)
        fg.serie(ejes[0], ks, ms, "pd", etiqueta="medido (mediana de 3)")
        ejes[0].plot(ks, [escala * float(f["modelo_ops"]) for f in puntos], "--",
                     color=fg.PALETA["modelo"], label=etiqueta_modelo)
        # La cota k n^2 d crece monótona en k; se escala para que coincida con el
        # máximo medido y se ve que no describe la caída para k cercano a n.
        k_max = ks[ms.index(max(ms))]
        ejes[0].plot(ks, [max(ms) * k / k_max for k in ks], ":", color=fg.PALETA["ninguna"],
                     label="cota k·n²·d, escalada en k = {}".format(k_max))
        ejes[0].set_xlabel("k (pulsos conservados), n = {}".format(n))
        ejes[0].set_ylabel("tiempo (ms)")
        # La cota se deja salir del panel para que el medido conserve su escala.
        ejes[0].set_ylim(0, 1.15 * max(ms))
        memorias = memorias_de(puntos, "k")
        if memorias:
            fg.serie(ejes[1], [m[0] for m in memorias], [m[1] for m in memorias], "pd", etiqueta="medido (maxrss)")
            ajuste = modelo_memoria(puntos)
            if ajuste:
                base, por_estado, _ = ajuste
                ejes[1].plot(ks, [base + por_estado * k * (n - k + 1) for k in ks], "--",
                             color=fg.PALETA["modelo"],
                             label="{:.1f} MB + {:.1f} B · k(n-k+1)".format(base, por_estado * 2 ** 20).replace(".", ","))
        ejes[1].set_xlabel("k (pulsos conservados), n = {}".format(n))
        ejes[1].set_ylabel("memoria pico (MB)")
        ejes[1].set_ylim(bottom=0)
        # Leyenda única debajo con las series de los dos paneles.
        manejadores, etiquetas = [], []
        for ax in ejes:
            h, e = ax.get_legend_handles_labels()
            manejadores += h
            etiquetas += e
        fig.legend(manejadores, etiquetas, loc="outside lower center", ncol=2)
        fg.guardar(fig, "e3_pd_vs_k")

    # Pregunta: el tiempo es proporcional a d, o hay un costo por par que no depende de d.
    puntos = sorted(filas_ok(filas, serie="vs_d"), key=lambda f: int(f["d"]))
    if len(puntos) >= 2:
        fig, ejes = fg.figura(paneles=1)
        ds = [int(f["d"]) for f in puntos]
        ms = [float(f["ms"]) for f in puntos]
        fg.serie(ejes[0], ds, ms, "pd", etiqueta="medido (mediana de 3)")
        # Recta por el origen ajustada con d >= 8, donde la norma domina el costo por par.
        grandes = [(x, y) for x, y in zip(ds, ms) if x >= 8] or list(zip(ds, ms))
        por_dim = sum(x * y for x, y in grandes) / sum(x * x for x, _ in grandes)
        ejes[0].plot([0, max(ds)], [0, por_dim * max(ds)], "--", color=fg.PALETA["modelo"],
                     label="{:.1f} ms · d (ajuste por el origen, d ≥ 8)".format(por_dim).replace(".", ","))
        ejes[0].set_xlabel("d (características por pulso), n = {}, k = {}".format(puntos[0]["n"], puntos[0]["k"]))
        ejes[0].set_ylabel("tiempo (ms)")
        ejes[0].set_xlim(left=0)
        ejes[0].set_ylim(bottom=0)
        fg.leyenda(ejes[0], loc="upper left")
        fg.guardar(fig, "e3_pd_vs_d")


# ---------------------------------------------------------------------------
# E4: lenguajes
# ---------------------------------------------------------------------------

def cmd_e4(args):
    asegurar_binario()
    tabla = Csv("e4_lenguajes.csv", ["algoritmo", "lenguaje", "familia", "n", "d", "k", "costo", "nodos"]
                + COLUMNAS_TIEMPOS)
    cocientes = Csv("e4_cocientes.csv", ["algoritmo", "n", "k", "ms_cpp", "ms_python", "cociente"])
    agotados = set()
    for algoritmo, n, k in especificacion_e4(args.rapido):
        instancia = generar_sintetica("estructura", n, k)
        tiempos = {}
        for lenguaje, armar in [("cpp", comando_cpp), ("python", comando_py)]:
            if (algoritmo, lenguaje) in agotados:
                continue
            r = medir(armar(instancia, algoritmo, ruta_tmp("e4.txt")), args.reps, args.timeout)
            tabla.fila(algoritmo=algoritmo, lenguaje=lenguaje, familia="estructura", n=n, d=D_DEFECTO, k=k,
                       **{c: r.get(c) for c in ["costo", "nodos"] + COLUMNAS_TIEMPOS})
            if r["estado"] == "ok":
                tiempos[lenguaje] = r["ms"]
            else:
                agotados.add((algoritmo, lenguaje))
        if "cpp" in tiempos and "python" in tiempos:
            cocientes.fila(algoritmo=algoritmo, n=n, k=k, ms_cpp=tiempos["cpp"], ms_python=tiempos["python"],
                           cociente=tiempos["python"] / tiempos["cpp"])
        progreso("E4 {} n={}: ".format(algoritmo, n) + ", ".join(
            "{}={:.2f} ms".format(l, t) for l, t in tiempos.items()))
    tabla.copiar_a_datos()
    cocientes.copiar_a_datos()
    figuras_e4()


def figuras_e4():
    filas = leer_csv("e4_lenguajes.csv")
    if not filas:
        return
    import statistics
    import figuras as fg
    # Pregunta: cuánto más tarda Python que C++ con el mismo algoritmo.
    fig, ejes = fg.figura(paneles=2, compartir_y=False)
    for ax, algoritmo in zip(ejes, ["bt", "pd"]):
        for lenguaje, clave, estilo in [("cpp", algoritmo, "-"), ("python", "py-" + algoritmo, "--")]:
            puntos = sorted(filas_ok(filas, algoritmo=algoritmo, lenguaje=lenguaje), key=lambda f: int(f["n"]))
            if puntos:
                fg.serie(ax, [int(f["n"]) for f in puntos], [float(f["ms"]) for f in puntos], clave,
                         etiqueta="C++" if lenguaje == "cpp" else "Python", estilo=estilo)
        if algoritmo == "pd":
            # Guía de crecimiento cúbico (k n^2 d con k = n/2) anclada en el primer punto de C++.
            base = sorted(filas_ok(filas, algoritmo="pd", lenguaje="cpp"), key=lambda f: int(f["n"]))
            if base:
                n0, t0 = int(base[0]["n"]), float(base[0]["ms"])
                ns = [int(f["n"]) for f in base]
                ax.plot(ns, [t0 * (n / n0) ** 3 for n in ns], ":", color=fg.PALETA["modelo"],
                        linewidth=1.0, label="proporcional a n³")
        ax.set_yscale("log")
        fg.eje_x_log(ax, [int(f["n"]) for f in filas_ok(filas, algoritmo=algoritmo)])
        ax.set_xlabel("n (pulsos), k = n/2")
        ax.set_title(fg.ETIQUETAS[algoritmo])
    ejes[0].set_ylabel("tiempo (ms)")
    # Leyenda neutra: el color cambia entre paneles (azul BT, verde PD) y lo que
    # distingue el lenguaje es el trazo (lleno C++, a trazos Python).
    from matplotlib.lines import Line2D
    gris = fg.PALETA["ninguna"]
    manejadores = [Line2D([], [], color=gris, linestyle="-", marker="o", label="C++"),
                   Line2D([], [], color=gris, linestyle="--", marker="o", alpha=0.6, label="Python"),
                   Line2D([], [], color=fg.PALETA["modelo"], linestyle=":", linewidth=1.0,
                          label="proporcional a n³ (solo PD)")]
    fig.legend(handles=manejadores, loc="outside lower center", ncol=3)
    fg.guardar(fig, "e4_lenguajes")

    cocientes = leer_csv("e4_cocientes.csv")
    if cocientes:
        # Ancho físico igual al que ocupa en el informe (0,42 del ancho de texto); las
        # medianas van en el caption.
        fig, ejes = fg.figura(paneles=1, ancho=2.65, alto=2.2)
        for algoritmo in ["bt", "pd"]:
            puntos = sorted([f for f in cocientes if f["algoritmo"] == algoritmo], key=lambda f: int(f["n"]))
            if not puntos:
                continue
            # Mediana del cociente sobre n >= 100, donde deja de pesar el costo fijo de C++.
            estables = [float(f["cociente"]) for f in puntos if int(f["n"]) >= 100]
            etiqueta = fg.ETIQUETAS[algoritmo]
            if estables:
                mediana = statistics.median(estables)
                ejes[0].axhline(mediana, color=fg.PALETA[algoritmo], linestyle=":", linewidth=1.0, alpha=0.8)
            fg.serie(ejes[0], [int(f["n"]) for f in puntos], [float(f["cociente"]) for f in puntos],
                     algoritmo, etiqueta=etiqueta)
        # Ticks explicitos: en un panel de 2,65 in las etiquetas 400, 600 y 1000 se pisan.
        ns_medidos = sorted({int(f["n"]) for f in cocientes})
        ticks = [n for n in (25, 50, 100, 200, 400, 1000) if ns_medidos[0] <= n <= ns_medidos[-1]]
        fg.eje_x_log(ejes[0], ticks or ns_medidos)
        ejes[0].set_xlabel("n (pulsos), k = n/2")
        ejes[0].set_ylabel("tiempo Python / tiempo C++")
        ejes[0].set_ylim(bottom=0)
        fg.leyenda(ejes[0], loc="lower right")
        fg.guardar(fig, "e4_cociente")


# ---------------------------------------------------------------------------
# E5: audio real
# ---------------------------------------------------------------------------

def seleccion_truncar(n, k):
    return list(range(1, k)) + [n]


def seleccion_uniforme(n, k):
    """k índices equiespaciados entre 1 y n. Con k <= n el paso es >= 1, así que el
    redondeo deja la secuencia estrictamente creciente."""
    if k == 1:
        return [1]
    return [int(round(1 + (n - 1) * t / (k - 1))) for t in range(k)]


def saltos_y_tramos(seleccion):
    """Cantidad de saltos (pares consecutivos no adyacentes) y largos descartados."""
    tramos = [b - a - 1 for a, b in zip(seleccion, seleccion[1:]) if b != a + 1]
    return len(tramos), tramos


def leer_fronteras(nombre):
    ruta = os.path.join(DIR_REAL, nombre + "_pulsos.txt")
    with open(ruta, encoding="utf-8") as archivo:
        return [float(l) for l in archivo if l.strip()]


def duracion_recorte(fronteras, seleccion):
    return sum(fronteras[i] - fronteras[i - 1] for i in seleccion)


def matriz_costos(features):
    """costos[i-1, j-1] = c(i, j) = ||f_{i+1} - f_j|| para i en 1..n-1 y j en 1..n."""
    import numpy as np
    f = np.array(features)
    return np.linalg.norm(f[1:, None, :] - f[None, :, :], axis=2)


def percentiles_saltos(costos, saltos):
    """Percentil del costo de cada salto (a, b) entre todos los saltos posibles, es decir
    los pares i < j con j >= i + 2 (los pares adyacentes no descartan nada)."""
    import numpy as np
    n = costos.shape[1]
    filas_ij, columnas_ij = np.triu_indices(n - 1, k=2, m=n)
    posibles = costos[filas_ij, columnas_ij]
    return [100.0 * np.mean(posibles < costos[a - 1, b - 1]) for a, b in saltos]


def pulsos_descartados(n, seleccion):
    return set(range(1, n + 1)) - set(seleccion)


def cmd_e5(args):
    asegurar_binario()
    columnas = ["nombre", "caracteristicas", "n", "d", "proporcion", "k", "costo_optimo", "costo_truncar",
                "costo_uniforme", "saltos_optimo", "saltos_uniforme", "tramos_descartados", "largo_max",
                "largo_medio", "percentil_saltos", "percentil_truncar", "duracion_original_s",
                "duracion_recorte_s", "ms", "estado"]
    tabla = Csv("e5_audio.csv", columnas)
    nombres = instancias_reales()
    if args.rapido:
        nombres = [nb for nb in nombres if nb in ("hgf_corta", "hgf_corta_mfcc", "action")]
    dir_instancias = os.path.join(DIR_NUMERICOS, "instancias_e5")
    selecciones = {}
    fronteras_de = {}
    for nombre in nombres:
        base = nombre[:-5] if nombre.endswith("_mfcc") else nombre
        caracteristicas = "mfcc" if nombre.endswith("_mfcc") else "croma"
        n, d, lineas = leer_lineas_pulsos(os.path.join(DIR_REAL, nombre + ".txt"))
        fronteras = leer_fronteras(nombre)
        fronteras_de[base] = fronteras
        _, _, _, features = leer_instancia(os.path.join(DIR_REAL, nombre + ".txt"))
        costos = matriz_costos(features)
        for proporcion in PROPORCIONES_E5:
            k = max(2, min(n, int(round(proporcion * n))))
            etiqueta = "{}_{}".format(nombre, int(round(100 * proporcion)))
            instancia = os.path.join(dir_instancias, etiqueta + ".txt")
            escribir_instancia_derivada(instancia, n, d, k, lineas)
            salida = os.path.join(dir_instancias, etiqueta + "_seleccion.txt")
            r = medir(comando_cpp(instancia, "pd", salida), args.reps, args.timeout)
            if r["estado"] != "ok":
                tabla.fila(nombre=base, caracteristicas=caracteristicas, n=n, d=d, proporcion=proporcion,
                           k=k, estado=r["estado"])
                continue
            optimo = r["seleccion"]
            truncar = seleccion_truncar(n, k)
            uniforme = seleccion_uniforme(n, k)
            saltos, tramos = saltos_y_tramos(optimo)
            selecciones[(base, caracteristicas, proporcion)] = (optimo, r["costo"], costo_seleccion(features, truncar))
            pares = [(a, b) for a, b in zip(optimo, optimo[1:]) if b != a + 1]
            tabla.fila(nombre=base, caracteristicas=caracteristicas, n=n, d=d, proporcion=proporcion, k=k,
                       costo_optimo=r["costo"], costo_truncar=costo_seleccion(features, truncar),
                       costo_uniforme=costo_seleccion(features, uniforme), saltos_optimo=saltos,
                       saltos_uniforme=saltos_y_tramos(uniforme)[0],
                       tramos_descartados=";".join(str(t) for t in tramos),
                       largo_max=max(tramos) if tramos else 0,
                       largo_medio=statistics.mean(tramos) if tramos else 0,
                       percentil_saltos=";".join("{:.2f}".format(p) for p in percentiles_saltos(costos, pares)),
                       percentil_truncar="{:.2f}".format(percentiles_saltos(costos, [(k - 1, n)])[0]),
                       duracion_original_s=fronteras[n] - fronteras[0],
                       duracion_recorte_s=duracion_recorte(fronteras, optimo), ms=r["ms"], estado="ok")
            progreso("E5 {} {:.0%}: costo {:.4g} (truncar {:.4g}), {} saltos, {:.1f} ms".format(
                nombre, proporcion, r["costo"], costo_seleccion(features, truncar), saltos, r["ms"]))
            # Audio recortado al 70 %: los tres temas de MacLeod y una escena (croma y mfcc).
            reconstruir = nombre == "hgf_corta" if args.rapido else nombre in RECONSTRUIR_E5
            if proporcion == 0.7 and reconstruir:
                reconstruir_audio(base, salida, nombre, etiqueta)
        if base in TEMAS_ESTRUCTURA_E5 and caracteristicas == "croma" and (base, "croma", 0.7) in selecciones:
            figura_estructura(base, costos, selecciones[(base, "croma", 0.7)][0], fronteras)
    tabla.copiar_a_datos()

    # Croma vs mfcc en los diálogos: mismas escenas, mismos k. El jaccard de las selecciones
    # tiene piso (2p - 1) / 1 cuando ambas conservan p n pulsos (0,8 con p = 0,9 aunque los
    # descartes sean disjuntos), así que se informa también el jaccard de los descartados.
    comparacion = Csv("e5_croma_mfcc.csv", ["nombre", "proporcion", "k", "saltos_croma", "saltos_mfcc",
                                            "mejora_croma", "mejora_mfcc", "jaccard", "jaccard_descartados",
                                            "descartado_s", "solapamiento_s"])
    for (base, caracteristicas, proporcion), (optimo, costo, costo_truncar) in sorted(selecciones.items()):
        if caracteristicas != "croma" or (base, "mfcc", proporcion) not in selecciones:
            continue
        optimo_mfcc, costo_mfcc, truncar_mfcc = selecciones[(base, "mfcc", proporcion)]
        n = optimo[-1]
        fronteras = fronteras_de[base]
        descartados = pulsos_descartados(n, optimo)
        descartados_mfcc = pulsos_descartados(n, optimo_mfcc)
        comunes = descartados & descartados_mfcc
        comparacion.fila(nombre=base, proporcion=proporcion, k=len(optimo),
                         saltos_croma=saltos_y_tramos(optimo)[0], saltos_mfcc=saltos_y_tramos(optimo_mfcc)[0],
                         mejora_croma=costo / costo_truncar if costo_truncar > 0 else "",
                         mejora_mfcc=costo_mfcc / truncar_mfcc if truncar_mfcc > 0 else "",
                         jaccard=len(set(optimo) & set(optimo_mfcc)) / len(set(optimo) | set(optimo_mfcc)),
                         jaccard_descartados=len(comunes) / len(descartados | descartados_mfcc),
                         descartado_s=sum(fronteras[i] - fronteras[i - 1] for i in descartados),
                         solapamiento_s=sum(fronteras[i] - fronteras[i - 1] for i in comunes))
    comparacion.copiar_a_datos()
    figuras_e5()


def reconstruir_audio(base, seleccion, nombre_instancia, etiqueta):
    """Recorta el mp3 original con reconstruir.py (usa librosa y soundfile del venv)."""
    audio = os.path.join(DIR_AUDIO, AUDIO_DE.get(base, ""))
    if not os.path.exists(audio):
        progreso("  audio {} no disponible, no se reconstruye (ver audio/descargar.sh)".format(audio))
        return
    pulsos = os.path.join(DIR_REAL, nombre_instancia + "_pulsos.txt")
    salida = os.path.join(DIR_AUDIO_SALIDA, etiqueta + ".wav")
    os.makedirs(DIR_AUDIO_SALIDA, exist_ok=True)
    cmd = [sys.executable, RECONSTRUIR_PY, audio, seleccion, "--pulsos", pulsos, "--salida", salida]
    proceso = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True)
    if proceso.returncode != 0:
        progreso("  fallo reconstruir.py: " + proceso.stderr.strip()[-300:])
    else:
        progreso("  audio: " + os.path.relpath(salida) + " (" + proceso.stdout.strip().splitlines()[-2] + ")")


def figura_estructura(base, costos, seleccion, fronteras=None):
    """Matriz de costos c(i, j) = ||f_{i+1} - f_j|| con los saltos de la selección óptima.
    Pregunta: los saltos caen en zonas de costo bajo lejos de la diagonal, es decir entre
    secciones repetidas del tema."""
    import numpy as np
    import figuras as fg
    n = costos.shape[1]
    # Ancho físico igual al que ocupa en el informe (0,42 del ancho de texto).
    fig, ejes = fg.figura(paneles=1, ancho=2.65, alto=2.3)
    ax = ejes[0]
    ax.grid(False)
    # fila i (base 1, 1..n-1) y columna j (1..n): distancia entre el pulso que debería
    # sonar después de i y el pulso j al que se salta.
    imagen = ax.imshow(costos, origin="lower", cmap="viridis", extent=(0.5, n + 0.5, 0.5, n - 0.5),
                       aspect="auto", interpolation="nearest")
    fig.colorbar(imagen, ax=ax, label="c(i, j)", shrink=0.85)
    saltos = [(a, b) for a, b in zip(seleccion, seleccion[1:]) if b != a + 1]
    for a, b in saltos:
        ax.axvspan(a + 0.5, b - 0.5, color="white", alpha=0.22, lw=0)
    manejadores = []
    if saltos:
        from matplotlib.patches import Patch
        manejadores.append(Patch(facecolor="white", edgecolor="#7f7f7f",
                                 label="columnas aclaradas: pulsos descartados"))
        manejadores.append(ax.scatter([b for _, b in saltos], [a for a, _ in saltos], s=80, facecolors="none",
                                      edgecolors=fg.PALETA["acento"], linewidths=1.8,
                                      label="salto (i, j) de la selección óptima"))
    ax.set_xlabel("j (pulso al que se salta)")
    ax.set_ylabel("i (pulso previo al salto)")
    if fronteras is not None:
        # Eje superior en segundos de la grabación original (el pulso p empieza en
        # fronteras[p-1]; la instancia arranca en el primer onset, no en 0).
        indices = np.arange(1, n + 1)
        segundos = np.array(fronteras[:n])
        arriba = ax.secondary_xaxis("top", functions=(lambda p: np.interp(p, indices, segundos),
                                                      lambda s: np.interp(s, segundos, indices)))
        # Ticks solo dentro del rango de la grabación: fuera de el np.interp satura y
        # matplotlib apilaria etiquetas en los bordes.
        from matplotlib.ticker import FixedLocator, MaxNLocator
        candidatos = MaxNLocator(nbins=8, steps=[1, 2, 5, 10]).tick_values(segundos[0], segundos[-1])
        arriba.xaxis.set_major_locator(FixedLocator([t for t in candidatos
                                                     if segundos[0] - 1 <= t <= segundos[-1]]))
        arriba.set_xlabel("tiempo en la grabación (s)")
    if manejadores:
        fig.legend(handles=manejadores, loc="outside lower center", ncol=1)
    fg.guardar(fig, "e5_estructura_" + base)


def figuras_e5():
    filas = leer_csv("e5_audio.csv")
    if not filas:
        return
    import numpy as np
    import figuras as fg
    filas = [f for f in filas if f["estado"] == "ok"]
    # Pregunta: cuánto mejora el óptimo a truncar y a muestrear uniforme en cada grabación.
    # Se grafican cocientes, no costos absolutos: croma y mfcc tienen escalas distintas.
    orden = list(AUDIO_DE)
    claves = sorted(set((f["nombre"], f["caracteristicas"]) for f in filas),
                    key=lambda c: (c[1] != "croma", orden.index(c[0]) if c[0] in orden else 99))
    # Nombres cortos para que las etiquetas rotadas no se coman el alto del panel.
    cortos = {"action": "Action", "ascending_the_vale": "Asc. the Vale", "batty_mcfaddin": "Batty McF.",
              "hgf_corta": "HGF corta", "hgf_media": "HGF media", "hgf_larga": "HGF larga",
              "suspense": "Suspense"}
    etiquetas = [cortos.get(nb, nb.replace("_", " ")) + (" (MFCC)" if car == "mfcc" else "")
                 for nb, car in claves]

    def valor(nombre, car, proporcion, columna):
        fila = [f for f in filas if f["nombre"] == nombre and f["caracteristicas"] == car
                and float(f["proporcion"]) == proporcion]
        return float(fila[0][columna]) if fila else np.nan

    if claves:
        # Ancho físico igual al que ocupa en el informe (0,55 del ancho de texto). Barras
        # horizontales: con once instancias las etiquetas rotadas no se leen a ese ancho,
        # en el eje y quedan horizontales a 8 pt y compartidas por los dos paneles.
        fig, ejes = fg.figura(paneles=2, compartir_y=True, ancho=3.45, alto=2.3)
        ancho = 0.27
        y = -np.arange(len(claves))  # la primera instancia arriba
        for desplazamiento, proporcion, alfa in zip([ancho, 0, -ancho], PROPORCIONES_E5, fg.ALFAS_TRES):
            vs_truncar = [valor(nb, car, proporcion, "costo_optimo") / valor(nb, car, proporcion, "costo_truncar")
                          for nb, car in claves]
            vs_uniforme = [valor(nb, car, proporcion, "costo_uniforme") / valor(nb, car, proporcion, "costo_optimo")
                           for nb, car in claves]
            ejes[0].barh(y + desplazamiento, vs_truncar, height=ancho, color=fg.PALETA["optimo"], alpha=alfa,
                         label="k = {:.0f} %".format(100 * proporcion))
            ejes[1].barh(y + desplazamiento, vs_uniforme, height=ancho, color=fg.PALETA["optimo"], alpha=alfa)
        ejes[0].axvline(1, color=fg.PALETA["truncar"], lw=0.8, ls="--")
        ejes[0].set_xlabel("óptimo / truncar")
        ejes[0].set_xlim(0, 1.05)
        ejes[0].xaxis.set_major_formatter(fg.formateador_coma())
        ejes[1].set_xscale("log")
        ejes[1].set_xlabel("uniforme / óptimo")
        ejes[0].set_yticks(y)
        ejes[0].set_yticklabels(etiquetas, fontsize=8)
        for ax in ejes:
            ax.grid(False, axis="y")
        fg.leyenda_abajo(fig, ejes[0])
        fg.guardar(fig, "e5_baselines")

    # Pregunta: en diálogos, croma y mfcc descartan los mismos tramos?
    comparacion = leer_csv("e5_croma_mfcc.csv")
    if comparacion and "jaccard_descartados" in comparacion[0]:
        fig, ejes = fg.figura(paneles=2, compartir_y=False, alto=3.1)
        nombres = sorted(set(f["nombre"] for f in comparacion))
        for nombre, color, marcador in zip(nombres, fg.SERIE_NEUTRA, ["o", "s", "^", "D"]):
            puntos = sorted((float(f["proporcion"]), float(f["jaccard_descartados"]))
                            for f in comparacion if f["nombre"] == nombre)
            ejes[0].plot([100 * p for p, _ in puntos], [j for _, j in puntos], marker=marcador, color=color,
                         label=nombre.replace("_", " "))
        ejes[0].set_xticks([100 * p for p in PROPORCIONES_E5])
        ejes[0].set_xlabel("k como porcentaje de n")
        ejes[0].set_ylabel("Jaccard de los descartados")
        ejes[0].set_ylim(-0.03, 1.03)
        fg.leyenda(ejes[0], loc="upper right")
        # Línea de tiempo al 70 %: en gris la escena entera, en color los tramos descartados.
        ax = ejes[1]
        dir_instancias = os.path.join(DIR_NUMERICOS, "instancias_e5")
        nombre_car = {"croma": "croma", "mfcc": "MFCC"}
        posiciones, etiquetas_y = [], []
        ya_etiquetado = set()
        for indice, nombre in enumerate(nombres):
            fronteras = leer_fronteras(nombre)
            inicio = fronteras[0]  # la escena empieza en el primer onset
            for sub, car in enumerate(["croma", "mfcc"]):
                sufijo = "_mfcc" if car == "mfcc" else ""
                ruta = os.path.join(dir_instancias, "{}{}_70_seleccion.txt".format(nombre, sufijo))
                if not os.path.exists(ruta):
                    continue
                with open(ruta, encoding="utf-8") as archivo:
                    seleccion = [int(t) for t in archivo.read().split()]
                y = -(indice * 2.6 + sub)
                ax.barh(y, fronteras[-1] - inicio, left=inicio, height=0.8, color="#e4e4e4")
                for a, b in zip(seleccion, seleccion[1:]):
                    if b != a + 1:
                        etiqueta = None if car in ya_etiquetado else "tramo descartado ({})".format(nombre_car[car])
                        ya_etiquetado.add(car)
                        ax.barh(y, fronteras[b - 1] - fronteras[a], left=fronteras[a], height=0.8,
                                color=fg.PALETA[car], label=etiqueta)
                posiciones.append(y)
                etiquetas_y.append("{} ({})".format(nombre.replace("_", " "), nombre_car[car]))
        ax.set_yticks(posiciones)
        ax.set_yticklabels(etiquetas_y, fontsize=7)
        ax.set_xlabel("tiempo (s), k = 70 % de n")
        ax.grid(False, axis="y")
        manejadores = ejes[0].get_legend_handles_labels()[0] + ax.get_legend_handles_labels()[0]
        etiquetas_leyenda = ejes[0].get_legend_handles_labels()[1] + ax.get_legend_handles_labels()[1]
        ejes[0].get_legend().remove()
        fig.legend(manejadores, etiquetas_leyenda, loc="outside lower center", ncol=3)
        fg.guardar(fig, "e5_croma_vs_mfcc")


# ---------------------------------------------------------------------------
# E6: tiempos sobre prefijos reales
# ---------------------------------------------------------------------------

def cmd_e6(args):
    asegurar_binario()
    tabla = Csv("e6_tiempos_reales.csv", ["instancia", "n", "d", "k", "algoritmo", "costo", "nodos"]
                + COLUMNAS_TIEMPOS)
    n_total, d, lineas = leer_lineas_pulsos(os.path.join(DIR_REAL, INSTANCIA_E6 + ".txt"))
    ns_fb, ns_resto = especificacion_e6(args.rapido)
    ns = sorted(set(ns_fb + [n for n in ns_resto if n < n_total] + ([n_total] if not args.rapido else [])))
    dir_instancias = os.path.join(DIR_NUMERICOS, "instancias_e6")
    agotados = set()
    for n in ns:
        k = max(2, int(round(0.7 * n)))
        instancia = os.path.join(dir_instancias, "{}_n{}_k{}.txt".format(INSTANCIA_E6, n, k))
        escribir_instancia_derivada(instancia, n, d, k, lineas[:n])
        resumen = []
        for algoritmo in ["fb", "bt", "pd"]:
            if algoritmo in agotados or (algoritmo == "fb" and n not in ns_fb):
                continue
            r = medir(comando_cpp(instancia, algoritmo, ruta_tmp("e6.txt")), args.reps, args.timeout)
            tabla.fila(instancia=INSTANCIA_E6, n=n, d=d, k=k, algoritmo=algoritmo,
                       **{c: r.get(c) for c in ["costo", "nodos"] + COLUMNAS_TIEMPOS})
            resumen.append("{}={}".format(algoritmo, "{:.2f} ms".format(r["ms"]) if r["estado"] == "ok" else r["estado"]))
            if r["estado"] != "ok":
                agotados.add(algoritmo)
        progreso("E6 {} n={} k={}: ".format(INSTANCIA_E6, n, k) + ", ".join(resumen))
    tabla.copiar_a_datos()
    figuras_e6()


def figuras_e6():
    filas = leer_csv("e6_tiempos_reales.csv")
    if not filas:
        return
    import figuras as fg
    d = int(filas[0]["d"])
    ticks = [5, 10, 20, 50, 100, 200, 500]

    def puntos_de(algoritmo):
        return sorted(filas_ok(filas, algoritmo=algoritmo), key=lambda f: int(f["n"]))

    def escala(puntos, modelo, n_min):
        # ms por operación del modelo: mediana sobre los prefijos con n >= n_min,
        # donde el costo fijo por corrida ya no pesa.
        cocientes = [float(f["ms"]) / modelo(int(f["n"]), int(f["k"]), d)
                     for f in puntos if int(f["n"]) >= n_min]
        return statistics.median(cocientes) if cocientes else 0.0

    # Pregunta: hasta qué n llega cada exacto en un tema real y si el tiempo sigue
    # el modelo de operaciones de cada uno (FB: C(n-2,k-2) k d; PD: (k-2)(n-k+1)^2 d).
    # Ancho físico igual al que ocupa en el informe (0,47 del ancho de texto); las
    # fórmulas de los modelos van en el caption.
    fig, ejes = fg.figura(paneles=1, ancho=3.0, alto=2.1)
    ax = ejes[0]
    # (modelo, n mínimo del ajuste, n desde donde se dibuja, etiqueta)
    modelos = {"fb": (modelo_fb, 16, 12, "modelo FB"),
               "pd": (modelo_pd, 100, 40, "modelo PD")}
    for algoritmo in ["fb", "bt", "pd"]:
        puntos = puntos_de(algoritmo)
        if not puntos:
            continue
        ns = [int(f["n"]) for f in puntos]
        fg.serie(ax, ns, [float(f["ms"]) for f in puntos], algoritmo)
        if algoritmo in modelos:
            modelo, n_min, n_dibujo, etiqueta = modelos[algoritmo]
            factor = escala(puntos, modelo, n_min)
            dibujo = [f for f in puntos if int(f["n"]) >= n_dibujo]
            ax.plot([int(f["n"]) for f in dibujo],
                    [factor * modelo(int(f["n"]), int(f["k"]), d) for f in dibujo], "--",
                    color=fg.PALETA[algoritmo], linewidth=1.0, alpha=0.8, label=etiqueta)
    ax.set_yscale("log")
    ns_todos = sorted(set(int(f["n"]) for f in filas_ok(filas)))
    fg.eje_x_log(ax, [n for n in ticks if ns_todos[0] <= n <= ns_todos[-1] * 1.1])
    ax.set_xlabel("n (primeros pulsos), k = 0,7 n")
    ax.set_ylabel("tiempo (ms)")
    fg.leyenda_abajo(fig, ax, columnas=2)
    fg.guardar(fig, "e6_tiempos_reales")

    # Pregunta: por qué BT es errático en el tema real. Nodos visitados y cociente
    # de tiempo contra PD sobre los mismos prefijos.
    bt = puntos_de("bt")
    pd = {int(f["n"]): float(f["ms"]) for f in puntos_de("pd")}
    bt = [f for f in bt if numero(f["nodos"]) is not None and int(f["n"]) in pd]
    if bt:
        fig, ejes = fg.figura(paneles=2, compartir_y=False)
        ns = [int(f["n"]) for f in bt]
        fg.serie(ejes[0], ns, [int(f["nodos"]) for f in bt], "bt", etiqueta="nodos visitados")
        ejes[0].set_yscale("log")
        ejes[0].set_ylabel("nodos visitados por BT")
        cocientes = [float(f["ms"]) / pd[int(f["n"])] for f in bt]
        ejes[1].axhline(1.0, color=fg.PALETA["modelo"], linewidth=0.8, linestyle=":")
        fg.serie(ejes[1], ns, cocientes, "bt", etiqueta="tiempo BT / tiempo PD")
        ejes[1].set_yscale("log")
        ejes[1].set_ylabel("tiempo BT / tiempo PD")
        for ax in ejes:
            fg.eje_x_log(ax, [n for n in ticks if ns[0] <= n <= ns[-1] * 1.1])
            ax.set_xlabel("n (prefijo), k = 0,7 n")
        fg.guardar(fig, "e6_bt_nodos")


# ---------------------------------------------------------------------------
# figuras y todo
# ---------------------------------------------------------------------------

def cmd_figuras(args):
    for funcion in [figuras_e1, figuras_e2, figuras_e3, figuras_e4, figuras_e5, figuras_e6]:
        funcion()
    # La matriz de estructura de E5 necesita las selecciones: se rehacen desde los CSV.
    filas = leer_csv("e5_audio.csv")
    dir_instancias = os.path.join(DIR_NUMERICOS, "instancias_e5")
    for base in TEMAS_ESTRUCTURA_E5:
        seleccion = os.path.join(dir_instancias, base + "_70_seleccion.txt")
        if any(f["nombre"] == base for f in filas) and os.path.exists(seleccion):
            _, _, _, features = leer_instancia(os.path.join(DIR_REAL, base + ".txt"))
            with open(seleccion, encoding="utf-8") as archivo:
                figura_estructura(base, matriz_costos(features), [int(x) for x in archivo.read().split()],
                                  leer_fronteras(base))


def configurar_rapido(con_figuras):
    """En modo --rapido nada se escribe en informe/: los CSV, los temporales y las
    figuras van a TP1/output/numericos/rapido/ para no pisar los datos del informe."""
    global DIR_NUMERICOS, DIR_TMP, DIR_DATOS
    DIR_NUMERICOS = DIR_RAPIDO
    DIR_TMP = os.path.join(DIR_RAPIDO, "tmp")
    DIR_DATOS = DIR_RAPIDO
    if con_figuras:
        import figuras
        figuras.DIR_FIGURAS = os.path.join(DIR_RAPIDO, "figuras")


def cmd_todo(args):
    inicio = time.time()
    cmd_generar(args)
    for nombre, funcion, timeout in [("e1", cmd_e1, 60), ("e2", cmd_e2, 60), ("e3", cmd_e3, 150),
                                     ("e4", cmd_e4, 150), ("e5", cmd_e5, 60), ("e6", cmd_e6, 60)]:
        parcial = time.time()
        args.timeout = args.timeout_global if args.timeout_global else timeout
        progreso("==== {} ====".format(nombre))
        funcion(args)
        progreso("==== {} listo en {:.1f} min ====".format(nombre, (time.time() - parcial) / 60))
    progreso("todo listo en {:.1f} min".format((time.time() - inicio) / 60))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("subcomando", choices=["generar", "e1", "e2", "e3", "e4", "e5", "e6", "figuras", "todo"])
    parser.add_argument("--rapido", action="store_true", help="version reducida para probar de punta a punta")
    parser.add_argument("--reps", type=int, default=3, help="corridas por medicion (se toma la mediana)")
    parser.add_argument("--timeout", type=float, default=None,
                        help="segundos por corrida (por defecto 60, o 150 en e3 y e4)")
    args = parser.parse_args(argv)
    args.timeout_global = args.timeout
    defectos = {"e3": 150, "e4": 150}
    if args.timeout is None:
        args.timeout = defectos.get(args.subcomando, 60)
    if args.rapido:
        args.reps = 1
        configurar_rapido(args.subcomando != "generar")
    funciones = {"generar": cmd_generar, "e1": cmd_e1, "e2": cmd_e2, "e3": cmd_e3, "e4": cmd_e4,
                 "e5": cmd_e5, "e6": cmd_e6, "figuras": cmd_figuras, "todo": cmd_todo}
    funciones[args.subcomando](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
