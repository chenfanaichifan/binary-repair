#!/bin/sh
# Build the committed fixture artefact. Requires gcc on x86-64 Linux.
# -DINCLUDEMAIN pulls in Juliet's own main(); -DOMITGOOD drops good1() so the
# binary exercises only the flawed path, which is what the contract describes.
set -eu
cd "$(dirname "$0")"
gcc -O0 -g -DINCLUDEMAIN -DOMITGOOD -I support src.c support/io.c -o original.elf