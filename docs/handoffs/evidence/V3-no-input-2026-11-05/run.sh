#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3}
cd "$HERE"
exec "$PYTHON" ../../../../routeb/run_manifest_repaired.py \
  --binary ./candidate \
  --tests ./tests \
  --out ./manifest-repaired.json \
  --contract ./contract.json
