#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

#include "Backtracking.h"
#include "FuerzaBruta.h"
#include "Instancia.h"
#include "ProgramacionDinamica.h"
#include "Solucion.h"

std::unique_ptr<Algoritmo> crearAlgoritmo(const std::string& algoritmo) {
    if (algoritmo == "fb") return std::unique_ptr<Algoritmo>(new FuerzaBruta());
    if (algoritmo == "bt") return std::unique_ptr<Algoritmo>(new Backtracking());
    if (algoritmo == "pd") return std::unique_ptr<Algoritmo>(new ProgramacionDinamica());
    throw std::runtime_error("Algoritmo desconocido: " + algoritmo + ". Usar fb, bt o pd.");
}

void registrarCsv(const std::string& ruta, const std::string& algoritmo,
                  const Instancia& instancia, double costo, double ms) {
    bool existe = std::ifstream(ruta).good();

    std::ofstream csv(ruta, std::ios::app);
    if (!csv.is_open()) return;

    if (!existe) csv << "algoritmo,n,d,k,costo,ms\n";
    csv << algoritmo << "," << instancia.n() << "," << instancia.d() << ","
        << instancia.k() << "," << std::setprecision(10) << costo << "," << ms << "\n";
}

void resolverInstancia(const std::string& rutaEntrada, const std::string& algoritmo,
                       const std::string& rutaCsv, const std::string& rutaSalidaPedida) {
    Instancia instancia(rutaEntrada);
    std::cout << "Instancia cargada: n=" << instancia.n() << " pulsos, d=" << instancia.d()
              << " características, k=" << instancia.k() << " a conservar\n";

    std::unique_ptr<Algoritmo> solver = crearAlgoritmo(algoritmo);

    auto inicio = std::chrono::steady_clock::now();
    Solucion solucion = solver->resolver(instancia);
    auto fin = std::chrono::steady_clock::now();

    double ms = std::chrono::duration<double, std::milli>(fin - inicio).count();

    if (!solucion.esValida(instancia)) {
        std::cout << "Atención: la selección devuelta no es válida. Debe tener exactamente "
                  << instancia.k() << " pulsos, empezar en 1, terminar en " << instancia.n()
                  << " y ser estrictamente creciente.\n";
    }

    solucion.imprimir(instancia);
    std::cout << "Tiempo: " << ms << " ms\n";

    std::string rutaSalida = rutaSalidaPedida.empty()
                                 ? "output/numericos/seleccion_" + algoritmo + ".txt"
                                 : rutaSalidaPedida;
    solucion.guardar(rutaSalida);
    std::cout << "Resultado guardado en " << rutaSalida << "\n";

    if (!rutaCsv.empty()) {
        registrarCsv(rutaCsv, algoritmo, instancia, solucion.costo(instancia), ms);
        std::cout << "Medición agregada a " << rutaCsv << "\n";
    }
}

void imprimirUso() {
    std::cout << "Uso:\n"
              << "  ./radioedit --instancia <archivo> --algoritmo <fb|bt|pd>\n"
              << "               [--salida <archivo>] [--csv <archivo>]\n"
              << "\nEjemplos:\n"
              << "  ./radioedit --instancia input/ejemplo.txt --algoritmo pd\n"
              << "  ./radioedit --instancia input/ejemplo.txt --algoritmo bt --csv output/numericos/tiempos.csv\n";
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        imprimirUso();
        return 1;
    }

    std::string rutaArchivo, algoritmo = "pd", rutaCsv, rutaSalida;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--instancia" && i + 1 < argc) {
            rutaArchivo = argv[++i];
        } else if (arg == "--algoritmo" && i + 1 < argc) {
            algoritmo = argv[++i];
        } else if (arg == "--salida" && i + 1 < argc) {
            rutaSalida = argv[++i];
        } else if (arg == "--csv" && i + 1 < argc) {
            rutaCsv = argv[++i];
        } else if (arg == "--ayuda" || arg == "--help") {
            imprimirUso();
            return 0;
        }
    }

    if (rutaArchivo.empty()) {
        imprimirUso();
        return 1;
    }

    try {
        resolverInstancia(rutaArchivo, algoritmo, rutaCsv, rutaSalida);
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
