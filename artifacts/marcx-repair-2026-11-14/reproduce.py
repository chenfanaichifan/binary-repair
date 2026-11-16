#!/usr/bin/env python3
"""Reproduce the MARCX1 capacity-check repair and its acceptance evidence.

Run from the repository root on macOS (Lima guest) or inside an x86-64 Linux
host with qemu-user.  Writes into this directory:

  marcx-fixed                  repaired ELF (sha256 93e27f2f...)
  patch-record.json            reviewed rewrite: bytes, disassembly, actions
  verification-report.json     deterministic gate packet for the accepted repair
  runtime-evidence.json        PoC/regression differential (original vs fixed)
  poc-manifest.json            the PoC/regression manifest used for the run
  challenge-suite.json         the challenge's own 16-case archive matrix
  SHA256SUMS                   digests of the generated evidence files

The repaired binary is only accepted when the deterministic gate passes with
the supplied PoC/regression manifest; the challenge suite is an independent,
outside-the-gate confirmation and is never used as acceptance evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = Path(__file__).resolve().parent
CHALLENGE = Path("/Users/huageorge/Documents/deepseek-harness/default-workspace/elf-challenge")
STAGE = Path.home() / ".br-guest-stage" / "marcx-accept"
ORIGINAL = ROOT / "fixtures" / "elf" / "vuln-capacity-confusion-x86_64.elf"
MANIFEST = ROOT / "fixtures" / "poc" / "marcx-capacity.json"
LIMA_INSTANCE = os.environ.get("BINARYREPAIR_LIMA_INSTANCE", "binaryrepair")

sys.path.insert(0, str(ROOT))
from app.services.repair.capacity import detect_capacity_confusion, repair_capacity_confusion  # noqa: E402
from app.services.poc_runner import run_poc  # noqa: E402


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _disassemble(data: bytes, offset: int, size: int, va: int) -> list[str]:
    from capstone import CS_ARCH_X86, CS_MODE_64, Cs

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    return [
        f"{ins.address:#x}: {ins.bytes.hex():<18} {ins.mnemonic:<8} {ins.op_str}"
        for ins in md.disasm(data[offset:offset + size], va)
    ]


def _write(name: str, payload: dict | str) -> None:
    path = ART / name
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _run_guest(executable: Path, argv: list[str]) -> dict:
    if shutil.which("limactl"):
        command = ["limactl", "shell", LIMA_INSTANCE, "--", str(executable), *argv]
    else:
        command = [str(executable), *argv]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
    crashed = (
        proc.returncode < 0
        or "target signal" in proc.stderr
        or "Segmentation fault" in proc.stderr
    )
    return {
        "exit_code": proc.returncode,
        "crashed": crashed,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main() -> int:
    original = ORIGINAL.read_bytes()
    assert _sha(original) == "72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5"
    patched, report = repair_capacity_confusion(original)
    assert patched is not None, report.limitations
    assert _sha(patched) == "93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2"

    (ART / "marcx-fixed").write_bytes(patched)
    os.chmod(ART / "marcx-fixed", 0o755)
    shutil.copy2(MANIFEST, ART / "poc-manifest.json")

    action = report.actions[0]
    patch_record = {
        "schema_version": 1,
        "original_sha256": report.original_sha256,
        "patched_sha256": report.patched_sha256,
        "format": report.format,
        "arch": report.arch,
        "strategy": report.strategy,
        "mode": report.mode,
        "status": report.status,
        "sites": [site.to_dict() for site in report.sites],
        "actions": [item.to_dict() for item in report.actions],
        "message_actions": list(report.message_actions),
        "before_disassembly": _disassemble(original, action.offset, action.size, action.site_va),
        "after_disassembly": _disassemble(patched, action.offset, action.size, action.site_va),
        "limitations": list(report.limitations),
    }
    _write("patch-record.json", patch_record)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    evidence = run_poc(original, patched, manifest)
    if evidence.status != "pass":
        print("PoC differential did not pass:", evidence.to_dict(), file=sys.stderr)
        return 1
    _write("runtime-evidence.json", evidence.to_dict())

    from app.services.binary_review import run_direct_repair

    outcome = run_direct_repair(
        original, request_review=False, client=None,
        data_dir=tempfile.mkdtemp(prefix="marcx-accept-"), poc_manifest=manifest,
    )
    verification = outcome.verification
    assert verification is not None and verification.gate.success is True
    _write("verification-report.json", {
        "schema_version": 1,
        "accepted": True,
        "gate": json.loads(json.dumps(verification.packet.get("gate"))),
        "scope": verification.packet.get("scope"),
        "checks": verification.packet.get("checks"),
        "patch": verification.packet.get("patch"),
        "candidate": verification.packet.get("candidate"),
        "runtime": verification.packet.get("runtime"),
        "poc_native": verification.packet.get("poc_native"),
        "report": outcome.report.to_dict(),
    })

    # Independent outside-the-gate confirmation against the challenge suite.
    STAGE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ORIGINAL, STAGE / "original.marcx")
    shutil.copy2(ART / "marcx-fixed", STAGE / "fixed.marcx")
    os.chmod(STAGE / "original.marcx", 0o755)
    os.chmod(STAGE / "fixed.marcx", 0o755)
    cases = [
        ("benign.marc", CHALLENGE / "build/testdata/benign.marc", []),
        ("benign_sparse.marc", CHALLENGE / "build/testdata/benign_sparse.marc", []),
        ("benign_crc.marc", CHALLENGE / "poc/build/benign_crc.marc", []),
        ("ctrl_span_equal_sizes.marc", CHALLENGE / "poc/build/ctrl_span_equal_sizes.marc", []),
        ("bad_crc.marc", CHALLENGE / "poc/build/bad_crc.marc", []),
        ("ctrl_literal_dst_oob.marc", CHALLENGE / "poc/build/ctrl_literal_dst_oob.marc", []),
        ("ctrl_span_no_sparse.marc", CHALLENGE / "poc/build/ctrl_span_no_sparse.marc", []),
        ("ctrl_span_src_oob.marc", CHALLENGE / "poc/build/ctrl_span_src_oob.marc", []),
        ("poc_overflow.marc", CHALLENGE / "build/testdata/poc_overflow.marc", []),
        ("poc_overflow_nocrc.marc", CHALLENGE / "build/testdata/poc_overflow_nocrc.marc", []),
        ("poc_span_note.marc", CHALLENGE / "poc/build/poc_span_note.marc", []),
        ("poc_span_note_min.marc", CHALLENGE / "poc/build/poc_span_note_min.marc", []),
        ("poc_span_min.marc", CHALLENGE / "poc/build/poc_span_min.marc", []),
        ("poc_span_oob.marc", CHALLENGE / "poc/build/poc_span_oob.marc", []),
        ("poc_overflow--list", CHALLENGE / "build/testdata/poc_overflow.marc", ["--list"]),
        ("poc_overflow--dump-index", CHALLENGE / "build/testdata/poc_overflow.marc", ["--dump-index"]),
    ]
    rows = []
    for name, source, extra in cases:
        target = STAGE / name.split("--")[0]
        shutil.copy2(source, target)
        before = _run_guest(STAGE / "original.marcx", [*extra, str(target)])
        after = _run_guest(STAGE / "fixed.marcx", [*extra, str(target)])
        identical = (
            before["exit_code"] == after["exit_code"]
            and before["stdout"] == after["stdout"]
            and before["stderr"] == after["stderr"]
        )
        if identical:
            disposition = "unchanged"
        elif before["crashed"] and after["exit_code"] == 1:
            disposition = "previously_crashing_now_rejected"
        elif before["exit_code"] == 0 and after["exit_code"] == 1:
            disposition = "invalid_input_now_rejected"
        else:
            disposition = "changed"
        rows.append({
            "case": name,
            "argv_extra": extra,
            "original": before,
            "fixed": after,
            "identical": identical,
            "disposition": disposition,
        })
        print(f"{name:24s} orig={before['exit_code']:4d} fixed={after['exit_code']:4d} {disposition}")
    _write("challenge-suite.json", {
        "schema_version": 1,
        "scope": "outside-the-gate confirmation; not acceptance authority",
        "expected": {
            "unchanged": "benign, CRC and differential-control archives render/reject exactly as before",
            "previously_crashing_now_rejected": "the overflow archive is rejected before the copy",
            "invalid_input_now_rejected": "an archive with an out-of-bounds span destination (silent 1-byte overflow in the original) is rejected",
            "changed": "unexpected",
        },
        "cases": rows,
        "all_expected": all(row["disposition"] != "changed" for row in rows),
    })

    digests = []
    for name in sorted(
        path.name for path in ART.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    ):
        digests.append(f"{_sha((ART / name).read_bytes())}  {name}")
    (ART / "SHA256SUMS").write_text("\n".join(digests) + "\n", encoding="utf-8")
    print("wrote artifacts to", ART)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
