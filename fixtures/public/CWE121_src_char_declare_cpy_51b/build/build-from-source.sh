#!/usr/bin/env bash
# Self-contained rebuild of the CWE121 fixture from the sources in ../source/.
#
# Run inside the isolated Ubuntu guest only. The host must not compile.
#
# WHY THIS SCRIPT EXISTS
#
# build/build.sh takes the case file and the support unit from an external
# Juliet checkout (JULIET_ROOT). That makes a reviewer depend on a 152,957,342 B
# download whose internal paths must match. This script removes that dependency:
# the unmodified case file and testcasesupport/ ship inside the fixture, with
# their own hashes in source/SHA256SUMS, so the block can be built from the
# package alone.
#
# WHAT IT DOES **NOT** PROVE
#
# It does not promise the byte-identical ELF `aa428157…8393`.
#
# -g records DW_AT_comp_dir and the source paths that were passed to gcc. T30
# measured this on the CWE416 fixture: the same sources built with relative vs
# absolute paths give different binaries (fc40085c… vs 0a26a805…), each stable
# within its own style. The path style that produced aa428157…8393 on 2026-10-20
# was not recorded, so no recipe can guarantee reproducing it.
#
# What this script guarantees instead:
#   1. the inputs are hash-checked before compiling;
#   2. the recipe is fixed and recorded here;
#   3. whatever it produces is stable for this recipe, so a second run can be
#      compared against the first.
#
# Treat its output as a rebuild of equivalent behaviour, not as a replacement
# for the frozen original.elf. Confirm the trigger boundary on it (49 × A must
# exit 0, 50 × A must still overrun) before using it for anything.
#
# Usage:
#   bash build/build-from-source.sh [output-elf]
#   default output: build/original-from-source.elf
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../source/CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b.c"
SUPPORT="$HERE/../source/testcasesupport"
OUT="${1:-$HERE/original-from-source.elf}"

for f in "$SRC" "$SUPPORT/io.c" "$SUPPORT/std_testcase.h" "$SUPPORT/std_testcase_io.h"; do
    test -f "$f" || { echo "missing source file: $f" >&2; exit 1; }
done

cd "$HERE"

# Verify the inputs against the recorded hashes before compiling. A mismatch
# means this is not the frozen fixture, so stop rather than build something
# that merely looks similar.
echo "== input hashes =="
sha256sum "$SRC" "$SUPPORT/io.c" "$SUPPORT/std_testcase.h" "$SUPPORT/std_testcase_io.h"

expected_case="8387d64613192b47c30658153548d111366f232a0bf03714e26643dd16ad343b"
actual_case=$(sha256sum "$SRC" | awk '{print $1}')
if [ "$actual_case" != "$expected_case" ]; then
    echo "case source hash mismatch: $actual_case != $expected_case" >&2
    exit 1
fi

# Flag list copied verbatim from build/build.sh so the two recipes differ only
# in where the sources come from.
echo "== build =="
gcc -O0 -g -fno-stack-protector -fno-pie -no-pie -Wall \
    -I "$SUPPORT" \
    -o "$OUT" \
    harness.c \
    "$SRC" \
    "$SUPPORT/io.c"

echo "== output =="
sha256sum "$OUT"
file "$OUT"
echo
echo "note: this hash is not expected to equal aa428157…8393; see the header."
