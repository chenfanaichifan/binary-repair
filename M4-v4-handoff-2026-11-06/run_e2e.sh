#!/bin/sh
# Rerun the V4 producer on the supplied binaries and compare its output with the
# recorded one, byte for byte.
#
#   sh run_e2e.sh
#
# This is the part that would catch a producer whose numbers drift with an
# environment that still passes the version checks. Exit 0 only if the harness
# exits 0 and its output file is identical to expected/harness-output.expected.json.
set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PY=${PY:-/opt/angr-venv/bin/python}

if [ ! -x "$PY" ]; then
    echo "no interpreter at $PY" >&2
    exit 2
fi

for f in inputs/v4_harness.py inputs/candidate.elf inputs/original.elf inputs/contract.json; do
    if [ ! -f "$HERE/$f" ]; then
        echo "missing input: $HERE/$f" >&2
        exit 2
    fi
done

TMP=$(mktemp -d 2>/dev/null || mktemp -d -t e2e) || exit 2
trap 'rm -rf "$TMP"' EXIT INT TERM

echo "\$ $PY inputs/v4_harness.py --candidate inputs/candidate.elf \\"
echo "      --original inputs/original.elf --contract inputs/contract.json \\"
echo "      --out $TMP/harness-output.json"
start=$(date +%s)
"$PY" "$HERE/inputs/v4_harness.py" \
    --candidate "$HERE/inputs/candidate.elf" \
    --original "$HERE/inputs/original.elf" \
    --contract "$HERE/inputs/contract.json" \
    --out "$TMP/harness-output.json" > "$TMP/harness.log" 2>&1
rc=$?
end=$(date +%s)
if [ "$rc" -ne 0 ]; then
    echo "FAIL: harness exited $rc; last lines of its log:" >&2
    tail -20 "$TMP/harness.log" >&2
    exit "$rc"
fi
echo "  exit 0 in $((end - start)) s"
echo

echo "\$ sha256sum harness-output.json expected/harness-output.expected.json"
sha256sum "$TMP/harness-output.json" "$HERE/expected/harness-output.expected.json" \
    | sed 's|^|  |'
echo

echo "\$ cmp -s harness-output.json expected/harness-output.expected.json"
if ! cmp -s "$TMP/harness-output.json" "$HERE/expected/harness-output.expected.json"; then
    echo "  differs; first 20 differing bytes:"
    cmp -l "$TMP/harness-output.json" "$HERE/expected/harness-output.expected.json" \
        | head -20 | sed 's/^/  /'
    echo
    echo "FAIL: the producer no longer reproduces the recorded output"
    exit 1
fi
echo "  byte-identical"
echo

echo "\$ $PY scripts/summarize_output.py harness-output.json"
"$PY" "$HERE/scripts/summarize_output.py" "$TMP/harness-output.json"
echo
echo "PASS: the harness reproduces the recorded output from these inputs"
