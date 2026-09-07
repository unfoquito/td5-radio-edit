#include "FuerzaBruta.h"

#include <limits>
#include <vector>

// Fuerza bruta honesta: enumera explícitamente TODOS los subconjuntos de k-2
// pulsos interiores tomados de {2, ..., n-1}, arma la selección completa
// (1, interiores, n), calcula su costo y se queda con la mejor. No hay podas ni
// memoización: cada una de las C(n-2, k-2) combinaciones se evalúa de punta a punta.
//
// La enumeración usa el esquema iterativo de "próxima combinación" en orden
// lexicográfico. Invariante del vector comb (posiciones 0..m-1, con m = k-2):
//   2 <= comb[0] < comb[1] < ... < comb[m-1] <= n-1,
// y comb[p] nunca supera (n-1) - (m-1-p), que es el mayor valor que le deja
// lugar a las m-1-p posiciones que vienen después. Para avanzar se busca la
// posición más a la derecha que todavía puede crecer, se incrementa y las que
// siguen se reinician al mínimo posible (consecutivas a partir de ella).
//
// Casos borde: k == 2 tiene m == 0 y la única selección es (1, n); k == n tiene
// m == n-2 y la única combinación es (2, ..., n-1). En ambos el ciclo corre una
// sola vez porque no hay posición que pueda crecer.
//
// Complejidad: C(n-2, k-2) combinaciones. Cada una cuesta O(k) por armar la
// selección y avanzar la combinación, más O(d) por cada par consecutivo de la
// selección que no sea un avance i -> i+1 (Instancia::costo devuelve 0 en O(1) en
// ese caso); esos pares son a lo sumo min(k-1, n-k). Total O(C(n-2, k-2) * k * d)
// como cota superior y O(k) de memoria extra. En la práctica, con d chico, el
// término que domina es el O(k) del armado y no las distancias.
Solucion FuerzaBruta::resolver(const Instancia& instancia) {
    int n = instancia.n();
    int k = instancia.k();
    int m = k - 2;  // cantidad de pulsos interiores a elegir

    // Primera combinación en orden lexicográfico: 2, 3, ..., m+1.
    std::vector<int> comb(m);
    for (int p = 0; p < m; p++) comb[p] = p + 2;

    Solucion mejor;
    double mejorCosto = std::numeric_limits<double>::infinity();

    // Se reutiliza la misma Solucion en todas las iteraciones para no pagar una
    // reserva de memoria nueva por combinación.
    Solucion actual;
    while (true) {
        // Armar la selección completa y evaluarla.
        actual.limpiar();
        actual.agregar(1);
        for (int p = 0; p < m; p++) actual.agregar(comb[p]);
        actual.agregar(n);

        // La primera combinación se guarda siempre, aunque su costo sea infinito
        // (pasa si una distancia desborda el double): así resolver nunca devuelve
        // una selección vacía. Después sólo se reemplaza con un costo estrictamente
        // menor, lo que deja la primera en orden lexicográfico ante empates.
        double costoActual = actual.costo(instancia);
        if (mejor.cantidad() == 0 || costoActual < mejorCosto) {
            mejorCosto = costoActual;
            mejor = actual;
        }

        // Próxima combinación: la posición más a la derecha que puede crecer.
        int p = m - 1;
        while (p >= 0 && comb[p] == (n - 1) - (m - 1 - p)) p--;
        if (p < 0) break;  // ya se recorrieron todas
        comb[p]++;
        for (int q = p + 1; q < m; q++) comb[q] = comb[q - 1] + 1;
    }

    return mejor;
}
