#!/usr/bin/env python3
"""Reimplementacion en Python de los algoritmos de radio edit del TP (C++ en ../source).

Sirve para comparar lenguajes con la misma recurrencia y la misma reconstruccion
que el binario C++, asi que la version principal usa solo la biblioteca estandar.
Hay una variante opcional con numpy (programacion_dinamica_numpy) claramente
separada; no hace falta tenerlo instalado para usar el resto.

Convencion: indices base 1 en toda la interfaz publica, igual que en C++.
Internamente features[i-1] guarda el vector f_i.

Equivalencia con el binario. El costo c(i, j) se calcula con la misma aritmetica
de punto flotante que Instancia::costo, operacion por operacion y en el mismo
orden (ver _norma_diferencia). Eso importa porque las podas y los desempates
comparan doubles: con math.dist o numpy.linalg.norm, que redondean distinto, dos
caminos con el mismo costo matematico podian quedar en orden invertido y la
seleccion o la cantidad de nodos visitados dejaban de coincidir con el C++. Para
que la igualdad sea bit a bit el binario tiene que compilarse con -ffp-contract=off
(ya esta en el Makefile): sin eso clang en arm64 fusiona "suma += dif*dif" en una
FMA y el resultado difiere en 1 ulp.

Sobre instancias validas la salida es la misma que la del binario: las lineas de
pantalla, el archivo --salida y las columnas del CSV (con la etiqueta "py-pd" o
"py-bt" en la columna algoritmo, para poder mezclar el archivo con las mediciones
del C++ sin confundir filas). Diferencias conocidas, solo en entradas mal formadas:
el C++ (libc++) acepta reales en hexadecimal ("0x10") y aca se rechazan; el texto
de algunos mensajes de error de argparse no es el de main.cpp (el codigo de salida
si es 1 en los dos).

CLI con la misma interfaz que el binario:
  python3 algoritmos.py --instancia <archivo> --algoritmo <bt|pd>
                        [--salida <archivo>] [--csv <archivo>]
                        [--sin-poda-factibilidad] [--sin-poda-optimalidad]  (solo bt)
"""

import argparse
import math
import os
import re
import sys
import time


# ---------------------------------------------------------------------------
# Instancia y costo (equivalentes a Instancia::cargar e Instancia::costo).
# ---------------------------------------------------------------------------

# Tokens que acepta Instancia::cargar: enteros decimales para la cabecera y reales
# en notacion decimal (con o sin exponente) para los valores. Se valida con una
# expresion regular ASCII antes de convertir porque int() y float() de Python son
# mas permisivos que istream >> (aceptan "1_0" o digitos unicode, por ejemplo).
_ENTERO = re.compile(r"[+-]?[0-9]+")
_REAL = re.compile(r"[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?")
_MAXIMO_INT = 2 ** 31 - 1


def leer_instancia(ruta):
    """Lee el formato del enunciado y devuelve (n, d, k, features).

    features es una lista de n listas de d floats, con features[i-1] = f_i.
    Replica las validaciones de Instancia::cargar y en el mismo orden: n >= 2,
    d >= 1, 2 <= k <= n, cabecera creible (n y d entran en un int y el archivo
    tiene bytes para n*d valores), exactamente n*d valores finitos (ni de menos ni
    de mas). Se lee por tokens, asi que tolera espacios o saltos de linea extra.
    Lanza ValueError con un mensaje claro (o FileNotFoundError si no existe).
    """
    with open(ruta, "r", encoding="utf-8") as archivo:
        tokens = archivo.read().split()

    if len(tokens) < 3 or not all(_ENTERO.fullmatch(t) for t in tokens[:3]):
        raise ValueError('Instancia mal formada ({}): la primera línea debe ser "n d k" '
                         'con enteros.'.format(ruta))
    n, d, k = int(tokens[0]), int(tokens[1]), int(tokens[2])
    if n < 2:
        raise ValueError("Instancia inválida ({}): n debe ser >= 2, se leyó n={}.".format(ruta, n))
    if d < 1:
        raise ValueError("Instancia inválida ({}): d debe ser >= 1, se leyó d={}.".format(ruta, d))
    if k < 2 or k > n:
        raise ValueError("Instancia inválida ({}): k debe cumplir 2 <= k <= n, se leyó k={} "
                         "con n={}.".format(ruta, k, n))
    if n > _MAXIMO_INT or d > _MAXIMO_INT:
        raise ValueError("Instancia inválida ({}): n y d deben entrar en un int, se leyó n={}, "
                         "d={}.".format(ruta, n, d))
    bytes_archivo = os.path.getsize(ruta)
    if n * d > bytes_archivo // 2:
        raise ValueError("Instancia mal formada ({}): la cabecera declara n*d={} valores pero el "
                         "archivo tiene sólo {} bytes.".format(ruta, n * d, bytes_archivo))

    valores = tokens[3:]
    features = []
    for i in range(n):
        pulso = []
        for j in range(d):
            posicion = i * d + j
            donde = "pulso {}, componente {}".format(i + 1, j + 1)
            if posicion >= len(valores):
                raise ValueError("Instancia mal formada ({}): se esperaban {} valores reales (n*d) "
                                 "y falta el {}.".format(ruta, n * d, donde))
            token = valores[posicion]
            if not _REAL.fullmatch(token):
                raise ValueError("Instancia mal formada ({}): valor no numérico en el {}."
                                 .format(ruta, donde))
            valor = float(token)
            if not math.isfinite(valor):
                raise ValueError("Instancia mal formada ({}): valor no finito en el pulso {}."
                                 .format(ruta, i + 1))
            pulso.append(valor)
        features.append(pulso)

    if len(valores) > n * d:
        raise ValueError("Instancia mal formada ({}): hay datos de más después de los {} "
                         "valores (n*d); el primero es \"{}\".".format(ruta, n * d, valores[n * d]))
    return n, d, k, features


def _norma_diferencia(esperado, sonado):
    """|| esperado - sonado ||_2 con exactamente la aritmetica de Instancia::costo.

    Pasos, en el mismo orden que el C++: escala = max |a - b|; si es 0 la norma es
    0; si no es finita se devuelve la escala (infinito); si no, suma de
    ((a - b) / escala)^2 coordenada por coordenada y escala * sqrt(suma). Cada
    operacion es la misma operacion IEEE que hace el C++, asi que el resultado
    coincide bit a bit con el binario (compilado sin contraccion a FMA).

    La suma se acumula con un ciclo explicito, de izquierda a derecha como
    "suma += dif*dif". No sirven sum() (en Python >= 3.12 compensa el error de
    redondeo con el metodo de Neumaier y puede dar otro double), math.fsum ni
    math.dist (escala distinto). Es unas 9 veces mas lento que math.dist, el
    precio de que las podas y los desempates vean los mismos doubles que el C++.
    """
    escala = 0.0
    for a, b in zip(esperado, sonado):
        diferencia = abs(a - b)
        if diferencia > escala:
            escala = diferencia
    if escala == 0.0:
        return 0.0
    if not math.isfinite(escala):
        return escala
    suma = 0.0
    for a, b in zip(esperado, sonado):
        diferencia = (a - b) / escala
        suma += diferencia * diferencia
    return escala * math.sqrt(suma)


def costo(features, i, j):
    """c(i, j) = || f_{i+1} - f_j ||_2 con 1 <= i < j <= n (base 1).

    Despues de reproducir el pulso i deberia sonar el i+1 pero suena el j. Si
    j == i+1 no hay salto y el costo es 0, sin calcular nada (como en C++).
    """
    if j == i + 1:
        return 0.0
    return _norma_diferencia(features[i], features[j - 1])


def costo_seleccion(features, seleccion):
    """Suma c(i_t, i_{t+1}) entre consecutivos (Solucion::costo)."""
    total = 0.0
    for t in range(len(seleccion) - 1):
        total += costo(features, seleccion[t], seleccion[t + 1])
    return total


def es_valida(n, k, seleccion):
    """Solucion::esValida: k indices, empieza en 1, termina en n, estrictamente creciente."""
    if len(seleccion) != k:
        return False
    if seleccion[0] != 1 or seleccion[-1] != n:
        return False
    return all(a < b for a, b in zip(seleccion, seleccion[1:]))


# ---------------------------------------------------------------------------
# Programacion dinamica (replica de ProgramacionDinamica::resolver).
# ---------------------------------------------------------------------------

def programacion_dinamica(n, k, features):
    """Devuelve la seleccion optima (lista de k indices base 1, creciente).

    Recurrencia bottom-up, la misma que en C++:
      M[t][i] = minimo costo de una seleccion de t pulsos que empieza en 1 y termina en i
      M[1][1] = 0, M[1][i] = inf para i > 1
      M[t][i] = min_{i' < i} ( M[t-1][i'] + c(i', i) )
    La respuesta es M[k][n]. Solo se guardan dos filas (anterior y actual) mas una
    tabla de predecesores para reconstruir.

    Poda de estados: en la fila t solo son alcanzables (y utiles) los i con
    t <= i <= n - (k - t): hacen falta t-1 pulsos antes y k-t despues. Todos esos
    estados tienen predecesor valido, salvo la fila 1 cuyo unico estado es i = 1.
    Los predecesores se guardan desplazados, en la posicion t*ancho + (i - t) con
    ancho = n-k+1, asi el espacio es Theta(k (n-k+1)) y no Theta(k n).

    Empates e infinito: el predecesor se fija con el primer candidato y despues
    solo se reemplaza con "<" estricto, asi un estado con costo infinito igual
    queda con predecesor valido y en empate gana el i' mas chico. Como ademas los
    costos son los mismos doubles que en C++, la seleccion coincide y no solo el
    costo.
    """
    INF = math.inf
    ancho = n - k + 1
    norma = _norma_diferencia

    # fila_anterior[i] = M[t-1][i], fila_actual[i] = M[t][i], con i en base 1.
    # No hace falta limpiar fila_actual entre filas: la fila t+1 solo lee las
    # posiciones [t, n-k+t], que son justo las que escribio la fila t.
    fila_anterior = [INF] * (n + 1)
    fila_actual = [INF] * (n + 1)
    predecesor = [0] * ((k + 1) * ancho)

    # Caso base: con un solo pulso se esta parado en el 1 con costo 0.
    fila_anterior[1] = 0.0

    for t in range(2, k + 1):
        i_min = t
        i_max = n - (k - t)
        base_pred = t * ancho - t  # predecesor[base_pred + i] es el de (t, i)
        for i in range(i_min, i_max + 1):
            # i' recorre los estados alcanzables de la fila t-1 que estan antes de i:
            # para t >= 3 son [t-1, i-1]; para t = 2 el unico estado de la fila 1 es 1.
            # El candidato i' = i-1 cuesta c(i-1, i) = 0 (no hay salto).
            f_i = features[i - 1]
            if t == 2:
                mejor = fila_anterior[1] + (0.0 if i == 2 else norma(features[1], f_i))
                mejor_previo = 1
            else:
                mejor = INF
                mejor_previo = 0
                for previo in range(t - 1, i - 1):
                    # features[previo] es f_{previo+1}, el pulso que deberia sonar.
                    candidato = fila_anterior[previo] + norma(features[previo], f_i)
                    if mejor_previo == 0 or candidato < mejor:
                        mejor = candidato
                        mejor_previo = previo
                # Ultimo candidato, i' = i-1, con salto de costo 0.
                candidato = fila_anterior[i - 1]
                if mejor_previo == 0 or candidato < mejor:
                    mejor = candidato
                    mejor_previo = i - 1
            fila_actual[i] = mejor
            predecesor[base_pred + i] = mejor_previo
        fila_anterior, fila_actual = fila_actual, fila_anterior

    return _reconstruir(n, k, ancho, predecesor)


def _reconstruir(n, k, ancho, predecesor):
    """Sigue la cadena de predecesores desde (k, n) hasta (1, 1) y la da vuelta."""
    seleccion = []
    actual = n
    for t in range(k, 0, -1):
        seleccion.append(actual)
        if t > 1:
            actual = predecesor[t * ancho + (actual - t)]
    seleccion.reverse()
    return seleccion


def programacion_dinamica_numpy(n, k, features):
    """Variante OPCIONAL con numpy (misma recurrencia, mismos empates, mismos doubles).

    Para cada estado (t, i) se vectoriza el minimo sobre i': se calcula de una
    vez el vector de normas || f_{i'+1} - f_i || para todos los i' del rango y
    se usa argmin (que devuelve el primer indice en caso de empate, igual que el
    "<" estricto del C++). No cambia el orden de complejidad, solo la constante.

    Las normas se calculan con el mismo escalado por max|dif| que Instancia::costo
    (no con numpy.linalg.norm, que eleva al cuadrado sin escalar y desborda a
    infinito con coordenadas de modulo mayor a ~1e154, con lo que argmin elegia
    cualquier cosa). La suma de cuadrados se acumula columna por columna para
    respetar el orden de coordenadas del C++ y que el resultado sea el mismo
    double. No se usa en las mediciones principales porque numpy no es biblioteca
    estandar.
    """
    import numpy as np  # importacion local: el resto del modulo no lo necesita

    F = np.asarray(features, dtype=float)
    d = F.shape[1]
    INF = math.inf
    ancho = n - k + 1
    fila_anterior = np.full(n + 1, INF)
    fila_actual = np.full(n + 1, INF)
    predecesor = [0] * ((k + 1) * ancho)
    fila_anterior[1] = 0.0

    def normas_escaladas(diferencias):
        # Una fila por candidato i'. Donde la escala es 0 la norma es 0 (se divide
        # por 1 para no generar nan) y donde es infinita se devuelve la escala.
        escala = np.abs(diferencias).max(axis=1)
        escala_segura = np.where(escala == 0.0, 1.0, escala)
        diferencias = diferencias / escala_segura[:, None]
        suma = np.zeros(len(escala))
        for c in range(d):
            suma += diferencias[:, c] * diferencias[:, c]
        with np.errstate(invalid="ignore"):
            return np.where(np.isfinite(escala), escala * np.sqrt(suma), escala)

    for t in range(2, k + 1):
        base_pred = t * ancho - t
        for i in range(t, n - (k - t) + 1):
            previo_min = 1 if t == 2 else t - 1
            # F[previo_min:i] son los f_{i'+1} para i' en [previo_min, i-1];
            # el ultimo termino da norma 0 (f_i - f_i), que es c(i-1, i) = 0.
            normas = normas_escaladas(F[previo_min:i] - F[i - 1])
            candidatos = fila_anterior[previo_min:i] + normas
            pos = int(np.argmin(candidatos))
            fila_actual[i] = candidatos[pos]
            predecesor[base_pred + i] = previo_min + pos
        fila_anterior, fila_actual = fila_actual, fila_anterior

    return _reconstruir(n, k, ancho, predecesor)


# ---------------------------------------------------------------------------
# Backtracking (replica de Backtracking::resolver y Backtracking::extender).
# ---------------------------------------------------------------------------

def backtracking(n, k, features, poda_factibilidad=True, poda_optimalidad=True):
    """Backtracking sobre selecciones parciales. Devuelve (seleccion, costo, nodos).

    Idea: recorrer el arbol de selecciones parciales. El estado es (ultimo pulso
    elegido, cantidad elegida t, costo parcial). Los hijos son las extensiones con
    un pulso j > ultimo en orden creciente, asi j = ultimo+1 (que cuesta 0) se
    explora primero y la cota se ajusta rapido. Una hoja es una seleccion con k
    pulsos; es solucion solo si termina en n.

    Podas (las mismas dos que en C++, apagables por separado):
      (a) factibilidad: no extender con un j desde el que no se puede llegar a n
          con exactamente k pulsos. Si faltan al menos dos pulsos (t+1 < k) hace
          falta j < n y n - j >= k - t - 1 (quedan suficientes pulsos despues de
          j); si j seria el ultimo (t+1 == k) tiene que ser j == n, y en ese caso
          se arranca directo en j = n en vez de recorrer y descartar los intermedios.
      (b) optimalidad: los costos son >= 0, asi que el costo parcial solo crece;
          si costo_parcial + c(ultimo, j) >= mejor_costo la rama no puede mejorar
          y se descarta. La cota inicial es la solucion de truncar (1, ..., k-1, n),
          cuyo costo es c(k-1, n).

    Decision de implementacion: en C++ la busqueda es recursiva con profundidad
    k. Aca se usa una pila explicita en vez de recursion porque Python tiene un
    limite de profundidad chico por defecto (1000) y, aun subiendolo con
    sys.setrecursionlimit, con k grande se agota la pila nativa del interprete y
    el proceso muere sin excepcion. Cada marco de la pila corresponde a una
    llamada a Backtracking::extender y guarda (ultimo, elegidos, costo_parcial,
    proximo j a probar), asi el orden de exploracion, los empates (gana la primera
    seleccion encontrada con costo estrictamente menor) y la cantidad de nodos
    visitados son exactamente los del C++.
    """
    # Cota inicial: truncar, conservar 1..k-1 y saltar a n. Siempre es valida (k <= n).
    mejor = list(range(1, k)) + [n]
    mejor_costo = costo(features, k - 1, n)

    parcial = [1]     # seleccion parcial en construccion (base 1); la raiz es {1}
    nodos = 0

    # "Visitar" un nodo es lo que hace extender al entrar: contarlo y, si es hoja,
    # evaluarla. Devuelve el marco a apilar (con su primer j), o None si es hoja.
    # Invariante: parcial tiene exactamente `elegidos` pulsos, el ultimo es
    # `ultimo` y `costo_parcial` es la suma de c entre sus consecutivos.
    def visitar(ultimo, elegidos, costo_parcial):
        nonlocal nodos, mejor, mejor_costo
        nodos += 1
        if elegidos == k:
            # Con la poda de factibilidad activa ultimo == n esta garantizado antes
            # de bajar; sin ella se chequea aca.
            if ultimo == n and costo_parcial < mejor_costo:
                mejor_costo = costo_parcial
                mejor = parcial[:]
            return None
        j_inicial = ultimo + 1
        if poda_factibilidad and elegidos + 1 == k:
            j_inicial = n
        return [ultimo, elegidos, costo_parcial, j_inicial]

    pila = [visitar(1, 1, 0.0)]
    while pila:
        marco = pila[-1]
        ultimo, elegidos, costo_parcial, j = marco
        if j > n:
            # Se agoto el ciclo de este nodo: es el return de extender.
            pila.pop()
            parcial.pop()
            continue
        marco[3] = j + 1

        if poda_factibilidad and elegidos + 1 < k:
            # Faltan al menos dos pulsos: j no puede ser n y tienen que quedar
            # k - elegidos - 1 pulsos despues de j. Si falla, es el break del C++.
            if j >= n or n - j < k - elegidos - 1:
                marco[3] = n + 1
                continue

        costo_salto = costo(features, ultimo, j)
        if poda_optimalidad and costo_parcial + costo_salto >= mejor_costo:
            continue

        parcial.append(j)
        hijo = visitar(j, elegidos + 1, costo_parcial + costo_salto)
        if hijo is None:
            parcial.pop()
        else:
            pila.append(hijo)

    return mejor, mejor_costo, nodos


# Nodos visitados en la ultima corrida de backtracking_cli, para que el CLI los
# informe igual que el binario (Backtracking::nodosVisitados).
ESTADISTICAS_BT = {"nodos": 0, "poda_factibilidad": True, "poda_optimalidad": True}


def backtracking_cli(n, k, features, sin_poda_factibilidad=False, sin_poda_optimalidad=False):
    """Adaptador para ALGORITMOS: recibe las opciones del CLI y devuelve solo la seleccion."""
    seleccion, _, nodos = backtracking(n, k, features,
                                       not sin_poda_factibilidad, not sin_poda_optimalidad)
    ESTADISTICAS_BT.update(nodos=nodos, poda_factibilidad=not sin_poda_factibilidad,
                           poda_optimalidad=not sin_poda_optimalidad)
    return seleccion


# ---------------------------------------------------------------------------
# CLI (misma interfaz que main.cpp).
# ---------------------------------------------------------------------------

# Nombre -> funcion(n, k, features, **opciones) que devuelve la seleccion (base 1).
# Las opciones sin_poda_factibilidad y sin_poda_optimalidad solo le llegan a "bt".
ALGORITMOS = {
    "pd": programacion_dinamica,
    "bt": backtracking_cli,
}


def registrar_csv(ruta, algoritmo, n, d, k, costo_total, ms):
    """Agrega una fila; escribe la cabecera si el archivo no existia (como registrarCsv).

    costo y ms van con 10 cifras significativas: es lo que produce el binario, donde
    el setprecision(10) queda pegado a los streams.
    """
    existe = os.path.exists(ruta)
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as csv:
        if not existe:
            csv.write("algoritmo,n,d,k,costo,ms\n")
        csv.write("{},{},{},{},{:.10g},{:.10g}\n".format(algoritmo, n, d, k, costo_total, ms))


def guardar_seleccion(ruta, seleccion):
    """Una sola linea con los indices separados por espacio; crea el directorio padre."""
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as salida:
        salida.write(" ".join(str(i) for i in seleccion) + "\n")


def resolver_instancia(ruta_entrada, algoritmo, ruta_csv, ruta_salida_pedida,
                       sin_poda_factibilidad=False, sin_poda_optimalidad=False):
    # Mismo orden que main.cpp: primero se carga la instancia, despues se elige el
    # algoritmo, asi los errores salen en el mismo orden que en el binario.
    n, d, k, features = leer_instancia(ruta_entrada)
    print("Instancia cargada: n={} pulsos, d={} características, k={} a conservar".format(n, d, k))

    if algoritmo not in ALGORITMOS:
        raise RuntimeError("Algoritmo desconocido o no implementado en Python: {}. "
                           "Disponibles: {}.".format(algoritmo, ", ".join(sorted(ALGORITMOS))))

    solver = ALGORITMOS[algoritmo]
    opciones = {}
    if algoritmo == "bt":
        opciones = dict(sin_poda_factibilidad=sin_poda_factibilidad,
                        sin_poda_optimalidad=sin_poda_optimalidad)
    elif sin_poda_factibilidad or sin_poda_optimalidad:
        print("Aviso: las opciones --sin-poda-* sólo aplican al algoritmo bt, se ignoran.")

    inicio = time.perf_counter()
    seleccion = solver(n, k, features, **opciones)
    fin = time.perf_counter()
    ms = (fin - inicio) * 1000.0

    costo_total = costo_seleccion(features, seleccion) if es_valida(n, k, seleccion) else math.inf
    print("Selección ({} pulsos): {}".format(len(seleccion), " ".join(str(i) for i in seleccion)))
    print("Costo: {:.10g}".format(costo_total))
    print("Tiempo: {:.10g} ms".format(ms))
    if algoritmo == "bt":
        print("Nodos visitados: {} (poda factibilidad: {}, poda optimalidad: {})".format(
            ESTADISTICAS_BT["nodos"], "si" if ESTADISTICAS_BT["poda_factibilidad"] else "no",
            "si" if ESTADISTICAS_BT["poda_optimalidad"] else "no"))

    # Una seleccion invalida no se guarda ni se registra: se corta con error (exit 1).
    if not es_valida(n, k, seleccion):
        raise RuntimeError("la selección devuelta por {} no es válida. Debe tener exactamente {} "
                           "pulsos, empezar en 1, terminar en {} y ser estrictamente creciente."
                           .format(algoritmo, k, n))

    etiqueta = "py-" + algoritmo
    ruta_salida = ruta_salida_pedida or os.path.join("output", "numericos",
                                                     "seleccion_{}.txt".format(etiqueta))
    guardar_seleccion(ruta_salida, seleccion)
    print("Resultado guardado en {}".format(ruta_salida))

    if ruta_csv:
        registrar_csv(ruta_csv, etiqueta, n, d, k, costo_total, ms)
        print("Medición agregada a {}".format(ruta_csv))


class _Parser(argparse.ArgumentParser):
    """ArgumentParser que falla como main.cpp: "Error: ..." en stderr y codigo 1 (no 2)."""

    def error(self, message):
        print("Error: {}".format(message), file=sys.stderr)
        self.print_usage(sys.stderr)
        sys.exit(1)


def parsear_argumentos(argv=None):
    # allow_abbrev=False: igual que main.cpp, un typo en --sin-poda-* corta con error
    # en vez de aceptarse como prefijo y correr en silencio con la poda activa.
    parser = _Parser(
        description="Algoritmos de radio edit en Python (misma interfaz que ./radioedit).",
        allow_abbrev=False)
    parser.add_argument("--instancia", required=True, help="archivo de entrada (formato n d k)")
    parser.add_argument("--algoritmo", default="pd", help="bt o pd (default pd)")
    parser.add_argument("--salida", default="", help="archivo con la seleccion (una linea)")
    parser.add_argument("--csv", default="", help="agrega una fila algoritmo,n,d,k,costo,ms")
    parser.add_argument("--sin-poda-factibilidad", action="store_true", help="solo bt")
    parser.add_argument("--sin-poda-optimalidad", action="store_true", help="solo bt")
    parser.add_argument("--ayuda", action="help", help="muestra esta ayuda (igual que --help)")
    return parser.parse_args(argv)


def main(argv=None):
    args = parsear_argumentos(argv)
    try:
        resolver_instancia(args.instancia, args.algoritmo, args.csv, args.salida,
                           args.sin_poda_factibilidad, args.sin_poda_optimalidad)
    except (OSError, ValueError, RuntimeError) as e:
        print("Error: {}".format(e), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
