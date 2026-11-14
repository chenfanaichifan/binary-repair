#!/usr/bin/env bash
# Reproduce the hard-case matrix. Keys are read from the environment; they are
# never written to the repository or evidence.
set -euo pipefail
cd "$(dirname "$0")"
if [ -z "${BINARYREPAIR_ASSISTANT_MODEL:-}" ]; then
  echo "set BINARYREPAIR_ASSISTANT_MODEL and a provider key first" >&2
  exit 2
fi
if [ "$#" -eq 0 ]; then
  echo "usage: ./run_matrix.sh <provider:model> [...]" >&2
  exit 2
fi
exec .venv/bin/python scripts/run_multi_model_matrix.py \
  --out "artifacts/multi-model-matrix-$(date +%Y%m%d)" \
  --models "$@" --benchmark --contract-level full
