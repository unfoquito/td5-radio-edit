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
    if (!csv.is_open()) {
        throw std::runtime_error("no se pudo abrir el archivo CSV " + ruta);
    }

    if (!existe) csv << "algoritmo,n,d,k,costo,ms\n";
    csv << algoritmo << "," << instancia.n() << "," << instancia.d() << ","
        << instancia.k() << "," << std::setprecision(10) << costo << "," << ms << "\n";
}

// Los dos últimos parámetros sólo afectan al backtracking: apagan cada poda por
// separado para los experimentos.
void resolverInstancia(const std::string& rutaEntrada, const std::string& algoritmo,
                       const std::string& rutaCsv, const std::string& rutaSalidaPedida,
                       bool sinPodaFactibilidad = false, bool sinPodaOptimalidad = false) {
    Instancia instancia(rutaEntrada);
    std::cout << "Instancia cargada: n=" << instancia.n() << " pulsos, d=" << instancia.d()
              << " características, k=" << instancia.k() << " a conservar\n";

    std::unique_ptr<Algoritmo> solver = crearAlgoritmo(algoritmo);

    // Configuración de podas: sólo tiene sentido para bt, para el resto se ignora.
    Backtracking* bt = dynamic_cast<Backtracking*>(solver.get());
    if (bt != nullptr) {
        bt->usarPodaFactibilidad(!sinPodaFactibilidad);
        bt->usarPodaOptimalidad(!sinPodaOptimalidad);
    } else if (sinPodaFactibilidad || sinPodaOptimalidad) {
        std::cout << "Aviso: las opciones --sin-poda-* sólo aplican al algoritmo bt, se ignoran.\n";
    }

    auto inicio = std::chrono::steady_clock::now();
    Solucion solucion = solver->resolver(instancia);
    auto fin = std::chrono::steady_clock::now();

    double ms = std::chrono::duration<double, std::milli>(fin - inicio).count();

    solucion.imprimir(instancia);
    std::cout << "Tiempo: " << ms << " ms\n";
    if (bt != nullptr) {
        std::cout << "Nodos visitados: " << bt->nodosVisitados()
                  << " (poda factibilidad: " << (bt->podaFactibilidadActiva() ? "si" : "no")
                  << ", poda optimalidad: " << (bt->podaOptimalidadActiva() ? "si" : "no") << ")\n";
    }

    // Una selección inválida no se guarda ni se registra: se corta con error (exit 1)
    // para que un script que encadene el binario se entere por el código de salida.
    if (!solucion.esValida(instancia)) {
        throw std::runtime_error("la selección devuelta por " + algoritmo +
                                 " no es válida. Debe tener exactamente " + std::to_string(instancia.k()) +
                                 " pulsos, empezar en 1, terminar en " + std::to_string(instancia.n()) +
                                 " y ser estrictamente creciente.");
    }

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
              << "               [--sin-poda-factibilidad] [--sin-poda-optimalidad]  (sólo bt)\n"
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
    bool sinPodaFactibilidad = false, sinPodaOptimalidad = false;

    // Cualquier argumento que no se reconozca (o una opción sin su valor) corta con
    // error: un typo en --sin-poda-* no puede correr en silencio con la poda activa.
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        bool esperaValor = (arg == "--instancia" || arg == "--algoritmo" ||
                            arg == "--salida" || arg == "--csv");
        if (esperaValor && i + 1 >= argc) {
            std::cerr << "Error: la opción " << arg << " requiere un valor.\n";
            imprimirUso();
            return 1;
        }
        if (arg == "--instancia") {
            rutaArchivo = argv[++i];
        } else if (arg == "--algoritmo") {
            algoritmo = argv[++i];
        } else if (arg == "--salida") {
            rutaSalida = argv[++i];
        } else if (arg == "--csv") {
            rutaCsv = argv[++i];
        } else if (arg == "--sin-poda-factibilidad") {
            sinPodaFactibilidad = true;
        } else if (arg == "--sin-poda-optimalidad") {
            sinPodaOptimalidad = true;
        } else if (arg == "--ayuda" || arg == "--help") {
            imprimirUso();
            return 0;
        } else {
            std::cerr << "Error: argumento desconocido: " << arg << "\n";
            imprimirUso();
            return 1;
        }
    }

    if (rutaArchivo.empty()) {
        imprimirUso();
        return 1;
    }

    try {
        resolverInstancia(rutaArchivo, algoritmo, rutaCsv, rutaSalida,
                          sinPodaFactibilidad, sinPodaOptimalidad);
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 1;
    }

    return 0;
}
