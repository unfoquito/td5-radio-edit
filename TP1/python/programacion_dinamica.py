#!/usr/bin/env python3
"""Atajo para verificar.py: corre algoritmos.py con --algoritmo pd.

verificar.py invoca el solver py-pd como
  <python> programacion_dinamica.py --instancia X --salida Y
asi que este archivo solo fija el algoritmo y delega en algoritmos.main.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from algoritmos import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["--algoritmo", "pd"] + sys.argv[1:]))
