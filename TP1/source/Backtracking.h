#pragma once

#include <vector>

#include "Algoritmo.h"

// Backtracking sobre selecciones parciales. Cada nodo del árbol de búsqueda es una
// selección parcial 1 = i_1 < ... < i_t y se extiende con el próximo pulso j > i_t.
// Tiene dos podas independientes (factibilidad y optimalidad) que se pueden apagar
// por separado para los experimentos, y un contador de nodos visitados.
// La búsqueda es recursiva con profundidad k (una llamada por pulso elegido), así
// que está pensada para los n del enunciado (cientos o miles); con k del orden de
// 10^5 se agota la pila del hilo principal. Para esos tamaños corresponde pd.
class Backtracking : public Algoritmo {
public:
    Backtracking();

    Solucion resolver(const Instancia& instancia) override;
    std::string nombre() const override { return "bt"; }

    // Activan o desactivan cada poda. Por defecto las dos están activas.
    void usarPodaFactibilidad(bool activar);
    void usarPodaOptimalidad(bool activar);
    bool podaFactibilidadActiva() const;
    bool podaOptimalidadActiva() const;

    // Cantidad de nodos (selecciones parciales) visitados en la última corrida.
    long long nodosVisitados() const;

private:
    void extender(const Instancia& instancia, int ultimo, int elegidos, double costoParcial);

    bool _podaFactibilidad;
    bool _podaOptimalidad;
    long long _nodos;

    // Estado de la búsqueda en curso: la selección parcial (base 1) y la mejor
    // solución completa encontrada hasta el momento con su costo.
    std::vector<int> _parcial;
    std::vector<int> _mejor;
    double _mejorCosto;
};
