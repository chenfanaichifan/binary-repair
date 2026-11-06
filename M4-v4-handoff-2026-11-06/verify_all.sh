#!/bin/sh
# Everything a verifier needs to run, in order.
#
#   sh verify_all.sh
#
# 1. SHA256SUMS covers every file in this handoff.
# 2. run_selfcheck.sh   — the machine is the recorded one.
# 3. run_e2e.sh         — the producer reproduces the recorded output.
#
# Each step prints PASS or FAIL, and the script exits with the number of failed
# steps (0 = everything passed). Running the steps individually is fine; this
# exists so nobody has to remember the order.
set -u

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
failures=0

echo "=== 1/3  file integrity ==="
if command -v sha256sum >/dev/null 2>&1; then
    if (cd "$HERE" && sha256sum -c SHA256SUMS >/dev/null 2>&1); then
        rows=$(wc -l < "$HERE/SHA256SUMS")
        echo "PASS: $rows files match SHA256SUMS"
    else
        echo "FAIL: SHA256SUMS does not match the files here; rerun sha256sum -c for detail"
        failures=$((failures + 1))
    fi
else
    echo "SKIP: no sha256sum on this machine"
fi

echo
echo "=== 2/3  environment self-check ==="
sh "$HERE/run_selfcheck.sh"
rc=$?
[ "$rc" -eq 0 ] || failures=$((failures + 1))

echo
echo "=== 3/3  end-to-end rerun ==="
sh "$HERE/run_e2e.sh"
rc=$?
[ "$rc" -eq 0 ] || failures=$((failures + 1))

echo
if [ "$failures" -eq 0 ]; then
    echo "ALL PASS: 3/3 steps"
else
    echo "FAILED: $failures of 3 steps"
fi
exit "$failures"
