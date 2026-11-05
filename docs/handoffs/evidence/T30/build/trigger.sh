#!/usr/bin/env bash
# Deterministic trigger for CWE416_Use_After_Free__malloc_free_char_01.
#
# Run inside the isolated guest only.
#
# Why `setarch -R` is required:
#
# The defect is unconditional -- bad() mallocs 100 bytes, fills them with 'A',
# frees the block, then reads it through printLine(). There is no input that
# avoids it, so the *path* is always the same. What is not stable is the bytes
# read back: glibc's tcache writes its next/key words into the first 16 bytes of
# a freed chunk, and the key carries a heap address. With ASLR on, that address
# changes every run, so stdout changes with it (measured: f76701, 0b1d03,
# a97c02 on three consecutive runs). `setarch -R` disables ASLR for this
# process only -- it does not alter the program or the allocator -- and makes
# the observation reproducible.
#
# What the observation proves:
#
# A correct program prints 99 'A' bytes followed by a newline: 100 bytes, and
# exit 0. This build prints 2 bytes of heap residue then stops (the third byte
# of the freed block is NUL), and also exits 0 -- so the defect is silent: no
# crash, no error, exit status unchanged. That silent-success shape is the
# reason the trigger records the exact bytes rather than only the exit code.
#
# Usage:
#   ./trigger.sh [binary]            one run, key=value on stdout
#   ./trigger.sh --repeat 50 [bin]   50 runs, report distinct observations
set -uo pipefail

REPEAT=1
if [ "${1:-}" = "--repeat" ]; then
    REPEAT=${2:?--repeat needs a count}
    shift 2
fi
BIN=${1:-./original.elf}

if [ ! -x "$BIN" ]; then
    echo "missing or non-executable binary: $BIN" >&2
    exit 2
fi

run_once() {
    local tmp rc
    tmp=$(mktemp -d) || return 1
    setarch -R "$BIN" >"$tmp/out" 2>"$tmp/err"
    rc=$?
    printf 'exit_code=%d stdout_hex=%s stdout_len=%d stderr_len=%d\n' \
        "$rc" \
        "$(od -An -tx1 -v "$tmp/out" | tr -d ' \n')" \
        "$(wc -c <"$tmp/out")" \
        "$(wc -c <"$tmp/err")"
    rm -rf "$tmp"
}

if [ "$REPEAT" -eq 1 ]; then
    run_once
    exit 0
fi

# Determinism evidence: every run must produce the identical observation.
i=0
while [ "$i" -lt "$REPEAT" ]; do
    run_once || exit 3
    i=$((i + 1))
done | sort | uniq -c | awk '{printf "%dx %s\n", $1, substr($0, index($0,$2))}'
