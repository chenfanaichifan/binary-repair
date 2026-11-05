#!/bin/sh
# Build the CWE416 fixture binary. Run inside the isolated Ubuntu guest only.
#
# Invoke as `sh build.sh` or `./build.sh`; the body is POSIX sh, not bash, so
# both work (dash does not support `set -o pipefail` or ${BASH_SOURCE}).
#
# The NIST Juliet test case is compiled unmodified; this script only supplies
# the harness entry point and the test-case support unit, exactly as the CWE121
# fixture does.
#
# Source of truth for the case file is NOT the local Juliet checkout (that
# checkout ships CWE121 only). It is:
#
#   repo   dsp-testing/samate-c-cpp
#   commit 01e353daa3d28a4ce2ae68904cbcde5e03e3519d
#   path   C/testcases/CWE416_Use_After_Free/
#          CWE416_Use_After_Free__malloc_free_char_01.c
#   sha256 fa84a6bb9df36a8a1ab4d33a7064746d9037247f7599d3cd39659478d4b7f42e
#
# testcasesupport/ comes from the local Juliet 1.3 checkout. That is safe
# because std_testcase.h and io.c there are byte-identical to the same paths in
# dsp-testing/samate-c-cpp @ 01e353d (verified 2026-11-05:
# a78aaf3a54a6210260ad70123c09c3c283c6edf7808b6244205e00b8f2d9b8d0 and
# 50ace91d0f9cd9f281d5d8ff3a9ca879ee2779d737030ae84e8e4be3df5b299c).
#
# REPRODUCIBILITY NOTE -- why the two prefix-map flags are here.
#
# -g embeds DW_AT_comp_dir and the source file names into the binary. Measured
# on 2026-11-05, same sources and same gcc, two builds each:
#
#   relative paths, cwd = source dir   -> fc40085c...87e0   (stable)
#   absolute paths, same cwd           -> 0a26a805...07ec   (stable)
#   relative + prefix-map              -> c9c2632e...23c9   (stable)
#
# Each invocation style is internally reproducible, but the hash DIFFERS between
# styles, so the same recipe in a differently-named directory would silently
# produce a different binary. The two flags below normalise the recorded paths
# to stable virtual ones, which removes that failure mode. This is a deliberate
# deviation from the CWE121 fixture's flag list (which omits them); build.json
# records the full flag string so nothing is implied.
set -eu

JULIET_ROOT="${JULIET_ROOT:-$HOME/evaluator/src/juliet-v1.3}"
SUPPORT="$JULIET_ROOT/C/testcasesupport"
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="${1:-$HERE/original.elf}"

test -f "$HERE/original.c" || { echo "missing case source: $HERE/original.c" >&2; exit 1; }
test -f "$HERE/harness.c" || { echo "missing harness: $HERE/harness.c" >&2; exit 1; }
test -f "$SUPPORT/io.c" || { echo "missing Juliet support: $SUPPORT/io.c" >&2; exit 1; }

# Compile from the source directory with relative names, so `-o` and the two
# local sources never appear as absolute paths.
cd "$HERE"

echo "== inputs =="
sha256sum original.c harness.c "$SUPPORT/io.c" "$SUPPORT/std_testcase.h"

# -fno-stack-protector is a fixture build decision: this case has no stack
# overflow, but keeping the flag identical to the CWE121 fixture means the two
# fixtures differ only in the case source, not in build posture.
#
# Expect a -Wuse-after-free warning from the case file at line 36. That warning
# IS the defect; it is recorded in build.json rather than suppressed, because
# silencing it would hide the very thing the fixture exists to demonstrate.
gcc -O0 -g -fno-stack-protector -fno-pie -no-pie -Wall \
    -fdebug-prefix-map="$HERE"=. -ffile-prefix-map="$HERE"=. \
    -fdebug-prefix-map="$SUPPORT"=juliet/testcasesupport \
    -ffile-prefix-map="$SUPPORT"=juliet/testcasesupport \
    -I "$SUPPORT" \
    -o "$OUT" \
    harness.c \
    original.c \
    "$SUPPORT/io.c"

echo "== output =="
sha256sum "$OUT"
file "$OUT"
# Machine-readable lines, so a caller (or a human pasting into build.json) can
# read the values without parsing sha256sum's two-column format.
printf 'sha256=%s\n' "$(sha256sum "$OUT" | cut -d' ' -f1)"
printf 'size=%s\n' "$(wc -c <"$OUT" | tr -d ' ')"
