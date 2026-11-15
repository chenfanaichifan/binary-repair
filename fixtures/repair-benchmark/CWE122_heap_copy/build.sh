#!/bin/sh
set -eu
cd "$(dirname "$0")"
CC=${CC:-x86_64-linux-gnu-gcc}
"$CC" -O0 -g -fno-stack-protector -fno-pie -no-pie \
  -o original.elf vuln.c
sha256sum original.elf
