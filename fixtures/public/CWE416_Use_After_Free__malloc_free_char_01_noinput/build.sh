#!/bin/sh
# Build the CWE416 no-input fixture binary. Run inside the isolated Ubuntu guest.
#
# This is the T30 recipe (docs/handoffs/evidence/T30/build/build.sh, sha256
# 6e33c825...) with exactly one change: the test-case support unit is resolved
# from ./support instead of a Juliet checkout, so the fixture is self-contained.
# The compiler line is untouched -- same flags, same order, same prefix maps.
#
# Why the prefix maps are here: -g embeds DW_AT_comp_dir and the source file
# names. The same sources built in a differently-named directory produce a
# different binary without them. They normalise the recorded paths to stable
# virtual ones, so the digest depends on the code and the flags, not on where
# the tree happens to sit. Measured in the T30 window on 2026-11-05:
#
#   relative paths, cwd = source dir   -> fc40085c...87e0   (stable)
#   absolute paths, same cwd           -> 0a26a805...07ec   (stable)
#   relative + prefix-map              -> c9c2632e...23c9   (stable)
#
# Source of truth for the case file is the SARD case shipped by
# dsp-testing/samate-c-cpp at 01e353d, byte-identical to original.c here
# (fa84a6bb...f42e). support/io.c and support/std_testcase.h are the Juliet 1.3
# testcasesupport files, byte-identical to the same paths in that archive.
#
# Expect a -Wuse-after-free warning from original.c line 36. That warning IS the
# defect; build.json records it rather than suppressing it.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
SUPPORT="${SUPPORT:-$HERE/support}"
OUT="${1:-$HERE/original.elf}"

test -f "$HERE/original.c" || { echo "missing case source: $HERE/original.c" >&2; exit 1; }
test -f "$HERE/harness.c" || { echo "missing harness: $HERE/harness.c" >&2; exit 1; }
test -f "$SUPPORT/io.c" || { echo "missing support unit: $SUPPORT/io.c" >&2; exit 1; }

# Compile from the source directory with relative names, so `-o` and the two
# local sources never appear as absolute paths.
cd "$HERE"

echo "== inputs =="
sha256sum original.c harness.c "$SUPPORT/io.c" "$SUPPORT/std_testcase.h"

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
printf 'sha256=%s\n' "$(sha256sum "$OUT" | cut -d' ' -f1)"
printf 'size=%s\n' "$(wc -c <"$OUT" | tr -d ' ')"
