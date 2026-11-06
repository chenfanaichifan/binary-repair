#!/bin/sh
# Build the committed fixture artefact. Requires gcc on x86-64 Linux.
# -DINCLUDEMAIN pulls in Juliet's own main(); -DOMITGOOD drops good1() so the
# binary exercises only the flawed path, which is what the contract describes.
#
# -fno-pie -no-pie: the contract's environment_assumptions require a non-PIE
#   guest. A PIE build is a different artefact and must not stand in for this one.
#
# -ffile-prefix-map: -g records the build directory in DW_AT_comp_dir, so the same
#   sources compiled in two directories give two digests with identical code. The
#   committed artefact was built in /var/tmp/cwe122; mapping every build to that
#   path makes the digest reproducible anywhere. Without it a rebuild differs in a
#   few bytes of .debug_line_str — and, because the linker hashes the whole file,
#   in the build-id too.
set -eu
cd "$(dirname "$0")"
here=$(pwd -P)
gcc -O0 -g -fno-pie -no-pie \
    -ffile-prefix-map="$here=/var/tmp/cwe122" \
    -DINCLUDEMAIN -DOMITGOOD -I support src.c support/io.c -o original.elf
