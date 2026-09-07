#include "Solucion.h"

#include "Instancia.h"

Solucion::Solucion() {}

void Solucion::agregar(int pulso) {
    (void)pulso;
}

void Solucion::limpiar() {}

const std::vector<int>& Solucion::indices() const {
    return _indices;
}

int Solucion::cantidad() const {
    return 0;
}

double Solucion::costo(const Instancia& instancia) const {
    (void)instancia;
    return 0.0;
}

bool Solucion::esValida(const Instancia& instancia) const {
    (void)instancia;
    return false;
}

void Solucion::imprimir(const Instancia& instancia) const {
    (void)instancia;
}

void Solucion::guardar(const std::string& ruta) const {
    (void)ruta;
}
