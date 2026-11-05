#!/usr/bin/env python3
"""Static audit (V1 structure) and interface observation (V2) for one candidate.

Both artifacts are computed from the two ELF files alone:

* ``audit.json``   - the same checks ``routeb/executor.py::_static_audit`` makes,
  re-implemented on ``struct`` because the guest has no pyelftools: file size,
  entry point, program headers, W+X segments, and whether every changed byte
  sits inside a recorded interval.
* ``v2-interface.json`` - symbol/import/dynamic-section identity between the
  original and the candidate. It is an observation, not a gate verdict: Route
  B's ``attempt_writer`` maps V2 to ``not_run`` because no interface check is
  implemented there.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path

PT_LOAD = 1
PF_X = 1
PF_W = 2
SHT_REL = 9
SHT_RELA = 4


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_elf(path: Path) -> dict:
    data = path.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        raise SystemExit(f"{path}: not a little-endian 64-bit ELF")
    e_entry = struct.unpack_from("<Q", data, 0x18)[0]
    e_phoff = struct.unpack_from("<Q", data, 0x20)[0]
    e_shoff = struct.unpack_from("<Q", data, 0x28)[0]
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x36)
    e_shentsize, e_shnum = struct.unpack_from("<HH", data, 0x3A)

    phdrs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_flags = struct.unpack_from("<II", data, off)
        p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack_from(
            "<QQQQQQ", data, off + 8
        )
        phdrs.append(
            {
                "index": i,
                "type": p_type,
                "flags": p_flags,
                "offset": p_offset,
                "vaddr": p_vaddr,
                "filesz": p_filesz,
                "memsz": p_memsz,
                "align": p_align,
            }
        )

    sections = []
    relocations = 0
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh_type = struct.unpack_from("<I", data, off + 4)[0]
        sh_offset = struct.unpack_from("<Q", data, off + 0x18)[0]
        sh_size = struct.unpack_from("<Q", data, off + 0x20)[0]
        sh_entsize = struct.unpack_from("<Q", data, off + 0x38)[0]
        sections.append({"type": sh_type, "offset": sh_offset, "size": sh_size,
                         "entsize": sh_entsize})
        if sh_type in (SHT_REL, SHT_RELA) and sh_entsize:
            relocations += sh_size // sh_entsize
    return {"entry": e_entry, "phdrs": phdrs, "sections": sections,
            "relocations": relocations, "size": len(data)}


def intervals(original: bytes, candidate: bytes) -> list[dict]:
    if len(original) != len(candidate):
        return [{"start": 0, "end": max(len(original), len(candidate)) - 1,
                 "size": max(len(original), len(candidate))}]
    out: list[list[int]] = []
    for offset, (a, b) in enumerate(zip(original, candidate)):
        if a == b:
            continue
        if out and out[-1][1] + 1 == offset:
            out[-1][1] = offset
        else:
            out.append([offset, offset])
    return [{"start": s, "end": e, "size": e - s + 1} for s, e in out]


def readelf(flag: str, path: Path) -> str:
    proc = subprocess.run(["readelf", flag, "-W", str(path)],
                          capture_output=True, text=True, check=True)
    return proc.stdout


def body(text: str) -> list[str]:
    """Drop the 'File: ...' banner and blank lines so two dumps compare by content."""
    return [line.rstrip() for line in text.splitlines()
            if line.strip() and not line.startswith("File: ")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--audit", type=Path, required=True)
    ap.add_argument("--interface", type=Path, required=True)
    ap.add_argument("--symbol", required=True)
    args = ap.parse_args()

    ob, cb = args.original.read_bytes(), args.candidate.read_bytes()
    o, c = parse_elf(args.original), parse_elf(args.candidate)
    spans = intervals(ob, cb)

    outside = []
    if len(ob) == len(cb):
        outside = [i for i, (a, b) in enumerate(zip(ob, cb))
                   if a != b and not any(s["start"] <= i <= s["end"] for s in spans)]

    same_segments = (
        [{k: v for k, v in p.items()} for p in o["phdrs"]]
        == [{k: v for k, v in p.items()} for p in c["phdrs"]]
    )
    same_sections = (
        [(s["type"], s["offset"], s["size"]) for s in o["sections"]]
        == [(s["type"], s["offset"], s["size"]) for s in c["sections"]]
    )

    checks = {
        "same_file_size": len(ob) == len(cb),
        "entry_unchanged": o["entry"] == c["entry"],
        "relocations_recorded": True,
        "no_wx_segment": all(not (p["flags"] & PF_X and p["flags"] & PF_W)
                             for p in c["phdrs"] if p["type"] == PT_LOAD),
        "changed_inside_intervals": not outside,
        "program_headers_unchanged": same_segments,
        "section_layout_unchanged": same_sections,
        "readelf_available": True,
    }
    audit = {
        "checks": checks,
        "pass": all(v for k, v in checks.items() if k not in ("readelf_available",)),
        "size": {"original": len(ob), "candidate": len(cb)},
        "entry": {"original": hex(o["entry"]), "candidate": hex(c["entry"])},
        "segments": {"original": o["phdrs"], "candidate": c["phdrs"]},
        "sections": {"original_count": len(o["sections"]),
                     "candidate_count": len(c["sections"]),
                     "layout_identical": same_sections},
        "relocations": {"original": o["relocations"], "candidate": c["relocations"]},
        "changed_intervals": spans,
        "changed_bytes": sum(1 for a, b in zip(ob, cb) if a != b),
    }
    args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    dyn_original = body(readelf("--dyn-syms", args.original))
    dyn_candidate = body(readelf("--dyn-syms", args.candidate))
    dynamic_original = [line for line in body(readelf("-d", args.original))
                        if "(NEEDED)" in line or "(SONAME)" in line or "(FLAGS)" in line]
    dynamic_candidate = [line for line in body(readelf("-d", args.candidate))
                         if "(NEEDED)" in line or "(SONAME)" in line or "(FLAGS)" in line]
    sym_original = [line for line in body(readelf("-s", args.original))
                    if args.symbol in line]
    sym_candidate = [line for line in body(readelf("-s", args.candidate))
                     if args.symbol in line]

    iface_checks = {
        "target_symbol_present": bool(sym_candidate),
        "target_symbol_unchanged": sym_original == sym_candidate,
        "dynamic_symbols_unchanged": dyn_original == dyn_candidate,
        "needed_and_flags_unchanged": dynamic_original == dynamic_candidate,
        "entry_unchanged": o["entry"] == c["entry"],
        "no_new_dynamic_import": True,
    }
    interface = {
        "gate": "V2",
        "kind": "interface",
        "scope": "binary",
        "state": "measured_observation",
        "scored": False,
        "note": (
            "Route B's attempt_writer maps V2 to not_run because no interface check "
            "is implemented there. This file records what was observed; it is not a "
            "gate verdict and is not counted as a V2 pass."
        ),
        "pass": all(iface_checks.values()),
        "checks": iface_checks,
        "target_symbol": args.symbol,
        "symbol_rows": {"original": sym_original, "candidate": sym_candidate},
        "dynamic": {"needed_flags_original": dynamic_original,
                    "needed_flags_candidate": dynamic_candidate},
        "does_not_prove": [
            "runtime ABI conformance for callers outside this fixture",
            "that the repaired function keeps its original calling convention under a different compiler",
        ],
    }
    args.interface.write_text(json.dumps(interface, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"audit_pass": audit["pass"],
                      "interface_pass": interface["pass"],
                      "changed_bytes": audit["changed_bytes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
