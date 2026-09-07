CXX      = g++
CXXFLAGS = -std=c++17 -O2 -Wall -Wextra
SRCDIR   = source
OUTDIR   = output

SOURCES  = $(SRCDIR)/main.cpp \
           $(SRCDIR)/Instancia.cpp \
           $(SRCDIR)/Solucion.cpp \
           $(SRCDIR)/FuerzaBruta.cpp \
           $(SRCDIR)/Backtracking.cpp \
           $(SRCDIR)/ProgramacionDinamica.cpp

TARGET = radioedit

# ─── Targets principales ──────────────────────────────────────────────────────

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CXX) $(CXXFLAGS) -o $@ $^

# ─── Ejecución ────────────────────────────────────────────────────────────────

run-ejemplo: $(TARGET)
	./$(TARGET) --instancia input/ejemplo.txt --algoritmo pd

# ─── Limpieza ─────────────────────────────────────────────────────────────────

clean:
	rm -f $(TARGET)

clean-output:
	find $(OUTDIR) -type f ! -name '.gitkeep' -delete

# Windows (MinGW): usar `mingw32-make` en lugar de `make`.

.PHONY: all run-ejemplo clean clean-output
