#!/bin/sh
# Emit 01-selfcheck.txt: the environment self-check, with the command shown.
#
#   sh run_selfcheck.sh > 01-selfcheck.txt
set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PY=${PY:-/opt/angr-venv/bin/python}

echo "# environment self-check — guest $(hostname), $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
echo "\$ /opt/angr-venv/bin/python selfcheck.py"
"$PY" "$HERE/selfcheck.py"
echo "exit=$?"
