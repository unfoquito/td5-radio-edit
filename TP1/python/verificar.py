#!/usr/bin/env python3
"""Verificador cruzado de los solvers de radio edit.

Genera instancias chicas al azar (n entre 2 y 12, d entre 1 y 4, k entre 2 y n,
incluyendo los bordes n=2, k=2 y k=n), corre cada solver pedido con --salida a un
archivo temporal, lee la selección, la valida (k índices base 1, empieza en 1,
termina en n, estrictamente creciente), recalcula el costo en Python y compara:
  * cada solver contra el óptimo exacto calculado acá por fuerza bruta (Python),
  * los solvers entre si, con tolerancia --tol (default 1e-6).
Las instancias que producen discrepancias (costo distinto, selección inválida,
salida ilegible, error o timeout) se guardan en --carpeta con un .log al lado.

Solvers disponibles con --solvers (separados por coma):
  fb, bt, pd   binario C++ (--binario), invocado como
               <binario> --instancia X --algoritmo <alg> --salida Y
  py-bt, py-pd scripts Python (--py-bt, --py-pd), invocados como
               <python> <script> --instancia X --salida Y
Además se pueden agregar solvers arbitrarios con --comando NOMBRE=PLANTILLA,
donde la plantilla usa {instancia} y {salida}; sirve para probar el propio
verificador con un solver ficticio.

Ejemplos:
  python3 verificar.py --binario ../radioedit --solvers fb,bt,pd --cantidad 200
  python3 verificar.py --binario /tmp/mi_bin --solvers pd --comando 'trivial=python3 trivial.py {instancia} {salida}'
"""

import argparse
import itertools
import math
import os
import random
import shlex
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import generador  # noqa: E402  (mismo directorio)


# ---------------------------------------------------------------------------
# Modelo del problema en Python (independiente del C++, para poder auditarlo).
# ---------------------------------------------------------------------------

def costo_salto(pulsos, i, j):
    """c(i, j) = || f_{i+1} - f_j ||_2 con i, j en base 1 e i < j."""
    if j == i + 1:
        return 0.0
    esperado = pulsos[i]       # f_{i+1} (base 0: índice i)
    sonado = pulsos[j - 1]     # f_j
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(esperado, sonado)))


def costo_seleccion(pulsos, seleccion):
    return sum(costo_salto(pulsos, seleccion[t], seleccion[t + 1])
               for t in range(len(seleccion) - 1))


def validar_seleccion(n, k, seleccion):
    """Devuelve None si es valida o un mensaje describiendo el problema."""
    if len(seleccion) != k:
        return "tiene {} indices y k={}".format(len(seleccion), k)
    if seleccion[0] != 1:
        return "no empieza en 1 (empieza en {})".format(seleccion[0])
    if seleccion[-1] != n:
        return "no termina en n={} (termina en {})".format(n, seleccion[-1])
    for a, b in zip(seleccion, seleccion[1:]):
        if a >= b:
            return "no es estrictamente creciente ({} >= {})".format(a, b)
    return None


def optimo_fuerza_bruta(n, k, pulsos):
    """Óptimo exacto probando todas las C(n-2, k-2) selecciones. Solo para n chico."""
    mejor_costo = math.inf
    mejor = None
    for medio in itertools.combinations(range(2, n), k - 2):
        seleccion = (1,) + medio + (n,)
        c = costo_seleccion(pulsos, seleccion)
        if c < mejor_costo:
            mejor_costo, mejor = c, seleccion
    return mejor_costo, list(mejor)


# ---------------------------------------------------------------------------
# Ejecución de solvers.
# ---------------------------------------------------------------------------

def construir_comandos(args):
    """Mapa nombre -> plantilla (lista de tokens con {instancia} y {salida})."""
    comandos = {}
    for nombre in [s.strip() for s in args.solvers.split(",") if s.strip()]:
        if nombre in ("fb", "bt", "pd"):
            comandos[nombre] = [args.binario, "--instancia", "{instancia}",
                                "--algoritmo", nombre, "--salida", "{salida}"]
        elif nombre == "py-bt":
            comandos[nombre] = [args.python, args.py_bt, "--instancia", "{instancia}",
                                "--salida", "{salida}"]
        elif nombre == "py-pd":
            comandos[nombre] = [args.python, args.py_pd, "--instancia", "{instancia}",
                                "--salida", "{salida}"]
        else:
            raise SystemExit("solver desconocido en --solvers: {}".format(nombre))
    for extra in args.comando:
        if "=" not in extra:
            raise SystemExit("--comando espera NOMBRE=PLANTILLA, se recibio: " + extra)
        nombre, plantilla = extra.split("=", 1)
        comandos[nombre.strip()] = shlex.split(plantilla)
    if not comandos:
        raise SystemExit("no hay solvers para correr (ver --solvers y --comando)")
    return comandos


def correr_solver(plantilla, ruta_instancia, ruta_salida, timeout):
    """Corre el solver y devuelve (selección o None, descripción del error o None, stdout+stderr)."""
    comando = [tok.format(instancia=ruta_instancia, salida=ruta_salida) for tok in plantilla]
    if os.path.exists(ruta_salida):
        os.remove(ruta_salida)
    try:
        proceso = subprocess.run(comando, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout ({} s)".format(timeout), ""
    except OSError as e:
        return None, "no se pudo ejecutar {}: {}".format(comando[0], e), ""
    registro = proceso.stdout + proceso.stderr
    if proceso.returncode != 0:
        return None, "termino con codigo {}".format(proceso.returncode), registro
    if not os.path.exists(ruta_salida):
        return None, "no escribio el archivo de salida", registro
    with open(ruta_salida, "r", encoding="utf-8") as archivo:
        contenido = archivo.read()
    lineas = [l for l in contenido.splitlines() if l.strip()]
    if len(lineas) != 1:
        return None, "la salida debe tener exactamente una linea no vacia (tiene {})".format(
            len(lineas)), registro
    try:
        seleccion = [int(tok) for tok in lineas[0].split()]
    except ValueError:
        return None, "la salida tiene tokens que no son enteros: {!r}".format(lineas[0]), registro
    return seleccion, None, registro


# ---------------------------------------------------------------------------
# Generación de casos.
# ---------------------------------------------------------------------------

def casos_a_probar(args, rng):
    """Primero los bordes fijos, después instancias al azar mezclando los tres modos."""
    fijos = [(2, 1, 2), (2, 3, 2), (3, 1, 2), (3, 1, 3), (4, 2, 4), (5, 1, 2), (6, 1, 4),
             (args.n_max, 1, 2), (args.n_max, args.d_max, args.n_max)]
    casos = []
    for n, d, k in fijos:
        if n <= args.n_max and d <= args.d_max:
            casos.append((n, d, k, "uniforme"))
    # Además del generador común se agrega el modo "repetidos": coordenadas enteras
    # en {0, 1, 2}, así hay pulsos exactamente iguales y muchos empates de costo.
    # Sirve para chequear que los solvers no dependan de como se desempata.
    modos = ["uniforme", "estructura", "adversarial", "repetidos"]
    for n, d, k in [(2, 1, 2), (4, 1, 4), (5, 1, 2), (6, 2, 3)]:
        if n <= args.n_max and d <= args.d_max:
            casos.append((n, d, k, "repetidos"))
    while len(casos) < args.cantidad:
        n = rng.randint(2, args.n_max)
        d = rng.randint(1, args.d_max)
        k = rng.randint(2, n)
        casos.append((n, d, k, rng.choice(modos)))
    return casos[:max(args.cantidad, len(fijos))]


def generar_repetidos(n, d, semilla):
    rng = random.Random(semilla)
    return [[float(rng.randint(0, 2)) for _ in range(d)] for _ in range(n)]


def generar_caso(n, d, k, modo, semilla, ruta):
    if modo == "repetidos":
        pulsos = generar_repetidos(n, d, semilla)
        generador.escribir_instancia(ruta, n, d, k, pulsos)
        return pulsos
    extra = {}
    if modo == "estructura":
        extra = dict(patron="ABBCBB", ruido=0.05)
    elif modo == "adversarial":
        extra = dict(paso=1.0)
    _, _, _, pulsos = generador.generar(n, d, k, modo, semilla, **extra)
    generador.escribir_instancia(ruta, n, d, k, pulsos)
    return pulsos


def resumir_cobertura(casos):
    """Cuenta cuántos casos tocan cada borde interesante, para saber qué se probó."""
    return {
        "n=2": sum(1 for n, _, _, _ in casos if n == 2),
        "k=2": sum(1 for _, _, k, _ in casos if k == 2),
        "k=n": sum(1 for n, _, k, _ in casos if k == n),
        "d=1": sum(1 for _, d, _, _ in casos if d == 1),
        "repetidos": sum(1 for _, _, _, modo in casos if modo == "repetidos"),
    }


# ---------------------------------------------------------------------------
# Programa principal.
# ---------------------------------------------------------------------------

def parsear_argumentos(argv=None):
    parser = argparse.ArgumentParser(
        description="Compara solvers de radio edit sobre instancias chicas al azar.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--binario", default=os.path.join(AQUI, "..", "radioedit"),
                        help="binario C++ a usar para fb, bt y pd")
    parser.add_argument("--solvers", default="fb,bt,pd",
                        help="lista separada por coma entre fb,bt,pd,py-bt,py-pd (vacio para ninguno)")
    parser.add_argument("--comando", action="append", default=[],
                        help="solver extra NOMBRE=PLANTILLA con {instancia} y {salida}; repetible")
    parser.add_argument("--python", default=sys.executable, help="interprete para py-bt y py-pd")
    parser.add_argument("--py-bt", default=os.path.join(AQUI, "backtracking.py"))
    parser.add_argument("--py-pd", default=os.path.join(AQUI, "programacion_dinamica.py"))
    parser.add_argument("--cantidad", type=int, default=100, help="cantidad de instancias (siempre se incluyen ademas los casos borde fijos)")
    parser.add_argument("--n-max", type=int, default=12)
    parser.add_argument("--d-max", type=int, default=4)
    parser.add_argument("--semilla", type=int, default=0)
    parser.add_argument("--tol", type=float, default=1e-6, help="tolerancia al comparar costos")
    parser.add_argument("--timeout", type=float, default=60.0, help="segundos por corrida")
    parser.add_argument("--carpeta", default=os.path.join(AQUI, "..", "output", "discrepancias"),
                        help="donde guardar las instancias con discrepancias")
    parser.add_argument("--sin-referencia", action="store_true",
                        help="no calcular el optimo exacto en Python (solo comparar solvers entre si)")
    parser.add_argument("--verboso", action="store_true", help="imprimir cada caso")
    return parser.parse_args(argv)


def main(argv=None):
    args = parsear_argumentos(argv)
    comandos = construir_comandos(args)
    rng = random.Random(args.semilla)
    casos = casos_a_probar(args, rng)

    carpeta_tmp = tempfile.mkdtemp(prefix="radioedit_verificar_")
    os.makedirs(args.carpeta, exist_ok=True)

    print("Solvers: {}".format(", ".join(comandos)))
    print("Casos: {} (n <= {}, d <= {}), semilla {}, tol {}".format(
        len(casos), args.n_max, args.d_max, args.semilla, args.tol))
    print("Cobertura: " + ", ".join("{} en {} casos".format(borde, cantidad)
                                    for borde, cantidad in resumir_cobertura(casos).items()))

    discrepancias = 0
    fallas_por_solver = {nombre: 0 for nombre in comandos}
    for indice, (n, d, k, modo) in enumerate(casos):
        ruta_instancia = os.path.join(carpeta_tmp, "caso_{:04d}.txt".format(indice))
        pulsos = generar_caso(n, d, k, modo, args.semilla * 100003 + indice, ruta_instancia)

        referencia = None
        if not args.sin_referencia:
            referencia = optimo_fuerza_bruta(n, k, pulsos)

        problemas = []
        resultados = {}
        registros = {}
        for nombre, plantilla in comandos.items():
            ruta_salida = os.path.join(carpeta_tmp, "sel_{:04d}_{}.txt".format(indice, nombre))
            seleccion, error, registro = correr_solver(plantilla, ruta_instancia, ruta_salida,
                                                       args.timeout)
            registros[nombre] = registro
            if error is not None:
                problemas.append("[{}] {}".format(nombre, error))
                continue
            invalida = validar_seleccion(n, k, seleccion)
            if invalida is not None:
                problemas.append("[{}] seleccion invalida {}: {}".format(nombre, seleccion, invalida))
                continue
            costo = costo_seleccion(pulsos, seleccion)
            resultados[nombre] = (costo, seleccion)
            if referencia is not None and abs(costo - referencia[0]) > args.tol:
                problemas.append("[{}] costo {:.9f} con {} pero el optimo es {:.9f} con {}".format(
                    nombre, costo, seleccion, referencia[0], referencia[1]))

        # Comparación entre solvers (todos contra el primero que respondio bien).
        if len(resultados) >= 2:
            base_nombre = next(iter(resultados))
            base_costo = resultados[base_nombre][0]
            for nombre, (costo, seleccion) in resultados.items():
                if abs(costo - base_costo) > args.tol:
                    problemas.append("[{}] costo {:.9f} difiere de [{}] costo {:.9f}".format(
                        nombre, costo, base_nombre, base_costo))

        etiqueta = "caso {:04d} n={} d={} k={} modo={}".format(indice, n, d, k, modo)
        if problemas:
            discrepancias += 1
            solvers_con_problemas = {p.split("]")[0].lstrip("[") for p in problemas}
            for solver in solvers_con_problemas:
                if solver in fallas_por_solver:
                    fallas_por_solver[solver] += 1
            destino = os.path.join(args.carpeta, "caso_{:04d}_n{}_d{}_k{}_{}.txt".format(
                indice, n, d, k, modo))
            shutil.copyfile(ruta_instancia, destino)
            with open(destino[:-4] + ".log", "w", encoding="utf-8") as log:
                log.write(etiqueta + "\n")
                if referencia is not None:
                    log.write("optimo (python): {:.9f} {}\n".format(referencia[0], referencia[1]))
                for p in problemas:
                    log.write(p + "\n")
                for nombre, registro in registros.items():
                    if registro.strip():
                        log.write("--- salida de {} ---\n{}\n".format(nombre, registro))
            print("DISCREPANCIA {} (guardada en {})".format(etiqueta, destino))
            for p in problemas:
                print("    " + p)
        elif args.verboso:
            detalle = ", ".join("{}={:.6f}".format(nombre, r[0]) for nombre, r in resultados.items())
            print("ok  {}: {}".format(etiqueta, detalle))

    shutil.rmtree(carpeta_tmp, ignore_errors=True)

    print()
    print("Resumen: {} casos, {} con discrepancias.".format(len(casos), discrepancias))
    for nombre, fallas in fallas_por_solver.items():
        print("  {}: {} casos con problemas".format(nombre, fallas))
    return 1 if discrepancias else 0


if __name__ == "__main__":
    sys.exit(main())
