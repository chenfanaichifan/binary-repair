#!/usr/bin/env bash
# Run M4's fixed Gate 5 script inside the guest/jobwrap.
# Invocation:
#   GATE5_SCRIPT=/path/M4-gate5-fixed.sh \
#     jobwrap gate5 -- <repo>/routeb/jobwrap_gate5.sh <repo> <work-dir>
#
# This wrapper never calls sudo/unshare and never runs on the host.
set -euo pipefail
ROOT=${1:-$PWD}
WORK=${2:-$PWD/gate5-evidence}
SCRIPT=${GATE5_SCRIPT:-}
if [[ -z "$SCRIPT" || ! -x "$SCRIPT" ]]; then
  echo "GATE5_SCRIPT must point to an executable M4 Gate 5 script" >&2
  exit 2
fi
mkdir -p "$WORK"
export HOME="$WORK/home"
export TMPDIR="$WORK/tmp"
mkdir -p "$HOME" "$TMPDIR"
cd "$ROOT"
exec "$SCRIPT" "$ROOT" "$WORK"
