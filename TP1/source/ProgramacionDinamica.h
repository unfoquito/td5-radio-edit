#pragma once

#include "Algoritmo.h"

class ProgramacionDinamica : public Algoritmo {
public:
    Solucion resolver(const Instancia& instancia) override;
    std::string nombre() const override { return "pd"; }
};
