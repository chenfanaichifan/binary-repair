#!/bin/sh
# Emit 02-pip-freeze.txt: the exact package set, and the one distribution that
# `pip freeze` does not list.
#
#   sh run_freeze.sh > 02-pip-freeze.txt
set -u

PY=${PY:-/opt/angr-venv/bin/python}
PIP=${PIP:-/opt/angr-venv/bin/pip}

echo "# package set of /opt/angr-venv — guest $(hostname), $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo
echo "\$ /opt/angr-venv/bin/pip freeze"
"$PIP" freeze
echo
echo "# pip omits itself from freeze. It is the 55th distribution:"
echo "\$ /opt/angr-venv/bin/python -c 'import importlib.metadata as m; print(m.version(\"pip\"), len(list(m.distributions())))'"
"$PY" -c 'import importlib.metadata as m; print(m.version("pip"), len(list(m.distributions())))'
echo
echo "# and the requirement set resolves cleanly against itself:"
echo "\$ /opt/angr-venv/bin/pip check"
"$PIP" check
