#!/usr/bin/env python3
"""Generador de instancias para el problema de radio edit.

Escribe archivos en el formato del enunciado: una primera linea "n d k" y
luego n lineas con d reales (el vector de caracteristicas de cada pulso).

Modos:
  uniforme     cada pulso es un punto uniforme en [0,1]^d (sin estructura).
  estructura   la grabacion tiene secciones repetidas (por ejemplo A B B C B B).
               Cada letra del patron tiene un vector base uniforme en [0,1]^d y
               cada pulso es el vector base de su seccion mas ruido gaussiano.
               Es el caso "musical": hay saltos casi gratis entre secciones iguales.
  adversarial  todos los pulsos son muy distintos entre si: puntos de una grilla
               regular separados por --paso, en orden aleatorio (o creciente con
               --ordenado). No hay saltos baratos, asi que las podas rinden poco.

Solo usa la biblioteca estandar, para que corra con cualquier Python 3.

Ejemplos:
  python3 generador.py --n 20 --d 2 --k 8 --modo uniforme --semilla 1 --salida ../input/u20.txt
  python3 generador.py --n 60 --d 3 --k 30 --modo estructura --patron ABBCBB --ruido 0.02 --salida ../input/e60.txt
  python3 generador.py --n 15 --d 1 --modo adversarial --paso 2 --salida ../input/a15.txt
"""

import argparse
import math
import os
import random
import sys


def generar_uniforme(n, d, rng):
    return [[rng.random() for _ in range(d)] for _ in range(n)]


def generar_estructura(n, d, rng, patron, largo_seccion=None, ruido=0.05):
    """Secciones repetidas. La seccion del pulso i (base 0) es
    patron[min(i // largo_seccion, len(patron) - 1)]: las letras se recorren
    en orden y la ultima absorbe el resto si n no es multiplo del largo."""
    if not patron:
        raise ValueError("el patron no puede ser vacio")
    if largo_seccion is None:
        largo_seccion = max(1, math.ceil(n / len(patron)))
    if largo_seccion < 1:
        raise ValueError("--largo-seccion debe ser >= 1")

    # Un vector base por letra distinta, asi dos secciones "B" comparten base.
    bases = {}
    for letra in patron:
        if letra not in bases:
            bases[letra] = [rng.random() for _ in range(d)]

    pulsos = []
    for i in range(n):
        letra = patron[min(i // largo_seccion, len(patron) - 1)]
        base = bases[letra]
        pulsos.append([b + rng.gauss(0.0, ruido) for b in base])
    return pulsos


def generar_adversarial(n, d, rng, paso=1.0, ordenado=False):
    """Puntos distintos de una grilla de lado ceil(n^(1/d)) en Z^d escalados por
    paso. Se toman los primeros n puntos en orden mixto-radix (para d=1 es la
    secuencia 0, paso, 2*paso, ...) y se mezclan salvo que se pida --ordenado.
    Con paso grande, cualquier salto cuesta al menos paso."""
    if paso <= 0:
        raise ValueError("--paso debe ser > 0")
    lado = max(2, math.ceil(n ** (1.0 / d)))
    while lado ** d < n:
        lado += 1

    puntos = []
    for indice in range(n):
        resto = indice
        coordenadas = []
        for _ in range(d):
            coordenadas.append(float(resto % lado) * paso)
            resto //= lado
        puntos.append(coordenadas)

    if not ordenado:
        rng.shuffle(puntos)
    return puntos


def escribir_instancia(ruta, n, d, k, pulsos, decimales=6):
    lineas = ["{} {} {}".format(n, d, k)]
    for vector in pulsos:
        lineas.append(" ".join("{:.{p}f}".format(x, p=decimales) for x in vector))
    contenido = "\n".join(lineas) + "\n"

    if ruta is None or ruta == "-":
        sys.stdout.write(contenido)
        return
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as archivo:
        archivo.write(contenido)


def generar(n, d, k, modo, semilla=None, patron="ABBCBB", largo_seccion=None,
            ruido=0.05, paso=1.0, ordenado=False):
    """Devuelve (n, d, k, pulsos). Valida n >= 2, d >= 1 y 2 <= k <= n."""
    if n < 2:
        raise ValueError("n debe ser >= 2")
    if d < 1:
        raise ValueError("d debe ser >= 1")
    if k is None:
        k = max(2, n // 2)
    if k < 2 or k > n:
        raise ValueError("k debe cumplir 2 <= k <= n (k={}, n={})".format(k, n))

    rng = random.Random(semilla)
    if modo == "uniforme":
        pulsos = generar_uniforme(n, d, rng)
    elif modo == "estructura":
        pulsos = generar_estructura(n, d, rng, patron, largo_seccion, ruido)
    elif modo == "adversarial":
        pulsos = generar_adversarial(n, d, rng, paso, ordenado)
    else:
        raise ValueError("modo desconocido: " + str(modo))
    return n, d, k, pulsos


def parsear_argumentos(argv=None):
    parser = argparse.ArgumentParser(
        description="Genera instancias de radio edit en el formato del enunciado.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument("--n", type=int, required=True, help="cantidad de pulsos (>= 2)")
    parser.add_argument("--d", type=int, default=1, help="dimension de las caracteristicas (>= 1)")
    parser.add_argument("--k", type=int, default=None,
                        help="pulsos a conservar (2 <= k <= n); por defecto max(2, n // 2)")
    parser.add_argument("--modo", choices=["uniforme", "estructura", "adversarial"],
                        default="uniforme")
    parser.add_argument("--semilla", type=int, default=None, help="semilla del generador aleatorio")
    parser.add_argument("--salida", default="-", help="archivo de salida ('-' es stdout)")
    parser.add_argument("--decimales", type=int, default=6, help="decimales al escribir cada valor")

    estructura = parser.add_argument_group("modo estructura")
    estructura.add_argument("--patron", default="ABBCBB",
                            help="secuencia de secciones, una letra por seccion (default ABBCBB)")
    estructura.add_argument("--largo-seccion", type=int, default=None,
                            help="pulsos por seccion; por defecto ceil(n / len(patron))")
    estructura.add_argument("--ruido", type=float, default=0.05,
                            help="desvio estandar del ruido gaussiano por componente")

    adversarial = parser.add_argument_group("modo adversarial")
    adversarial.add_argument("--paso", type=float, default=1.0,
                             help="separacion entre puntos vecinos de la grilla")
    adversarial.add_argument("--ordenado", action="store_true",
                             help="no mezclar: dejar los puntos en orden creciente de grilla")
    return parser.parse_args(argv)


def main(argv=None):
    args = parsear_argumentos(argv)
    try:
        n, d, k, pulsos = generar(args.n, args.d, args.k, args.modo, args.semilla,
                                  args.patron, args.largo_seccion, args.ruido,
                                  args.paso, args.ordenado)
    except ValueError as e:
        print("Error: {}".format(e), file=sys.stderr)
        return 1
    escribir_instancia(args.salida, n, d, k, pulsos, args.decimales)
    if args.salida not in (None, "-"):
        print("Instancia generada en {} (n={}, d={}, k={}, modo={})".format(
            args.salida, n, d, k, args.modo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
