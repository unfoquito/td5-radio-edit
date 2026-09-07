#!/usr/bin/env bash
# Descarga el audio usado en la experimentación. Los archivos no se versionan.
# Fuentes y licencias en FUENTES.md.
set -e
cd "$(dirname "$0")"
bajar() { [ -f "$2" ] && { echo "ya existe $2"; return; }; echo "bajando $2"; curl -L --fail --retry 3 -o "$2" "$1"; }
INC="https://archive.org/download/Incompetech/mp3-royaltyfree"
bajar "$INC/Action.mp3" macleod_action.mp3
bajar "$INC/Ascending%20the%20Vale.mp3" macleod_ascending_the_vale.mp3
bajar "$INC/Batty%20McFaddin.mp3" macleod_batty_mcfaddin.mp3
bajar "https://archive.org/download/his_girl_friday/his_girl_friday.mp3" his_girl_friday.mp3
bajar "https://archive.org/download/OTRR_Suspense_Singles/Suspense%20420902%20011%20The%20Hitch-Hiker%20(128-44)%2028018%2029m32s.mp3" suspense_the_hitch_hiker.mp3
echo "listo"
