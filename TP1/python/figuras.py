#!/usr/bin/env python3
"""Paleta y helpers de matplotlib compartidos por las figuras de experimentos.py.

Todas las figuras del informe salen de aca para que tengan el mismo estilo:
ancho de media pagina A4 (6 pulgadas), fuente legible, sin titulo adentro (el
caption va en LaTeX), leyenda sin marco y PNG a 200 dpi en informe/figuras/.
"""

import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
DIR_FIGURAS = os.path.join(os.path.dirname(os.path.dirname(AQUI)), "informe", "figuras")

# Paleta sobria, una entrada por serie que aparece en el informe.
PALETA = {
    "fb": "#b03a2e",           # fuerza bruta: rojo ladrillo
    "bt": "#2e5c8a",           # backtracking: azul
    "pd": "#2a7f4f",           # programacion dinamica: verde
    "py-bt": "#7fa6c9",        # las versiones Python, mas claras
    "py-pd": "#7fbf9a",
    "ninguna": "#7f7f7f",      # configuraciones de podas de BT
    "factibilidad": "#d98c2b",
    "optimalidad": "#7b5ea7",
    "ambas": "#2e5c8a",
    "optimo": "#2a7f4f",       # baselines de E5
    "truncar": "#7f7f7f",
    "uniforme": "#d98c2b",
    "estructura": "#2a7f4f",   # familias sinteticas (uniforme comparte el naranja)
    "adversarial": "#7b5ea7",
    "croma": "#2e5c8a",
    "mfcc": "#d98c2b",
    "modelo": "#333333",       # curva teorica
    "acento": "#b03a2e",
}

ETIQUETAS = {
    "fb": "Fuerza bruta",
    "bt": "Backtracking",
    "pd": "Programación dinámica",
    "py-bt": "Backtracking (Python)",
    "py-pd": "Programación dinámica (Python)",
    "ninguna": "Sin podas",
    "factibilidad": "Solo factibilidad",
    "optimalidad": "Solo optimalidad",
    "ambas": "Ambas podas",
    "optimo": "Óptimo (PD)",
    "truncar": "Truncar",
    "uniforme": "Muestreo uniforme",
    "croma": "Croma",
    "mfcc": "MFCC",
}

MARCADORES = {"fb": "o", "bt": "s", "pd": "^", "py-bt": "s", "py-pd": "^",
              "ninguna": "o", "factibilidad": "s", "optimalidad": "D", "ambas": "^",
              "uniforme": "o", "estructura": "s", "adversarial": "^"}

# Marcador por regimen de k, para distinguir series del mismo algoritmo.
MARCADORES_REGIMEN = {"n/4": "o", "n/2": "s", "3n/4": "^"}

FAMILIAS_TITULO = {"uniforme": "Uniforme", "estructura": "Con estructura",
                   "adversarial": "Adversarial"}

# Series sin semantica propia (por ejemplo una escena por linea) y tres niveles de
# opacidad para distinguir k = 50, 70 y 90 % de n con un mismo color.
SERIE_NEUTRA = ["#2e5c8a", "#d98c2b", "#2a7f4f", "#7b5ea7"]
ALFAS_TRES = [0.45, 0.72, 1.0]

plt.rcParams.update({
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "lines.linewidth": 1.4,
    "lines.markersize": 4,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linewidth": 0.5,
    "legend.frameon": False,
    "savefig.dpi": 200,
    "figure.constrained_layout.use": True,
})


def figura(paneles=1, ancho=6.0, alto=None, compartir_y=True):
    """Crea una figura de media pagina con `paneles` ejes en fila."""
    if alto is None:
        alto = 3.3 if paneles == 1 else 2.6
    fig, ejes = plt.subplots(1, paneles, figsize=(ancho, alto), sharey=compartir_y, squeeze=False)
    return fig, list(ejes[0])


def guardar(fig, nombre):
    """Guarda en informe/figuras/<nombre>.png y cierra la figura."""
    os.makedirs(DIR_FIGURAS, exist_ok=True)
    ruta = os.path.join(DIR_FIGURAS, nombre + ".png")
    fig.savefig(ruta)
    plt.close(fig)
    print("  figura: " + os.path.relpath(ruta))
    return ruta


def serie(ax, x, y, clave, etiqueta=None, estilo="-", **extra):
    """Dibuja una serie con el color y marcador de la paleta."""
    ax.plot(x, y, estilo, color=PALETA[clave], marker=MARCADORES.get(clave, "o"),
            label=etiqueta if etiqueta is not None else ETIQUETAS.get(clave, clave), **extra)


def leyenda(ax, **extra):
    manejadores, etiquetas = ax.get_legend_handles_labels()
    if manejadores:
        ax.legend(**extra)


def leyenda_abajo(fig, ax, columnas=None):
    """Leyenda unica debajo de los paneles, con las series del eje dado.
    Evita tapar las curvas cuando el rango de los datos ocupa todo el panel."""
    manejadores, etiquetas = ax.get_legend_handles_labels()
    if manejadores:
        fig.legend(manejadores, etiquetas, loc="outside lower center",
                   ncol=columnas or len(manejadores))


def eje_x_log(ax, valores):
    """Eje x logaritmico con los ticks en los valores medidos y sin etiquetas menores.
    Con menos de dos decadas matplotlib etiqueta tambien los ticks menores (2x10^1,
    3x10^1, ...) y las etiquetas se pisan."""
    import math
    from matplotlib.ticker import FixedLocator, NullFormatter, ScalarFormatter
    ax.set_xscale("log")
    # Si dos valores quedan a menos de 0,12 decadas (800 y 1000 se pisan) se
    # conserva el mayor, asi el extremo del rango siempre lleva etiqueta.
    ticks = []
    for v in sorted(set(valores)):
        if ticks and math.log10(v) - math.log10(ticks[-1]) < 0.12:
            ticks[-1] = v
        else:
            ticks.append(v)
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    formateador = ScalarFormatter()
    formateador.set_scientific(False)
    ax.xaxis.set_major_formatter(formateador)
    ax.xaxis.set_minor_formatter(NullFormatter())
