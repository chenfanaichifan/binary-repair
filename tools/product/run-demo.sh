#!/usr/bin/env bash
# tools/product/run-demo.sh
#
# One-command product demo: scan -> repair -> independent verify -> export.
#
# Usage:
#   tools/product/run-demo.sh --list
#   tools/product/run-demo.sh <fixture|all> [outdir]
#
# Properties:
#   * deterministic path only: no AI provider, no API key, no outbound network;
#   * the report never claims a repair unless the independent verifier agrees;
#   * refused/unsupported inputs produce no candidate bytes (fail closed).
#
# Exit codes: 0 demo completed and report written (any verdict), 1 internal
# error or false-verified claim, 2 usage error.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
ENTRY="$ROOT/scripts/product/demo_repair.py"
DEFAULT_OUT="artifacts/m3-product-2026-11-17/demo"

if [[ ! -f "$ENTRY" ]]; then
  echo "ERROR: missing product demo entry: $ENTRY" >&2
  exit 2
fi

if [[ "${1:-}" == "--list" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  if [[ ! -x "$PY" ]]; then
    echo "ERROR: python venv not found at $PY (run ./start-gui.sh first)" >&2
    exit 2
  fi
  exec "$PY" "$ENTRY" "$@"
fi

FIXTURE="${1:-}"
OUTDIR="${2:-$DEFAULT_OUT}"
if [[ -z "$FIXTURE" ]]; then
  echo "usage: tools/product/run-demo.sh <fixture|all> [outdir]" >&2
  echo "       tools/product/run-demo.sh --list" >&2
  exit 2
fi
if [[ ! -x "$PY" ]]; then
  echo "ERROR: python venv not found at $PY" >&2
  echo "       create it with ./start-gui.sh (the demo itself needs no network)" >&2
  exit 2
fi

# Resolve a relative outdir against the caller's directory, not the repo root.
if [[ "$OUTDIR" != /* ]]; then
  OUTDIR="$PWD/$OUTDIR"
fi

echo "run-demo: mode=deterministic (no AI, no API key, no network)"
echo "run-demo: fixture=$FIXTURE outdir=$OUTDIR"
cd "$ROOT"
if (( $# > 2 )); then
  exec "$PY" "$ENTRY" "$FIXTURE" --out "$OUTDIR" "${@:3}"
fi
exec "$PY" "$ENTRY" "$FIXTURE" --out "$OUTDIR"
