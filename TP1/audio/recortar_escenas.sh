#!/usr/bin/env bash
# Corta escenas de diálogo de las grabaciones largas para armar instancias de tamaño manejable.
# Los cortes se hacen sin recodificar (copia del stream mp3).
set -e
cd "$(dirname "$0")"
cortar() { [ -f "$4" ] && { echo "ya existe $4"; return; }; ffmpeg -v error -y -ss "$2" -t "$3" -i "$1" -c copy "$4"; echo "escrito $4"; }
# His Girl Friday (1940): tres escenas de largo distinto
cortar his_girl_friday.mp3 00:04:30 00:01:30 hgf_escena_corta.mp3
cortar his_girl_friday.mp3 00:40:00 00:03:20 hgf_escena_media.mp3
cortar his_girl_friday.mp3 01:10:00 00:06:00 hgf_escena_larga.mp3
# Suspense, The Hitch-Hiker (1942): un tramo central de la radionovela
cortar suspense_the_hitch_hiker.mp3 00:06:00 00:04:00 suspense_tramo.mp3
echo "listo"
