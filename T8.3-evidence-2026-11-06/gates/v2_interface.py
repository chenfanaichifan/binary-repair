#!/usr/bin/env python3
"""V2 (interface) checks for the CWE416 no-input candidate.

Five static checks, each a comparison between the unrepaired original and the
candidate. Nothing is executed: this gate asks whether the repair changed the
binary's *interface* — the symbol, the dynamic imports, the linkage, the entry
point — not whether its behaviour is right (that is V3/V4).

    python3 v2_interface.py --original fixture/original.elf \
                            --candidate candidate/candidate.elf \
                            --symbol CWE416_Use_After_Free__malloc_free_char_01_bad \
                            --out gates/V2-interface.json

Exit 0 when all five pass, 1 otherwise, 2 when readelf is missing or a file is
absent. The output is JSON with one entry per check, the measured values that
decide it, and the things it does not prove.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

CHECKS = (
    "target_symbol_present_and_unchanged",
    "dynamic_symbol_table_unchanged",
    "needed_and_flags_unchanged",
    "entry_point_unchanged",
    "no_new_dynamic_import",
)

DOES_NOT_PROVE = [
    "runtime ABI conformance for callers outside this fixture",
    "that a caller compiled against the original still links against the candidate in every case",
    "behavioural equivalence: V2 compares the interface, V3 and V4 compare the behaviour",
]


def readelf(*args: str) -> str:
    return subprocess.run(["readelf", *args], capture_output=True, text=True,
                          check=False).stdout


def symbol_rows(binary: Path, symbol: str) -> list[str]:
    rows = []
    for line in readelf("-sW", str(binary)).splitlines():
        if line.rstrip().endswith(symbol):
            rows.append(" ".join(line.split()))
    return rows


def dynsym(binary: Path) -> list[str]:
    out = readelf("--dyn-syms", "-W", str(binary))
    rows = []
    for line in out.splitlines():
        fields = line.split()
        # 1: (2) 3: 4: 5: 6: 7: 8: name — keep the whole normalised row
        if len(fields) >= 8 and fields[0].endswith(":"):
            rows.append(" ".join(fields))
    return rows


def dynamic(binary: Path) -> dict[str, list[str]]:
    out = readelf("-dW", str(binary))
    needed, flags = [], []
    for line in out.splitlines():
        if "(NEEDED)" in line:
            needed.append(" ".join(line.split()))
        if "(FLAGS)" in line or "(FLAGS_1)" in line:
            flags.append(" ".join(line.split()))
    return {"needed": needed, "flags": flags}


def header(binary: Path) -> dict[str, str]:
    out = readelf("-hW", str(binary))
    fields = {}
    for line in out.splitlines():
        for key in ("Type:", "Machine:", "Entry point address:"):
            if key in line:
                fields[key.rstrip(":")] = line.split(key)[1].strip()
    return fields


def relocations(binary: Path) -> list[str]:
    out = readelf("-rW", str(binary))
    rows = []
    for line in out.splitlines():
        fields = line.split()
        if fields and fields[0].rstrip(":").isdigit() and len(fields) >= 5:
            rows.append(" ".join(fields))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    if shutil.which("readelf") is None:
        print("readelf not found", file=sys.stderr)
        return 2
    for path in (args.original, args.candidate):
        if not path.is_file():
            print(f"missing: {path}", file=sys.stderr)
            return 2

    results: list[dict] = []

    def record(check: str, passed: bool, measured: dict) -> None:
        results.append({"id": check, "pass": bool(passed), "measured": measured})
        print(f"  [{'ok' if passed else 'FAIL'}] {check}")

    # 1. the target symbol: same name, address, size, binding, visibility, type
    original_row = symbol_rows(args.original, args.symbol)
    candidate_row = symbol_rows(args.candidate, args.symbol)
    record(CHECKS[0], len(original_row) == 1 and original_row == candidate_row,
           {"symbol": args.symbol,
            "original_rows": original_row, "candidate_rows": candidate_row})

    # 2. the dynamic symbol table as a whole
    original_dyn = dynsym(args.original)
    candidate_dyn = dynsym(args.candidate)
    record(CHECKS[1], original_dyn == candidate_dyn,
           {"original_count": len(original_dyn), "candidate_count": len(candidate_dyn),
            "only_in_original": [r for r in original_dyn if r not in candidate_dyn][:5],
            "only_in_candidate": [r for r in candidate_dyn if r not in original_dyn][:5]})

    # 3. DT_NEEDED and the dynamic flags
    original_dynsec = dynamic(args.original)
    candidate_dynsec = dynamic(args.candidate)
    record(CHECKS[2], original_dynsec == candidate_dynsec,
           {"original": original_dynsec, "candidate": candidate_dynsec})

    # 4. ELF type, machine and entry point
    original_header = header(args.original)
    candidate_header = header(args.candidate)
    record(CHECKS[3], original_header == candidate_header,
           {"original": original_header, "candidate": candidate_header})

    # 5. no dynamic import the original did not have
    original_undefined = [r for r in original_dyn if " UND " in r]
    candidate_undefined = [r for r in candidate_dyn if " UND " in r]
    added = [r for r in candidate_undefined if r not in original_undefined]
    original_rel = relocations(args.original)
    candidate_rel = relocations(args.candidate)
    record(CHECKS[4], not added and len(candidate_rel) <= len(original_rel),
           {"added_undefined_symbols": added,
            "original_undefined_count": len(original_undefined),
            "candidate_undefined_count": len(candidate_undefined),
            "original_relocations": len(original_rel),
            "candidate_relocations": len(candidate_rel)})

    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    payload = {
        "gate": "V2",
        "kind": "interface",
        "scope": "binary",
        "schema_version": 1,
        "state": "passed" if passed == total else "failed",
        "passed": passed,
        "total": total,
        "checks": results,
        "method": "readelf -sW / --dyn-syms -W / -dW / -hW / -rW on both binaries; "
                  "the extracted rows are compared as normalised text",
        "original_sha256": __import__("hashlib").sha256(args.original.read_bytes()).hexdigest(),
        "candidate_sha256": __import__("hashlib").sha256(args.candidate.read_bytes()).hexdigest(),
        "does_not_prove": DOES_NOT_PROVE,
        "note": "Producer-side interface measurement. Route B's attempt_writer still "
                "maps V2 to not_run (attempt_writer.py:219), so an attempt assembled "
                "from a bundle reports required_check_not_run until V2 is wired there. "
                "This file records what was measured; accepting it as a gate result is "
                "the reviewer's decision, not this script's.",
    }

    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"\nV2 interface: {passed}/{total} checks passed")
    print(f"written: {args.out}" if args.out else "")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
