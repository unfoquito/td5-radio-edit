#pragma once

#include <string>

#include "Instancia.h"
#include "Solucion.h"

class Algoritmo {
public:
    virtual ~Algoritmo() {}

    virtual Solucion resolver(const Instancia& instancia) = 0;

    virtual std::string nombre() const = 0;
};
