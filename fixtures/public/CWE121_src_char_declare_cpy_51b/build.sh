#!/bin/sh
# Reproduce original.elf. Offline and fail-closed: every prerequisite is
# checked before the compiler runs, and the result is compared with the hash
# recorded in build.json.
#
# Needs: gcc 13.3.0 (Ubuntu 24.04) and a juliet-v1.3 testcasesupport tree.
# Neither is vendored here; build.json#reproduction records that this recipe has
# not been run on the authoring host.
set -eu

if [ -z "${JULIET_ROOT:-}" ]; then
    echo "JULIET_ROOT must point at the juliet-v1.3/C directory" >&2
    exit 1
fi

SUPPORT="$JULIET_ROOT/testcasesupport"
if [ ! -f "$SUPPORT/io.c" ] || [ ! -f "$SUPPORT/std_testcase.h" ]; then
    echo "missing Juliet testcasesupport under $SUPPORT" >&2
    exit 1
fi

if ! command -v gcc >/dev/null 2>&1; then
    echo "gcc is required" >&2
    exit 1
fi

CC=${CC:-gcc}

"$CC" \
    -mtune=generic -march=x86-64 -g -O0 \
    -fno-stack-protector -fno-pie \
    -fstack-clash-protection -fcf-protection -fasynchronous-unwind-tables \
    -no-pie \
    -I "$SUPPORT" \
    -o original.elf \
    src.c harness.c "$SUPPORT/io.c"

EXPECTED=$(python3 -c 'import json;print(json.load(open("build.json"))["output"]["sha256"])')
ACTUAL=$(python3 -c 'import hashlib;print(hashlib.sha256(open("original.elf","rb").read()).hexdigest())')

if [ "$EXPECTED" != "$ACTUAL" ]; then
    echo "hash mismatch: build.json says $EXPECTED, the build produced $ACTUAL" >&2
    exit 1
fi

echo "reproduced original.elf ($ACTUAL)"
