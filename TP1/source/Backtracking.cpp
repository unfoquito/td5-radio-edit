#include "Backtracking.h"

#include <limits>

// Idea: recorrer el árbol de selecciones parciales. El estado es (último pulso
// elegido i, cantidad elegida t, costo parcial). Los hijos son las extensiones con
// un pulso j > i, en orden creciente, así j = i+1 (que cuesta 0) se explora primero
// y la cota se ajusta rápido. Una hoja es una selección con k pulsos; es solución
// sólo si termina en n.
//
// Podas:
//  (a) factibilidad: no extender con un j desde el que no se puede llegar a n con
//      exactamente k pulsos. Si todavía faltan al menos dos pulsos (t+1 < k) hace
//      falta j < n y n - j >= k - t - 1 (quedan suficientes pulsos después de j);
//      si j sería el último (t+1 == k) tiene que ser j == n.
//  (b) optimalidad: como todos los costos son >= 0, el costo parcial sólo puede
//      crecer, así que si costoParcial + c(i, j) >= mejorCosto la rama no puede
//      mejorar y se descarta. La cota inicial es la solución de truncar
//      (1, 2, ..., k-1, n), cuyo costo es c(k-1, n).
//
// Complejidad: sin podas cada iteración del ciclo recurre, así que el trabajo se
// amortiza en las aristas del árbol y el total es O(d * sum_{t<k} C(n-1, t)),
// que para k ~ n/2 es Theta(d * 2^n). Con la poda de factibilidad el ciclo nunca
// itera sin recurrir (los rangos se cortan con break o se salta directo a j = n),
// así que el tiempo sigue siendo O(d) por nodo visitado; con k fijo los nodos son
// O(n^{k-2}). Memoria O(k) por la selección parcial y la pila de recursión.

Backtracking::Backtracking()
    : _podaFactibilidad(true), _podaOptimalidad(true), _nodos(0),
      _mejorCosto(std::numeric_limits<double>::infinity()) {}

void Backtracking::usarPodaFactibilidad(bool activar) {
    _podaFactibilidad = activar;
}

void Backtracking::usarPodaOptimalidad(bool activar) {
    _podaOptimalidad = activar;
}

bool Backtracking::podaFactibilidadActiva() const {
    return _podaFactibilidad;
}

bool Backtracking::podaOptimalidadActiva() const {
    return _podaOptimalidad;
}

long long Backtracking::nodosVisitados() const {
    return _nodos;
}

Solucion Backtracking::resolver(const Instancia& instancia) {
    const int n = instancia.n();
    const int k = instancia.k();

    _nodos = 0;
    _parcial.clear();
    _parcial.reserve(static_cast<size_t>(k));

    // Cota inicial: truncar la grabación, conservar 1..k-1 y saltar a n.
    // Es siempre válida (k <= n) y da un mejor costo finito desde el arranque.
    _mejor.clear();
    for (int i = 1; i < k; i++) _mejor.push_back(i);
    _mejor.push_back(n);
    _mejorCosto = instancia.costo(k - 1, n);

    // La raíz es la selección parcial {1}: el primer pulso se conserva siempre.
    _parcial.push_back(1);
    extender(instancia, 1, 1, 0.0);

    Solucion solucion;
    for (int pulso : _mejor) solucion.agregar(pulso);
    return solucion;
}

// Invariante: _parcial tiene exactamente `elegidos` pulsos, el último es `ultimo`,
// y `costoParcial` es la suma de c entre sus consecutivos.
void Backtracking::extender(const Instancia& instancia, int ultimo, int elegidos, double costoParcial) {
    const int n = instancia.n();
    const int k = instancia.k();

    _nodos++;

    // Hoja: ya hay k pulsos. Es solución sólo si el último es n (con la poda de
    // factibilidad activa esto se garantiza antes de bajar; sin ella se chequea acá).
    if (elegidos == k) {
        if (ultimo == n && costoParcial < _mejorCosto) {
            _mejorCosto = costoParcial;
            _mejor = _parcial;
        }
        return;
    }

    // Si j sería el k-ésimo pulso tiene que ser n: con la poda de factibilidad se
    // arranca directo ahí en vez de recorrer (y descartar) todos los j intermedios,
    // que costaría O(n) por cada nodo de profundidad k-1 sin visitar nada nuevo.
    int jInicial = ultimo + 1;
    if (_podaFactibilidad && elegidos + 1 == k) jInicial = n;

    for (int j = jInicial; j <= n; j++) {
        if (_podaFactibilidad && elegidos + 1 < k) {
            // Faltan al menos dos pulsos: j no puede ser n y tienen que quedar
            // k - elegidos - 1 pulsos después de j para completar.
            if (j >= n || n - j < k - elegidos - 1) break;
        }

        double costoSalto = instancia.costo(ultimo, j);
        if (_podaOptimalidad && costoParcial + costoSalto >= _mejorCosto) continue;

        _parcial.push_back(j);
        extender(instancia, j, elegidos + 1, costoParcial + costoSalto);
        _parcial.pop_back();
    }
}
