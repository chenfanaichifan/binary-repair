#!/usr/bin/env bash
# Build the routeb fixture as a non-PIE x86-64 Linux ELF for Route A.
# On arm64 Linux/macOS use a cross compiler (x86_64-linux-gnu-gcc) or Zig.
set -euo pipefail
cd "$(dirname "$0")"
CC=${CC:-x86_64-linux-gnu-gcc}
if ! command -v "$CC" >/dev/null 2>&1; then
  echo "missing $CC; install gcc-x86-64-linux-gnu (Linux) or set CC to a cross compiler" >&2
  exit 2
fi
"$CC" -O0 -g0 -fno-stack-protector -fno-builtin -fno-pie -no-pie \
  -o vuln-x86_64 vuln.c
file vuln-x86_64
sha256sum vuln-x86_64 2>/dev/null || shasum -a 256 vuln-x86_64
