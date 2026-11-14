#!/usr/bin/env bash
# User-local Ghidra + JDK 25 installer for Apple Silicon macOS (no sudo).
# The official Ghidra 12.x zip omits macOS native decompiler binaries, so this
# script also builds them from the shipped Gradle project.
set -euo pipefail

GHIDRA_VERSION="${GHIDRA_VERSION:-12.2}"
GHIDRA_ZIP_URL="${GHIDRA_ZIP_URL:-https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.2_build/ghidra_12.2_PUBLIC_20261016.zip}"
GHIDRA_HOME="${GHIDRA_HOME:-$HOME/Applications/ghidra_${GHIDRA_VERSION}_PUBLIC}"
JDK_HOME="${JDK_HOME:-$HOME/Applications/JDKs/temurin-25}"
JDK_URL="${JDK_URL:-https://api.adoptium.net/v3/binary/latest/25/ga/mac/aarch64/jdk/hotspot/normal/eclipse?project=jdk}"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This installer targets Apple Silicon macOS (Darwin/arm64)." >&2
  exit 2
fi
mkdir -p "$HOME/Applications/JDKs"

if [[ ! -x "$JDK_HOME/bin/java" ]]; then
  echo "[1/4] downloading Temurin 25 to $JDK_HOME"
  tmp=$(mktemp)
  curl -fL --retry 3 --connect-timeout 20 -o "$tmp" "$JDK_URL"
  rm -rf "$JDK_HOME"; mkdir -p "$JDK_HOME"
  tar xzf "$tmp" -C "$JDK_HOME" --strip-components=1
  rm -f "$tmp"
else
  echo "[1/4] JDK already present: $JDK_HOME"
fi

if [[ ! -x "$GHIDRA_HOME/support/analyzeHeadless" ]]; then
  echo "[2/4] downloading Ghidra $GHIDRA_VERSION"
  tmp=$(mktemp)
  curl -fL --retry 3 --connect-timeout 20 -o "$tmp" "$GHIDRA_ZIP_URL"
  rm -rf "$GHIDRA_HOME"; mkdir -p "$(dirname "$GHIDRA_HOME")"
  unzip -q "$tmp" -d "$(dirname "$GHIDRA_HOME")"
  rm -f "$tmp"
else
  echo "[2/4] Ghidra already present: $GHIDRA_HOME"
fi

export JAVA_HOME="$JDK_HOME"
export PATH="$JAVA_HOME/bin:$PATH"
echo "[3/4] JDK: $("$JAVA_HOME/bin/java" -version 2>&1 | head -1)"
if [[ ! -x "$GHIDRA_HOME/Ghidra/Features/Decompiler/build/os/mac_arm_64/decompile" ]]; then
  echo "[4/4] building macOS arm64 native components (one-time)"
  (cd "$GHIDRA_HOME/support/gradle" && ./gradlew buildNatives)
else
  echo "[4/4] native decompiler already built"
fi

cat <<EOF

Installed:
  JDK_HOME=$JDK_HOME
  GHIDRA_HOME=$GHIDRA_HOME

Use:
  export JAVA_HOME="$JDK_HOME"
  export PATH="\$JAVA_HOME/bin:\$PATH"
  export GHIDRA_HOME="$GHIDRA_HOME"
  "$GHIDRA_HOME/ghidraRun"                  # GUI
  bash routeb/ghidra/export.sh <elf> <func> <outdir>   # headless decompile
EOF
