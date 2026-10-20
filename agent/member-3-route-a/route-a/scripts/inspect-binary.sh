#!/usr/bin/env bash
# inspect-binary.sh — STUB.
#
# Intended: one command that writes the ELF inspection report for
#   docs/03-architecture.md (file + ELF header + program headers + sections)
# and, optionally, the disassembly of one function for
#   docs/04-instruction-inspection.md.
#
# Not implemented yet: this is the skeleton committed before the lab work
# starts. Replace the body once the shared sample is frozen.
#
# Usage (planned):
#   ./scripts/inspect-binary.sh <elf> [function-name] [out-dir]

set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <elf> [function-name] [out-dir]" >&2
  exit 2
fi

echo "inspect-binary.sh: not implemented (skeleton)" >&2
echo "planned inputs: elf=$1 function=${2:-<none>} out=${3:-reports}" >&2
exit 1
