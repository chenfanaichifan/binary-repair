#!/bin/sh
# Build a small CGC cb-multios subset on macOS arm64.
# Requires a full clone and CMake >= 3.5 policy override.
set -eu
ROOT="${1:-$HOME/cb-multios}"
TARGETS="${CGC_TARGETS:-3D_Image_Toolkit Palindrome basic_messaging CGC_Hangman_Game Board_Game}"
cd "$ROOT"
if [ ! -f include/maths_compat.c ]; then
  cp "$(dirname "$0")/cgc/maths_compat.c" include/maths_compat.c
fi
python3 - <<'PY'
from pathlib import Path
p=Path('include/CMakeLists.txt'); s=p.read_text()
if 'maths_compat.c' not in s:
    s=s.replace('set(cgc_src libcgc.c maths.S)', 'if(APPLE AND CMAKE_SYSTEM_PROCESSOR MATCHES "arm64")\n  set(cgc_src libcgc.c maths_compat.c)\nelse()\n  set(cgc_src libcgc.c maths.S)\nendif()')
    p.write_text(s)
PY
CMAKE_OPTS="-DCMAKE_POLICY_VERSION_MINIMUM=3.5" BUILD64=1 \
  NO_PYTHON_I_KNOW_WHAT_I_AM_DOING_I_SWEAR=1 ./build.sh
cd build64
for t in $TARGETS; do
  cmake --build . --target "$t" "${t}_patched" -j4
done
