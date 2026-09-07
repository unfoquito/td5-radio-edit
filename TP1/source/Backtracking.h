#pragma once

#include "Algoritmo.h"

class Backtracking : public Algoritmo {
public:
    Solucion resolver(const Instancia& instancia) override;
    std::string nombre() const override { return "bt"; }
};
