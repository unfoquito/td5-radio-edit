#pragma once

#include "Algoritmo.h"

class FuerzaBruta : public Algoritmo {
public:
    Solucion resolver(const Instancia& instancia) override;
    std::string nombre() const override { return "fb"; }
};
