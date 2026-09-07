#include "Solucion.h"

#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>

#include "Instancia.h"

// Una Solucion es la lista de pulsos conservados, en base 1 y en el orden en que
// se agregaron. No se valida al agregar (los algoritmos la van construyendo de a
// pasos); la validez se chequea con esValida.

Solucion::Solucion() {}

void Solucion::agregar(int pulso) {
    _indices.push_back(pulso);
}

void Solucion::limpiar() {
    _indices.clear();
}

const std::vector<int>& Solucion::indices() const {
    return _indices;
}

int Solucion::cantidad() const {
    return static_cast<int>(_indices.size());
}

// Suma c(i_t, i_{t+1}) entre pulsos consecutivos de la selección. Si algún par no
// cumple 1 <= i < j <= n el costo no está definido y se devuelve infinito, para que
// una selección rota nunca parezca mejor que una válida.
double Solucion::costo(const Instancia& instancia) const {
    double total = 0.0;
    for (size_t t = 0; t + 1 < _indices.size(); t++) {
        int i = _indices[t];
        int j = _indices[t + 1];
        if (i < 1 || j > instancia.n() || i >= j) {
            return std::numeric_limits<double>::infinity();
        }
        total += instancia.costo(i, j);
    }
    return total;
}

// Válida si tiene exactamente k pulsos, empieza en 1, termina en n y es
// estrictamente creciente (con eso también quedan todos en rango).
bool Solucion::esValida(const Instancia& instancia) const {
    if (cantidad() != instancia.k()) return false;
    if (_indices.front() != 1) return false;
    if (_indices.back() != instancia.n()) return false;
    for (size_t t = 0; t + 1 < _indices.size(); t++) {
        if (_indices[t] >= _indices[t + 1]) return false;
    }
    return true;
}

void Solucion::imprimir(const Instancia& instancia) const {
    std::cout << "Selección (" << cantidad() << " pulsos):";
    for (int pulso : _indices) std::cout << " " << pulso;
    std::cout << "\n";
    std::cout << "Costo: " << std::setprecision(10) << costo(instancia) << "\n";
}

// Escribe una sola línea con los índices separados por espacio. Crea el directorio
// padre si no existe, así el usuario puede pasar cualquier --salida.
void Solucion::guardar(const std::string& ruta) const {
    std::filesystem::path camino(ruta);
    if (camino.has_parent_path()) {
        std::filesystem::create_directories(camino.parent_path());
    }

    std::ofstream salida(ruta);
    if (!salida.is_open()) {
        throw std::runtime_error("No se pudo escribir la salida en " + ruta);
    }
    for (size_t t = 0; t < _indices.size(); t++) {
        if (t > 0) salida << " ";
        salida << _indices[t];
    }
    salida << "\n";
}
