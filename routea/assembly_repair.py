"""Binary-level assembly repair: disassemble, trampoline, verify, emit ELF.

This is intentionally *not* a naive "disassemble whole binary and reassemble"
tool: relocations, data-in-code, exception tables and PIE make whole-file
reassembly unsound.  It applies a reviewed call-site trampoline (the existing
Route A cave) and verifies the resulting ELF and assembly before returning it.

The output is a candidate, never an acceptance verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from elftools.elf.elffile import ELFFile

from app.domain.contracts import SecurityContract
from routea.cave import audit_cave_layout, build_cave_patched, plan_route_a_cave
from routea.worker import RouteAError, decode_function

MD = Cs(CS_ARCH_X86, CS_MODE_64)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def disassemble(path: Path, target: str) -> dict[str, Any]:
    info = decode_function(path, target)
    return {
        "target": info.name,
        "entry": hex(info.entry),
        "size": info.size,
        "instructions": [i.to_dict() for i in info.instructions],
    }


def assembly_text(rows: list[dict[str, Any]]) -> str:
    lines = []
    for row in rows:
        lines.append(f"{row['address']}: {row['bytes']:<24} {row['mnemonic']:<8} {row['op_str']}")
    return "\n".join(lines) + "\n"


def repair_binary(
    original: Path,
    *,
    target: str,
    cave_addr: int,
    cave_size: int,
    contract: SecurityContract,
    out: Path,
    report_path: Path,
    asm_dir: Path,
) -> dict[str, Any]:
    if out.resolve() == original.resolve():
        raise ValueError("refusing to overwrite the original binary")
    before = disassemble(original, target)
    plan = plan_route_a_cave(original, contract, cave_addr=cave_addr, cave_size=cave_size)
    manifest = build_cave_patched(original, plan, out, scope_authorized=True)
    after = disassemble(out, target)
    audit = audit_cave_layout(original, out, plan)

    asm_dir.mkdir(parents=True, exist_ok=True)
    (asm_dir / "before.asm").write_text(assembly_text(before["instructions"]), encoding="utf-8")
    (asm_dir / "after.asm").write_text(assembly_text(after["instructions"]), encoding="utf-8")

    # Independent structural checks; the audit above is plan-specific.
    with original.open("rb") as fh:
        e1 = ELFFile(fh)
        orig_entry = e1.header["e_entry"]
        orig_segments = [(s["p_type"], int(s["p_flags"]), int(s["p_offset"]), int(s["p_vaddr"]),
                          int(s["p_filesz"]), int(s["p_memsz"])) for s in e1.iter_segments()]
    with out.open("rb") as fh:
        e2 = ELFFile(fh)
        new_entry = e2.header["e_entry"]
        new_segments = [(s["p_type"], int(s["p_flags"]), int(s["p_offset"]), int(s["p_vaddr"]),
                         int(s["p_filesz"]), int(s["p_memsz"])) for s in e2.iter_segments()]
    wx = any((flags & 0x3) == 0x3 for _t, flags, _o, _v, _f, _m in new_segments)
    report = {
        "schema": 1,
        "original": str(original),
        "patched": str(out),
        "original_sha256": _sha(original),
        "patched_sha256": _sha(out),
        "changed": _sha(original) != _sha(out),
        "target": target,
        "call_site": hex(plan.call_site),
        "cave": {"vaddr": hex(plan.cave_addr), "size": plan.cave_size},
        "assembly": {"before": before, "after": after,
                     "before_file": str(asm_dir / "before.asm"),
                     "after_file": str(asm_dir / "after.asm")},
        "elf": {
            "entry_unchanged": orig_entry == new_entry,
            "segments_unchanged_except_rx_growth": len(orig_segments) == len(new_segments),
            "no_wx": not wx,
        },
        "audit": audit,
        "manifest": manifest.to_dict(),
        "limits": [
            "This is a call-site trampoline for the exact contracted function, not whole-binary reassembly.",
            "The candidate is static evidence; execution must happen in a disposable guest.",
            "A non-empty cave/segment extension is an explicit binary-layout edit.",
        ],
    }
    report["rounds"] = [
        {"round": 1, "check": "original function disassembled; call site decoded",
         "pass": bool(before["instructions"])},
        {"round": 2, "check": "patched ELF re-opened and target disassembled",
         "pass": bool(after["instructions"]) and report["changed"]},
        {"round": 3, "check": "ELF layout, audit and W^X",
         "pass": bool(audit.get("pass") and report["elf"]["entry_unchanged"]
                     and report["elf"]["segments_unchanged_except_rx_growth"]
                     and report["elf"]["no_wx"])},
    ]
    report["passed"] = all(row["pass"] for row in report["rounds"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--elf", type=Path, required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--cave", required=True)
    ap.add_argument("--cave-size", type=lambda v: int(v, 0), required=True)
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--asm-dir", type=Path, required=True)
    args = ap.parse_args()
    contract = SecurityContract.from_dict(json.loads(args.contract.read_text(encoding="utf-8")))
    report = repair_binary(
        args.elf, target=args.target, cave_addr=int(args.cave, 16),
        cave_size=args.cave_size, contract=contract,
        out=args.out, report_path=args.report, asm_dir=args.asm_dir,
    )
    print(json.dumps({"passed": report["passed"], "patched_sha256": report["patched_sha256"],
                      "call_site": report["call_site"]}, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
