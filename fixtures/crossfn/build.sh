#!/usr/bin/env bash
# Build the M2 cross-function fixtures (offline, deterministic flags).
#
# Usage: fixtures/crossfn/build.sh
#   ZIG=/path/to/zig overrides the bundled zig 0.17.1 toolchain path.
# Outputs: crossfn_param.elf, crossfn_global.elf, original.sha256
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
ZIG="${ZIG:-$ROOT/.tmp/zigpkg/site/ziglang/zig}"
if [ ! -x "$ZIG" ]; then
  echo "FAIL: zig toolchain not found at $ZIG (set ZIG=/path/to/zig)" >&2
  exit 1
fi
# -fno-sanitize=all keeps the fixture minimal and deterministic: zig cc's
# default C build links ubsan runtime checks that obscure the data-flow shape
# and inflate the image to ~4 MiB.  No DWARF is emitted (-g0): the stack
# capacity residual documented in README.md is intentional.
CFLAGS=(-target x86_64-linux-gnu -O0 -g0 -fno-pie -no-pie -fno-stack-protector
        -fno-sanitize=all)
: > "$HERE/original.sha256"
for name in crossfn_param crossfn_global; do
  "$ZIG" cc "${CFLAGS[@]}" -o "$HERE/$name.elf" "$HERE/$name.c"
  if command -v sha256sum >/dev/null 2>&1; then
    digest="$(sha256sum "$HERE/$name.elf" | cut -d' ' -f1)"
  else
    digest="$(shasum -a 256 "$HERE/$name.elf" | cut -d' ' -f1)"
  fi
  echo "built $name.elf sha256=$digest"
  echo "$digest  $name.elf" >> "$HERE/original.sha256"
done
echo "OK: original.sha256 written"
