#!/usr/bin/env python3

import argparse
import array
import os
import wave

def leer_seleccion(ruta):
    with open(ruta) as f:
        indices = [int(x) for x in f.read().split()]

    if not indices:
        raise SystemExit(
            f"La seleccion en {ruta} esta vacia.\n"
            "Probablemente el algoritmo todavia no esta implementado: "
            "completar source/ProgramacionDinamica.cpp y volver a correr `make`."
        )
    return indices

def leer_fronteras(ruta):
    with open(ruta) as f:
        return [float(linea) for linea in f if linea.strip()]

def tramos(indices):
    grupos = []
    inicio = anterior = indices[0]

    for pulso in indices[1:]:
        if pulso == anterior + 1:
            anterior = pulso
        else:
            grupos.append((inicio, anterior))
            inicio = anterior = pulso

    grupos.append((inicio, anterior))
    return grupos

def unir(bloques, nch, cuadros_fade):
    if not bloques:
        return array.array("h")

    salida = array.array("h", bloques[0])

    for bloque in bloques[1:]:
        fade = min(cuadros_fade, len(salida) // nch, len(bloque) // nch)

        if fade == 0:
            salida.extend(bloque)
            continue

        base = len(salida) - fade * nch
        for f in range(fade):
            peso = (f + 1) / (fade + 1)
            for c in range(nch):
                viejo = salida[base + f * nch + c]
                nuevo = bloque[f * nch + c]
                mezcla = int(viejo * (1.0 - peso) + nuevo * peso)
                salida[base + f * nch + c] = max(-32768, min(32767, mezcla))

        salida.extend(bloque[fade * nch:])

    return salida

def reconstruir_wav(ruta_audio, indices, fronteras, ruta_salida, ms_fade):
    with wave.open(ruta_audio, "rb") as f:
        nch = f.getnchannels()
        ancho = f.getsampwidth()
        sr = f.getframerate()
        total = f.getnframes()

        if ancho != 2:
            raise ValueError("Solo se admiten WAV PCM de 16 bits en el backend estandar")

        muestras = array.array("h", f.readframes(total))

    cuadros_fade = int(sr * ms_fade / 1000.0)

    bloques = []
    for primero, ultimo in tramos(indices):
        inicio = int(fronteras[primero - 1] * sr)
        fin = int(fronteras[ultimo] * sr)

        inicio = max(0, min(inicio, total))
        fin = max(inicio, min(fin, total))

        bloques.append(muestras[inicio * nch:fin * nch])

    salida = unir(bloques, nch, cuadros_fade)

    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
    with wave.open(ruta_salida, "wb") as f:
        f.setnchannels(nch)
        f.setsampwidth(2)
        f.setframerate(sr)
        f.writeframes(salida.tobytes())

    return len(salida) // nch / sr, total / sr

def reconstruir_comprimido(ruta_audio, indices, fronteras, ruta_salida, ms_fade):
    import librosa
    import numpy as np
    import soundfile as sf

    y, sr = librosa.load(ruta_audio, sr=None, mono=True)
    cuadros_fade = int(sr * ms_fade / 1000.0)

    salida = np.zeros(0, dtype=np.float32)

    for primero, ultimo in tramos(indices):
        inicio = max(0, min(int(fronteras[primero - 1] * sr), len(y)))
        fin = max(inicio, min(int(fronteras[ultimo] * sr), len(y)))
        bloque = y[inicio:fin]

        if len(salida) == 0:
            salida = bloque.copy()
            continue

        fade = min(cuadros_fade, len(salida), len(bloque))
        if fade == 0:
            salida = np.concatenate([salida, bloque])
            continue

        rampa = np.linspace(0.0, 1.0, fade, endpoint=False, dtype=np.float32)
        salida[-fade:] = salida[-fade:] * (1.0 - rampa) + bloque[:fade] * rampa
        salida = np.concatenate([salida, bloque[fade:]])

    os.makedirs(os.path.dirname(ruta_salida) or ".", exist_ok=True)
    sf.write(ruta_salida, salida, sr)

    return len(salida) / sr, len(y) / sr

def main():
    parser = argparse.ArgumentParser(description="Reconstruye el audio recortado.")
    parser.add_argument("audio", help="grabacion original (wav o mp3)")
    parser.add_argument("seleccion", help="archivo con la linea de pulsos conservados")
    parser.add_argument("--pulsos", required=True, help="archivo con las n+1 fronteras de pulsos")
    parser.add_argument("--salida", required=True, help="archivo de audio a generar")
    parser.add_argument("--crossfade", type=float, default=15.0,
                        help="duracion del crossfade en milisegundos")
    args = parser.parse_args()

    indices = leer_seleccion(args.seleccion)
    fronteras = leer_fronteras(args.pulsos)

    if indices[-1] >= len(fronteras):
        raise ValueError("La seleccion referencia pulsos que no estan en el archivo de fronteras")

    es_wav = args.audio.lower().endswith(".wav")
    backend = reconstruir_wav if es_wav else reconstruir_comprimido

    duracion, original = backend(args.audio, indices, fronteras, args.salida, args.crossfade)

    cortes = len(tramos(indices)) - 1
    print(f"Pulsos conservados: {len(indices)} de {len(fronteras) - 1}")
    print(f"Saltos: {cortes}")
    print(f"Duracion: {original:.2f} s -> {duracion:.2f} s ({duracion / original:.1%})")
    print(f"Escrito {args.salida}")

if __name__ == "__main__":
    main()
