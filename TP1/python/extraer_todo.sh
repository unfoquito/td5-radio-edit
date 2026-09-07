#!/usr/bin/env bash
# Genera las instancias reales a partir del audio de TP1/audio (ver audio/FUENTES.md).
# Cada grabación se recorta al 70 % de su duración. Los diálogos se extraen también con mfcc,
# porque el croma describe armonía y en la voz hablada tiene poco sentido.
set -e
cd "$(dirname "$0")/.."
PY=../.venv/bin/python
mkdir -p input/real
ext() { echo "== $1 ($3)"; $PY python/extraer.py "audio/$1" --salida "input/real/$2" --duracion "$4" --caracteristicas "$3"; }
dur() { ffprobe -v error -show_entries format=duration -of csv=p=0 "audio/$1"; }
for par in "macleod_action.mp3 action" "macleod_ascending_the_vale.mp3 ascending_the_vale" "macleod_batty_mcfaddin.mp3 batty_mcfaddin" \
           "hgf_escena_corta.mp3 hgf_corta" "hgf_escena_media.mp3 hgf_media" "hgf_escena_larga.mp3 hgf_larga" "suspense_tramo.mp3 suspense"; do
  set -- $par
  D=$(dur "$1"); T=$(python3 -c "print(round($D*0.7,2))")
  ext "$1" "$2" chroma "$T"
  case "$2" in hgf_*|suspense) ext "$1" "${2}_mfcc" mfcc "$T";; esac
done
echo "listo"; ls input/real
