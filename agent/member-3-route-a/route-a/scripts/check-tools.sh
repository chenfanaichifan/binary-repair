#!/usr/bin/env bash
# check-tools.sh — list the binary-inspection tools available in the isolated
# Ubuntu environment and capture their versions.
#
# Usage:  ./scripts/check-tools.sh [output-file]
# Example: ./scripts/check-tools.sh reports/02-tool-inventory.txt

set -u

out_file="${1:-}"

TOOLS=(
  file
  readelf
  objdump
  objcopy
  nm
  strings
  gdb
  gcc
  make
  python3
  sha256sum
  checksec
  r2
)

emit() {
  printf '%s\n' "$*"
}

run() {
  if [ -n "$out_file" ]; then
    printf '%s\n' "$*" >> "$out_file"
  else
    printf '%s\n' "$*"
  fi
}

if [ -n "$out_file" ]; then
  : > "$out_file"
fi

run "# tool inventory — generated $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
run "# host: $(uname -srm)"
run ""

for t in "${TOOLS[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    path="$(command -v "$t")"
    ver="$("$t" --version 2>&1 | head -n 1)"
    [ -n "$ver" ] || ver="(version not reported)"
    run "[present] $t  $ver"
    run "          path: $path"
  else
    run "[missing] $t"
  fi
done

run ""
run "# python packages, if python3 is present"
if command -v python3 >/dev/null 2>&1; then
  while IFS= read -r line; do
    run "$line"
  done < <(python3 - <<'PY' 2>/dev/null || true
import importlib
for mod in ("capstone", "pwn", "elftools", "lief"):
    try:
        m = importlib.import_module(mod)
        print(f"[present] python:{mod}  {getattr(m, '__version__', 'version unknown')}")
    except Exception:
        print(f"[missing] python:{mod}")
PY
  )
else
  run "[missing] python3"
fi

if [ -n "$out_file" ]; then
  emit "wrote $out_file"
fi
