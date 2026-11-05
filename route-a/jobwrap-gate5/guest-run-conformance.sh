#!/usr/bin/env bash
# guest-run-conformance.sh — one-shot: build the successor, install config,
# run the conformance window, emit evidence. GUEST ONLY.
#
# This script compiles a binary, so it must never run on the host
# (AGENTS.md §3). It refuses unless it sees Linux and root.
#
# Usage (inside the disposable Ubuntu guest, as root):
#   bash route-a/jobwrap-gate5/guest-run-conformance.sh <repo-root> [job-id]
#
# It will:
#   1. refuse on non-Linux / non-root;
#   2. compile jobwrap_gate5.c -> /var/tmp/conformance/jobwrap-gate5 (static, -Werror);
#      never into /usr/local/sbin, where the Gate 4 and Gate 5 binaries live;
#   3. install routea.conf.sample -> /usr/local/etc/binrepair/routea.conf (0600);
#   4. run the conformance matrix via workers/broker/guest_conformance.py;
#   5. print the evidence path and the host-side verdict command.
#
# It also needs the host-generated case matrix:
#   host$ python -m workers.broker.conformance --dump-matrix matrix.json
# and a JSON matrix path in $MATRIX (default /var/tmp/conformance/matrix.json).
#
# Nothing it does is a claim of success; the verdict is computed on the host.

set -uo pipefail

REPO=${1:-}
JOB_ID=${2:-demo}

refuse() { echo "guest-run-conformance: refusing: $*" >&2; exit 2; }

[[ "$(uname -s)" == "Linux" ]] || refuse "not Linux; the host never compiles or runs binaries"
[[ "$(id -u)" == "0" ]] || refuse "must run as root (euid=$(id -u))"
[[ -n "$REPO" ]] || refuse "usage: $0 <repo-root> [job-id]"
[[ -f "$REPO/route-a/jobwrap-gate5/jobwrap_gate5.c" ]] || refuse "source not found under $REPO"

SRC="$REPO/route-a/jobwrap-gate5/jobwrap_gate5.c"
# Scratch build. DO NOT build into /usr/local/sbin:
#   /usr/local/sbin/jobwrap       b232d60b…  is bound to Gate 4
#   /usr/local/sbin/jobwrap-gate5 0066973d…  is bound to Gate 5
# Overwriting either would invalidate a recorded hash binding. The conformance
# build is a separate artefact and stays under /var/tmp (record 89 §6).
BIN=/var/tmp/conformance/jobwrap-gate5
CONF_DIR=/usr/local/etc/binrepair
CONF=$CONF_DIR/routea.conf
WORK=/var/tmp/conformance
EVID=$WORK/evidence.json

mkdir -p "$WORK"

echo "=== 1/4 build ==="
gcc -O2 -Wall -Wextra -Werror -static -o "$BIN" "$SRC" || {
    echo "BUILD FAILED — check the compiler output above." >&2
    exit 3
}
chown root:root "$BIN"; chmod 0755 "$BIN"
echo "built: $BIN"
sha256sum "$BIN"
echo "NOTE: Gate 4 (b232d60b) and Gate 5 (0066973d) binaries untouched."

echo "=== 2/4 install config ==="
mkdir -p "$CONF_DIR"
install -o root -g root -m 0600 \
    "$REPO/route-a/jobwrap-gate5/routea.conf.sample" "$CONF"
echo "installed: $CONF"
sed -n '1,5p' "$CONF" | sed 's/^/  /'

echo "=== 3/4 prepare work dirs ==="
mkdir -p "$WORK"
# Probe cases drop to uid 1003 and write their attestation into --work, so that
# directory must be writable by the dropped uid.
chmod 0777 "$WORK"
JOB_DIR="/var/lib/binrepair/jobs/$JOB_ID"
mkdir -p "$JOB_DIR/route_a"
# The job dir must be writable by uid 1003 for the worker's output, but the
# input files stay root-owned and read-only (see record 89 §6 on this being a
# demo-level convenience, not a production permission model).
chmod 0777 "$JOB_DIR" 2>/dev/null || true
mkdir -p /var/lib/binrepair/evidence
chmod 0700 /var/lib/binrepair/evidence
echo "work dirs ready"
[[ -f "${MATRIX:-/var/tmp/conformance/matrix.json}" ]] || {
    echo "MISSING case matrix: set MATRIX=/path/matrix.json" >&2
    echo "generate it on the host: python -m workers.broker.conformance --dump-matrix matrix.json" >&2
    exit 5
}

echo "=== 4/4 conformance matrix ==="
python3 "$REPO/workers/broker/guest_conformance.py" \
    --executor "$BIN" \
    --matrix "${MATRIX:-/var/tmp/conformance/matrix.json}" \
    --repo "$REPO" \
    --work "$WORK" \
    --routea-work "$JOB_DIR" \
    --snapshot-uid "${SNAPSHOT_UID:-11}" \
    --snapshot-name "${SNAPSHOT_NAME:-gate4-harness}" \
    --original-jobwrap /usr/local/sbin/jobwrap \
    --out "$EVID" \
    --guest-ack || {
        echo "runner failed; no evidence written" >&2
        exit 4
    }

echo
echo "=== evidence ==="
sha256sum "$EVID"
echo
echo "Copy the evidence out, then judge it ON THE HOST with:"
echo "  python3 -c \"import json,sys; from workers.broker.conformance import evaluate; \\"
echo "    print(evaluate(json.load(open(sys.argv[1]))).model_dump_json(indent=2))\" $EVID"
echo
echo "Note: routea cases need a real job. With only the sample config and no"
echo "candidate at /var/lib/binrepair/jobs/$JOB_ID/route_a/candidate.elf they"
echo "will come back as exit 4 (hash mismatch) or abort earlier — that is"
echo "expected and will show up as fail/inconclusive, never as pass."
