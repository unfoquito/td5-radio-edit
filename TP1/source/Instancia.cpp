#include "Instancia.h"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>

// Convención de toda la interfaz pública: índices base 1.
// Internamente _features[i-1] guarda el vector f_i.

Instancia::Instancia() : _n(0), _d(0), _k(0) {}

Instancia::Instancia(const std::string& ruta) : _n(0), _d(0), _k(0) {
    cargar(ruta);
}

// Lee el archivo en el formato del enunciado: "n d k" y luego n líneas con d reales.
// Se lee por tokens (no por líneas) para tolerar espacios o saltos de línea extra,
// pero se valida que haya exactamente n*d valores numéricos: ni de menos ni de más.
// Antes de reservar memoria se chequea que la cabecera sea creíble (entra en int y
// el archivo tiene bytes suficientes para n*d valores), así una cabecera absurda
// falla con un mensaje claro en vez de agotar la memoria.
void Instancia::cargar(const std::string& ruta) {
    std::ifstream archivo(ruta);
    if (!archivo.is_open()) {
        throw std::runtime_error("No se pudo abrir la instancia: " + ruta);
    }

    long long n, d, k;
    if (!(archivo >> n >> d >> k)) {
        throw std::runtime_error("Instancia mal formada (" + ruta +
                                 "): la primera línea debe ser \"n d k\" con enteros.");
    }
    if (n < 2) {
        throw std::runtime_error("Instancia inválida (" + ruta + "): n debe ser >= 2, se leyó n=" +
                                 std::to_string(n) + ".");
    }
    if (d < 1) {
        throw std::runtime_error("Instancia inválida (" + ruta + "): d debe ser >= 1, se leyó d=" +
                                 std::to_string(d) + ".");
    }
    if (k < 2 || k > n) {
        throw std::runtime_error("Instancia inválida (" + ruta + "): k debe cumplir 2 <= k <= n, se leyó k=" +
                                 std::to_string(k) + " con n=" + std::to_string(n) + ".");
    }

    // Cotas de sanidad de la cabecera. Cada valor real ocupa al menos dos bytes
    // (un dígito y un separador), así que n*d no puede superar el tamaño del archivo.
    const long long maximoInt = std::numeric_limits<int>::max();
    if (n > maximoInt || d > maximoInt) {
        throw std::runtime_error("Instancia inválida (" + ruta + "): n y d deben entrar en un int, se leyó n=" +
                                 std::to_string(n) + ", d=" + std::to_string(d) + ".");
    }
    std::error_code ec;
    const auto bytes = std::filesystem::file_size(ruta, ec);
    if (!ec && static_cast<unsigned long long>(n) * static_cast<unsigned long long>(d) > bytes / 2) {
        throw std::runtime_error("Instancia mal formada (" + ruta + "): la cabecera declara n*d=" +
                                 std::to_string(n * d) + " valores pero el archivo tiene sólo " +
                                 std::to_string(bytes) + " bytes.");
    }

    // Se lee pulso a pulso (sin reservar los n de antemano) para que un archivo
    // truncado falle apenas se acaban los datos.
    std::vector<std::vector<double>> features;
    features.reserve(static_cast<size_t>(n));
    for (long long i = 0; i < n; i++) {
        std::vector<double> pulso(static_cast<size_t>(d));
        for (long long j = 0; j < d; j++) {
            double valor;
            if (!(archivo >> valor)) {
                std::string donde = "pulso " + std::to_string(i + 1) + ", componente " + std::to_string(j + 1);
                if (archivo.eof()) {
                    throw std::runtime_error("Instancia mal formada (" + ruta + "): se esperaban " +
                                             std::to_string(n * d) + " valores reales (n*d) y falta el " + donde + ".");
                }
                throw std::runtime_error("Instancia mal formada (" + ruta + "): valor no numérico en el " + donde + ".");
            }
            if (!std::isfinite(valor)) {
                throw std::runtime_error("Instancia mal formada (" + ruta + "): valor no finito en el pulso " +
                                         std::to_string(i + 1) + ".");
            }
            pulso[static_cast<size_t>(j)] = valor;
        }
        features.push_back(std::move(pulso));
    }

    // Si después de los n*d valores queda cualquier token, el archivo no describe la
    // instancia que dice la cabecera (por ejemplo, n declarado menor que las filas reales).
    std::string sobrante;
    if (archivo >> sobrante) {
        throw std::runtime_error("Instancia mal formada (" + ruta + "): hay datos de más después de los " +
                                 std::to_string(n * d) + " valores (n*d); el primero es \"" + sobrante + "\".");
    }

    // Recién acá se pisa el estado, así una carga fallida no deja la instancia a medias.
    _n = static_cast<int>(n);
    _d = static_cast<int>(d);
    _k = static_cast<int>(k);
    _features = std::move(features);
}

int Instancia::n() const {
    return _n;
}

int Instancia::d() const {
    return _d;
}

int Instancia::k() const {
    return _k;
}

const std::vector<double>& Instancia::feature(int i) const {
    if (i < 1 || i > _n) {
        throw std::out_of_range("Instancia::feature: índice " + std::to_string(i) +
                                " fuera de rango [1, " + std::to_string(_n) + "].");
    }
    return _features[static_cast<size_t>(i - 1)];
}

// c(i, j) = || f_{i+1} - f_j ||_2: después de reproducir el pulso i debería sonar
// el i+1, pero suena el j. Si j == i+1 el costo es 0 (no hay salto).
//
// La norma se calcula escalando por la mayor |diferencia| antes de elevar al
// cuadrado (la misma idea que std::hypot): así sólo desborda a infinito cuando la
// norma en sí no entra en un double, y no cuando una coordenada supera ~1e154.
double Instancia::costo(int i, int j) const {
    if (i < 1 || j > _n || i >= j) {
        throw std::out_of_range("Instancia::costo: se requiere 1 <= i < j <= n, se recibió i=" +
                                std::to_string(i) + ", j=" + std::to_string(j) + ".");
    }
    if (j == i + 1) return 0.0;

    const std::vector<double>& esperado = _features[static_cast<size_t>(i)];      // f_{i+1}
    const std::vector<double>& sonado = _features[static_cast<size_t>(j - 1)];    // f_j

    double escala = 0.0;
    for (int c = 0; c < _d; c++) {
        double diferencia = std::fabs(esperado[static_cast<size_t>(c)] - sonado[static_cast<size_t>(c)]);
        if (diferencia > escala) escala = diferencia;
    }
    if (escala == 0.0) return 0.0;
    // Si una sola resta ya desborda, la norma tampoco cabe en un double: se devuelve
    // infinito y los algoritmos lo tratan como un costo más (nunca como "inalcanzable").
    if (!std::isfinite(escala)) return escala;

    double suma = 0.0;
    for (int c = 0; c < _d; c++) {
        double diferencia = (esperado[static_cast<size_t>(c)] - sonado[static_cast<size_t>(c)]) / escala;
        suma += diferencia * diferencia;
    }
    return escala * std::sqrt(suma);
}
