#!/usr/bin/env bash
# Build the frozen fixture binary. Run inside the isolated Ubuntu guest only.
#
# The NIST Juliet C/C++ 1.3 test case is compiled unmodified; this script only
# supplies the harness entry point and the test-case support unit.
set -euo pipefail

JULIET_ROOT="${JULIET_ROOT:-$HOME/evaluator/src/juliet-v1.3}"
CASE="CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b"
SUPPORT="$JULIET_ROOT/C/testcasesupport"
SRC="$JULIET_ROOT/C/testcases/CWE121_Stack_Based_Buffer_Overflow/s09/$CASE.c"
OUT="${1:-$PWD/original.elf}"

test -f "$SRC" || { echo "missing Juliet source: $SRC" >&2; exit 1; }
test -f "$SUPPORT/io.c" || { echo "missing Juliet support: $SUPPORT/io.c" >&2; exit 1; }

gcc -O0 -g -fno-stack-protector -fno-pie -no-pie -Wall \
    -I "$SUPPORT" \
    -o "$OUT" \
    harness.c \
    "$SRC" \
    "$SUPPORT/io.c"

sha256sum "$OUT"
file "$OUT"
