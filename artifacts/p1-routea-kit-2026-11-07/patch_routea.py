#!/usr/bin/env python3
"""Route A candidate for CWE416 no-input: move read before free.

Original bad():
  0x401305  call free@plt
  ... later ...
  0x401311  call printLine

Route A patch:
  0x401305  call printLine   (read/print while block is alive)
  0x401311  call free@plt    (free after the read)

This uses the contract's authorized edit "Move the read of the block before
free()". No added code, no segment/import change, file size unchanged.
Run only in the disposable guest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ORIGINAL_SHA = "c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9"
OFF_PRINT = 0x1305
OFF_FREE = 0x1311
# 0x401305: call free@plt  -> call printLine (0x4013fe); rel = 0x4013fe-0x40130a
PRINT_BEFORE = bytes.fromhex("e8e6fdffff")
PRINT_AFTER = bytes.fromhex("e8f4000000")
# 0x401311: call printLine -> call free@plt (0x4010f0); rel = 0x4010f0-0x401316
FREE_BEFORE = bytes.fromhex("e8e8000000")
FREE_AFTER = bytes.fromhex("e8dafdffff")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    original = args.original.read_bytes()
    if sha(original) != ORIGINAL_SHA:
        raise SystemExit(f"original hash mismatch: {sha(original)}")
    if original[OFF_PRINT:OFF_PRINT + 5] != PRINT_BEFORE:
        raise SystemExit(f"print-site precondition failed at {OFF_PRINT:#x}")
    if original[OFF_FREE:OFF_FREE + 5] != FREE_BEFORE:
        raise SystemExit(f"free-site precondition failed at {OFF_FREE:#x}")

    cand = bytearray(original)
    cand[OFF_PRINT:OFF_PRINT + 5] = PRINT_AFTER
    cand[OFF_FREE:OFF_FREE + 5] = FREE_AFTER
    candidate = bytes(cand)
    if len(candidate) != len(original):
        raise SystemExit("patch changed file size")
    diffs = [i for i, (a, b) in enumerate(zip(original, candidate)) if a != b]
    expected = sorted(
        i
        for i in set(range(OFF_PRINT, OFF_PRINT + 5)) | set(range(OFF_FREE, OFF_FREE + 5))
        if original[i] != candidate[i]
    )
    if diffs != expected:
        raise SystemExit(f"unexpected diff set: {diffs} expected {expected}")

    args.out.write_bytes(candidate)
    report = {
        "schema_version": 1,
        "route": "route_a",
        "method": "swap two call targets: printLine before free (contract authorized edit 1)",
        "original": {"sha256": sha(original), "size": len(original)},
        "candidate": {"sha256": sha(candidate), "size": len(candidate)},
        "edits": [
            {"offset": OFF_PRINT, "vaddr": "0x401305", "before": PRINT_BEFORE.hex(),
             "after": PRINT_AFTER.hex(), "text": "call free@plt -> call printLine"},
            {"offset": OFF_FREE, "vaddr": "0x401311", "before": FREE_BEFORE.hex(),
             "after": FREE_AFTER.hex(), "text": "call printLine -> call free@plt"},
        ],
        "bytes_changed": len(diffs),
        "size_delta": 0,
        "independent_of_route_b": "route B candidate is 46d16e99 (NOP free); this candidate swaps calls and has a different hash",
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_sha256": report["candidate"]["sha256"],
                      "bytes_changed": len(diffs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
