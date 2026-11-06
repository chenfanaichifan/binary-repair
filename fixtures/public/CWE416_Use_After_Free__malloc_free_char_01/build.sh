#!/bin/sh
# Build the fixture artefact from the verbatim SARD source.
#
# INCLUDEMAIN is deliberately NOT defined: the upstream main() would call both
# good() and bad() in one process, and the harness supplies a fixed entry point
# instead.  The prefix maps strip the authoring host's absolute path so the
# DWARF in original.elf does not depend on where the tree is checked out.
set -eu

if ! command -v gcc >/dev/null 2>&1; then
    echo "gcc is required; this fixture ships no compiled artifact" >&2
    exit 1
fi

FIXTURE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$FIXTURE_ROOT"

CC=${CC:-gcc}

"$CC" \
    -mtune=generic -march=x86-64 -g -O0 \
    -fno-stack-protector -fno-pie \
    -fstack-clash-protection -fcf-protection -fasynchronous-unwind-tables \
    -ffile-prefix-map="$FIXTURE_ROOT"=. \
    -fmacro-prefix-map="$FIXTURE_ROOT"=. \
    -I support \
    -no-pie \
    -o original.elf \
    original.c harness.c support/io.c

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
