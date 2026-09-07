#include "Instancia.h"

Instancia::Instancia() : _n(0), _d(0), _k(0) {}

Instancia::Instancia(const std::string& ruta) : _n(0), _d(0), _k(0) {
    (void)ruta;
}

void Instancia::cargar(const std::string& ruta) {
    (void)ruta;
}

int Instancia::n() const {
    return 0;
}

int Instancia::d() const {
    return 0;
}

int Instancia::k() const {
    return 0;
}

const std::vector<double>& Instancia::feature(int i) const {
    (void)i;
    static const std::vector<double> vacio;
    return vacio;
}

double Instancia::costo(int i, int j) const {
    (void)i;
    (void)j;
    return 0.0;
}
