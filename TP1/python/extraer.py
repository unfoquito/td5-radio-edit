#!/usr/bin/env python3

import argparse
import os

def extraer(ruta_audio, sr_objetivo, caracteristicas):
    import librosa
    import numpy as np

    y, sr = librosa.load(ruta_audio, sr=sr_objetivo, mono=True)

    bpm, pulsos = librosa.beat.beat_track(y=y, sr=sr, units="frames")

    if caracteristicas == "chroma":
        matriz = librosa.feature.chroma_cqt(y=y, sr=sr)
    elif caracteristicas == "mfcc":
        matriz = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=12)
    else:
        matriz = np.vstack([
            librosa.feature.chroma_cqt(y=y, sr=sr),
            librosa.feature.mfcc(y=y, sr=sr, n_mfcc=12),
        ])

    sincronizada = librosa.util.sync(matriz, pulsos, aggregate=np.mean)

    tiempos = librosa.frames_to_time(pulsos, sr=sr)
    duracion = len(y) / sr

    fronteras = list(tiempos) + [duracion]

    features = sincronizada.T
    n = min(len(features), len(fronteras) - 1)

    # librosa 0.11 devuelve el tempo como arreglo de un elemento; se toma el escalar.
    bpm = float(np.atleast_1d(bpm)[0])

    return features[:n], fronteras[:n + 1], duracion, bpm

def main():
    parser = argparse.ArgumentParser(description="Convierte una grabacion en una instancia.")
    parser.add_argument("audio", help="grabacion de entrada (mp3, wav, flac, ...)")
    parser.add_argument("--salida", required=True,
                        help="prefijo de salida; genera <prefijo>.txt y <prefijo>_pulsos.txt")
    parser.add_argument("--k", type=int, default=None, help="cantidad de pulsos a conservar")
    parser.add_argument("--duracion", type=float, default=None,
                        help="duracion objetivo en segundos; alternativa a --k")
    parser.add_argument("--sr", type=int, default=22050, help="frecuencia de muestreo")
    parser.add_argument("--caracteristicas", choices=["chroma", "mfcc", "ambas"],
                        default="chroma", help="descriptor por pulso")
    args = parser.parse_args()

    features, fronteras, duracion, bpm = extraer(args.audio, args.sr, args.caracteristicas)

    n = len(features)
    d = len(features[0])

    if args.k is not None:
        k = args.k
    elif args.duracion is not None:
        k = max(2, min(n, round(n * args.duracion / duracion)))
    else:
        k = n // 2

    if not 2 <= k <= n:
        raise SystemExit(f"k debe estar entre 2 y {n}; se pidio {k}")

    directorio = os.path.dirname(args.salida)
    if directorio:
        os.makedirs(directorio, exist_ok=True)

    ruta_txt = args.salida + ".txt"
    ruta_beats = args.salida + "_pulsos.txt"

    with open(ruta_txt, "w") as f:
        f.write(f"{n} {d} {k}\n")
        for vector in features:
            f.write(" ".join(f"{v:.4f}" for v in vector) + "\n")

    with open(ruta_beats, "w") as f:
        for t in fronteras:
            f.write(f"{t:.6f}\n")

    print(f"Grabacion: {duracion:.1f} s, {bpm:.1f} BPM estimados")
    print(f"Instancia: n = {n} pulsos, d = {d}, k = {k}")
    print(f"Recorte objetivo: {duracion * k / n:.1f} s")
    print(f"Escritos {ruta_txt}, {ruta_beats}")

if __name__ == "__main__":
    main()
