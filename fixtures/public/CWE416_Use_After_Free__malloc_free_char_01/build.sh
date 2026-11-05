#!/bin/sh
# Produce original.elf offline.  Fail closed: every prerequisite is checked
# before the compiler runs, and the result is compared with build.json.
#
# This recipe has NOT been run on the authoring host (no guest compiler there).
# build.json#output.sha256 is null until M3/VMer builds it; the script then
# prints the digest to record, and refuses to overwrite a non-null mismatch.
set -eu

if ! command -v gcc >/dev/null 2>&1; then
    echo "gcc is required; this sample has no compiled artifact on the authoring host" >&2
    exit 1
fi

CC=${CC:-gcc}

"$CC" \
    -mtune=generic -march=x86-64 -g -O0 \
    -fno-stack-protector -fno-pie \
    -fstack-clash-protection -fcf-protection -fasynchronous-unwind-tables \
    -no-pie \
    -o original.elf \
    src.c harness.c

ACTUAL=$(sha256sum original.elf | cut -d' ' -f1)
EXPECTED=$(python3 -c 'import json;print(json.load(open("build.json"))["output"]["sha256"] or "")')

if [ -z "$EXPECTED" ]; then
    echo "built original.elf" >&2
    echo "build.json#output.sha256 is null; record $ACTUAL after review" >&2
    echo "sha256=$ACTUAL"
    exit 0
fi

if [ "$EXPECTED" != "$ACTUAL" ]; then
    echo "hash mismatch: build.json says $EXPECTED, the build produced $ACTUAL" >&2
    exit 1
fi

echo "original.elf reproduces build.json#output.sha256"
