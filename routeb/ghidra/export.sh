#!/usr/bin/env bash
# Export one decompiled function from an ELF using Ghidra headless.
#
#   export.sh <elf> [function] [outdir]
#
# Requires Ghidra 12.x and JDK 25 on this Apple Silicon host. Set GHIDRA_HOME
# and JAVA_HOME if they are not the user-local defaults installed by
# scripts/install_ghidra_macos.sh.
set -euo pipefail

GHIDRA_HOME=${GHIDRA_HOME:-$HOME/Applications/ghidra_12.2_PUBLIC}
JAVA_HOME=${JAVA_HOME:-$HOME/Applications/JDKs/temurin-25}
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"
BIN=${1:?usage: export.sh <elf> [function] [outdir]}
FUNC=${2:-copy_name}
OUT=${3:-$(cd "$(dirname "$0")/.." && pwd)/out}

if [[ ! -x "$GHIDRA_HOME/support/analyzeHeadless" ]]; then
  echo "analyzeHeadless not found under GHIDRA_HOME=$GHIDRA_HOME" >&2
  exit 1
fi

if [[ ! -x "$JAVA_HOME/bin/java" ]]; then
  echo "java not found under JAVA_HOME=$JAVA_HOME (see scripts/install_ghidra_macos.sh)." >&2
  exit 1
fi
if [[ ! -x "$GHIDRA_HOME/ghidraRun" ]]; then
  echo "Ghidra not found under GHIDRA_HOME=$GHIDRA_HOME" >&2
  exit 1
fi

"$JAVA_HOME/bin/java" -version 2>&1 | head -1
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)

PROJ=$(mktemp -d "${TMPDIR:-/tmp}/br-ghidra.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT

"$GHIDRA_HOME/support/analyzeHeadless" "$PROJ" brproj \
  -import "$(cd "$(dirname "$BIN")" && pwd)/$(basename "$BIN")" \
  -overwrite \
  -scriptPath "$(cd "$(dirname "$0")" && pwd)" \
  -postScript ExportFunction.java "$FUNC" "$OUT/$FUNC.c" \
  -deleteProject

echo
echo "--- $OUT/$FUNC.c ---"
sed -n '1,120p' "$OUT/$FUNC.c"
