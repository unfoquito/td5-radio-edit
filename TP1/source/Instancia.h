#pragma once

#include <string>
#include <vector>

class Instancia {
public:
    Instancia();
    Instancia(const std::string& ruta);

    void cargar(const std::string& ruta);

    int n() const;
    int d() const;
    int k() const;

    const std::vector<double>& feature(int i) const;

    double costo(int i, int j) const;

private:
    int _n;
    int _d;
    int _k;

    std::vector<std::vector<double>> _features;
};
