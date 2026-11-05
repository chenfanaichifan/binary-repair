#!/usr/bin/env python3
"""Apply the one authorized byte-level edit to the CWE416 no-input fixture.

The contract authorises two repairs (contract.json#authorized_edits). This one
takes the first: "drop the free() and accept the leak". The other option, moving
the read ahead of free(), needs new instructions in a code cave and changes more
bytes; it is not used here.

The edit is five bytes inside bad():

    vaddr 0x401305, file offset 0x1305
      e8 e6 fd ff ff    call 4010f0 <free@plt>
    -> 90 90 90 90 90    five NOPs

Everything else is copied through untouched: same file size, same entry point,
same program headers, no added byte anywhere. The 100-byte block therefore stays
allocated and printLine() reads live memory instead of tcache residue.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

OFFSET = 0x1305
VADDR = 0x401305
BEFORE = bytes.fromhex("e8e6fdffff")  # call 4010f0 <free@plt>
AFTER = bytes.fromhex("9090909090")  # 5 x nop


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    original = args.original.read_bytes()
    if original[:4] != b"\x7fELF" or original[4] != 2:
        raise SystemExit("not a 64-bit ELF")
    found = original[OFFSET : OFFSET + len(BEFORE)]
    if found != BEFORE:
        raise SystemExit(
            f"precondition failed at 0x{OFFSET:x}: expected {BEFORE.hex()}, got {found.hex()}"
        )

    candidate = bytearray(original)
    candidate[OFFSET : OFFSET + len(AFTER)] = AFTER
    candidate = bytes(candidate)

    if len(candidate) != len(original):
        raise SystemExit("patch changed the file size")
    diffs = [i for i, (a, b) in enumerate(zip(original, candidate)) if a != b]
    outside = [i for i in diffs if not OFFSET <= i < OFFSET + len(AFTER)]
    if outside:
        raise SystemExit(f"bytes changed outside the edit region: {outside[:8]}")

    args.out.write_bytes(candidate)
    report = {
        "schema_version": 1,
        "method": "byte-level instruction removal; no C replacement, no code cave, no added bytes",
        "original": {"path": args.original.name, "sha256": sha256(original), "size": len(original)},
        "candidate": {"path": args.out.name, "sha256": sha256(candidate), "size": len(candidate)},
        "edits": [
            {
                "file_offset": OFFSET,
                "file_offset_hex": hex(OFFSET),
                "vaddr": hex(VADDR),
                "length": len(AFTER),
                "before_hex": BEFORE.hex(),
                "after_hex": AFTER.hex(),
                "before_text": "call 4010f0 <free@plt>",
                "after_text": "nop; nop; nop; nop; nop",
                "contract_clause": "authorized_edits[0]: drop the free() and accept the leak",
            }
        ],
        "bytes_changed": len(diffs),
        "changed_intervals": [
            {"start": OFFSET, "end": OFFSET + len(AFTER) - 1, "size": len(AFTER)}
        ],
        "size_delta": len(candidate) - len(original),
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"candidate_sha256": report["candidate"]["sha256"],
                      "bytes_changed": len(diffs), "size_delta": report["size_delta"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
