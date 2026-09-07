#include "ProgramacionDinamica.h"

#include <limits>
#include <utility>
#include <vector>

// Programación dinámica bottom-up sobre la recurrencia
//   M[t][i] = mínimo costo de una selección de t pulsos que empieza en 1 y termina en i
//   M[1][1] = 0, M[1][i] = infinito para i > 1
//   M[t][i] = min_{t-1 <= i' < i} ( M[t-1][i'] + c(i', i) )
// La respuesta es M[k][n]. Como en la fila t sólo importa la fila t-1, se guardan
// dos filas de M (anterior y actual) y una tabla de predecesores para reconstruir
// la selección al final.
//
// Poda de estados: en la fila t sólo son alcanzables los i con t <= i <= n - (k - t):
// se necesitan al menos t-1 pulsos antes de i (uno por fila previa) y al menos k-t
// pulsos después de i para completar los k. Y todos esos i son alcanzables de verdad
// (1, 2, ..., t-1, i es una selección parcial válida), así que cada estado del rango
// tiene un predecesor. La fila 1 es la excepción: su único estado es i = 1.
//
// Los predecesores se guardan desplazados, predecesor[t][i - t], con ancho n-k+1
// (la cantidad de estados útiles por fila), así el espacio es Theta(k (n-k+1)) en
// vez de Theta(k n); para k cercano a n queda lineal.
//
// Costo infinito vs. inalcanzable: Instancia::costo puede devolver infinito si la
// distancia no cabe en un double. Por eso el predecesor se fija con el primer i'
// candidato y recién después se compara con "<": un estado alcanzable siempre queda
// con predecesor válido aunque su costo sea infinito, y la reconstrucción nunca
// sigue el centinela 0.
//
// El costo c(i', i) se calcula al vuelo con instancia.costo (O(d) por par). Como d es
// chico (12 en la práctica), precalcular una matriz O(n^2) de costos no cambia el orden
// de magnitud del tiempo pero sí llevaría el espacio a O(n^2).
//
// Complejidad: la fila 2 cuesta O(n d) (un único i' = 1) y cada fila t >= 3 recorre
// O((n-k+1)^2) pares (i', i) con O(d) cada uno, así que el tiempo total es
// O(n d + (k-2) (n-k+1)^2 d): para k = 2 es O(n d) y para k = n es O(n d) también.
// Espacio Theta(k (n-k+1)) por los predecesores más O(n) por las dos filas.
//
// Empates: en cada estado se toma el primer i' que alcanza el mínimo, o sea el
// predecesor más chico. Eso fija una solución óptima determinista (la mínima
// comparando desde el último índice hacia atrás), que no es necesariamente la
// lexicográficamente menor leída de izquierda a derecha.
Solucion ProgramacionDinamica::resolver(const Instancia& instancia) {
    const int n = instancia.n();
    const int k = instancia.k();
    const double INF = std::numeric_limits<double>::infinity();

    // Estados útiles por fila: i - t va de 0 a n - k.
    const int ancho = n - k + 1;

    // filaAnterior[i] = M[t-1][i], filaActual[i] = M[t][i], con i en base 1.
    // No hace falta reinicializar filaActual entre filas: la fila t+1 sólo lee las
    // posiciones [t, n-k+t], que son exactamente las que escribió la fila t.
    std::vector<double> filaAnterior(static_cast<size_t>(n) + 1, INF);
    std::vector<double> filaActual(static_cast<size_t>(n) + 1, INF);

    // predecesor[t][i - t] = i' que realiza el mínimo de M[t][i], para 2 <= t <= k.
    std::vector<std::vector<int>> predecesor(static_cast<size_t>(k) + 1,
                                             std::vector<int>(static_cast<size_t>(ancho), 0));

    // Caso base: con un solo pulso, sólo se puede estar parado en el 1 con costo 0.
    filaAnterior[1] = 0.0;

    for (int t = 2; t <= k; t++) {
        // Rango útil de i en la fila t (ver invariante de arriba).
        const int iMin = t;
        const int iMax = n - (k - t);

        for (int i = iMin; i <= iMax; i++) {
            // i' recorre los estados alcanzables de la fila t-1 que están antes de i.
            // Para t >= 3 son todos los de [t-1, i-1] (i-1 <= n-(k-(t-1)), así que
            // el rango cae dentro de lo computado en la fila anterior). Para t = 2
            // el único estado de la fila 1 es i' = 1.
            const int previoMin = (t == 2) ? 1 : t - 1;
            const int previoMax = (t == 2) ? 1 : i - 1;

            double mejor = INF;
            int mejorPrevio = 0;
            for (int previo = previoMin; previo <= previoMax; previo++) {
                double candidato = filaAnterior[static_cast<size_t>(previo)] + instancia.costo(previo, i);
                if (mejorPrevio == 0 || candidato < mejor) {
                    mejor = candidato;
                    mejorPrevio = previo;
                }
            }

            filaActual[static_cast<size_t>(i)] = mejor;
            predecesor[static_cast<size_t>(t)][static_cast<size_t>(i - t)] = mejorPrevio;
        }

        std::swap(filaAnterior, filaActual);
    }

    // Reconstrucción: desde (k, n) se sigue la cadena de predecesores hasta (1, 1)
    // y se invierte para dejar los índices en orden creciente.
    std::vector<int> seleccion;
    seleccion.reserve(static_cast<size_t>(k));
    int actual = n;
    for (int t = k; t >= 1; t--) {
        seleccion.push_back(actual);
        if (t > 1) actual = predecesor[static_cast<size_t>(t)][static_cast<size_t>(actual - t)];
    }

    Solucion solucion;
    for (auto it = seleccion.rbegin(); it != seleccion.rend(); ++it) {
        solucion.agregar(*it);
    }
    return solucion;
}
