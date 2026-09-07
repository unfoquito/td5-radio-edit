#pragma once

#include <string>
#include <vector>

class Instancia;

class Solucion {
public:
    Solucion();

    void agregar(int pulso);

    void limpiar();

    const std::vector<int>& indices() const;
    int cantidad() const;

    double costo(const Instancia& instancia) const;

    bool esValida(const Instancia& instancia) const;

    void imprimir(const Instancia& instancia) const;

    void guardar(const std::string& ruta) const;

private:
    std::vector<int> _indices;
};
