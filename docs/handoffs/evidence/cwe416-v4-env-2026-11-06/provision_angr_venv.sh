#!/bin/sh
# Rebuild the guest V4 environment from nothing.
#
# Measured target (2026-11-06, guest lab@binrepair-vm):
#   Ubuntu 24.04.5 LTS, kernel 6.8.0-147-generic, glibc 2.39, x86-64
#   CPython 3.12.3 at /usr/bin/python3.12
#   /opt/angr-venv created by `/usr/bin/python3 -m venv /opt/angr-venv`
#   angr 10.0.4.post1, z3-solver 5.1.0.0 (libz3 answers 5.1.0)
#   54 distributions, pip 26.2.1, `pip check` clean
#
# Run as a user with sudo. Needs egress to PyPI (about 650 MB installed).
#
#   sh provision_angr_venv.sh
#   /opt/angr-venv/bin/python selfcheck.py
#
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV=${VENV:-/opt/angr-venv}
PYTHON=${PYTHON:-/usr/bin/python3}
PIP_VERSION=${PIP_VERSION:-26.2.1}
REQS="$HERE/requirements-angr-10.0.4.post1.txt"

say() { printf '\n== %s\n' "$1"; }

[ -f "$REQS" ] || { echo "missing $REQS" >&2; exit 1; }

say "1. distro interpreter and the venv module"
# python3.12-venv is a separate package on Ubuntu; without it `-m venv` fails
# on ensurepip.
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv

say "2. the venv"
# pyvenv.cfg on the measured venv records exactly this command, with
# `version = 3.12.3` and `include-system-site-packages = false`.
sudo "$PYTHON" -m venv "$VENV"

say "3. pip $PIP_VERSION, then the 54 pins"
sudo "$VENV/bin/pip" install --upgrade "pip==$PIP_VERSION"
sudo "$VENV/bin/pip" install -r "$REQS"

say "4. checks"
"$VENV/bin/pip" check
"$VENV/bin/pip" freeze | wc -l
"$VENV/bin/python" -c 'import sys, angr, z3; print(sys.version.split()[0], angr.__version__, z3.get_version_string())'
"$VENV/bin/python" "$HERE/selfcheck.py"

say "done"
cat <<'NOTE'
A rebuild is only equivalent if the interpreter is the distro 3.12.3 and libz3
comes from the pinned z3-solver wheel — angr's results depend on both. Do not
substitute a pyenv/conda 3.12: the wheel tags and the z3 build differ.

This recipe reproduces the interpreter, not the verdicts. Whether the evidence
produced under it satisfies Gate V4 is a separate question, answered by
replaying it, not by this script.
NOTE
