#!/usr/bin/env bash
# Source this from bash/zsh before headless Ghidra use.
export JAVA_HOME="${JAVA_HOME:-$HOME/Applications/JDKs/temurin-25}"
export GHIDRA_HOME="${GHIDRA_HOME:-$HOME/Applications/ghidra_12.2_PUBLIC}"
export PATH="$JAVA_HOME/bin:$PATH"
if [[ ! -x "$GHIDRA_HOME/support/analyzeHeadless" ]]; then
  echo "Ghidra not found at GHIDRA_HOME=$GHIDRA_HOME" >&2
  return 1 2>/dev/null || exit 1
fi
