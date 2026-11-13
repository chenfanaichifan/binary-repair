#!/usr/bin/env python3
"""Probe the deterministic gate with structurally valid but semantically wrong
candidates.

This is an experiment, not a pass/fail claim: every case is generated through a
real AI-path protocol (assembly or direct bytes), the deterministic validator
accepts or rejects it, and the runtime/gate outcome is recorded.  Cases that
pass the gate despite a known semantic deviation are reported as blind spots.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai_assembly_repair import asm_repair  # noqa: E402
from app.services.ai_binary_repair import DIRECT_PATH, ai_repair  # noqa: E402
from app.services.binary_pipeline import detect_container  # noqa: E402
from app.services.repair.analyzer import analyze  # noqa: E402

ELF_I386 = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf"
ELF_MEMCPY = ROOT / "fixtures" / "elf" / "vuln-memcpy-x86.elf"

ASM_CORRECT_NO_PUTS = r"""
.intel_syntax noprefix
.text
.globl repair_entry
repair_entry:
    push ebp
    mov ebp, esp
    sub esp, 32
    mov eax, dword ptr [ebp+8]
    lea edx, [ebp-16]
    xor ecx, ecx
.Lloop:
    cmp ecx, 15
    jae .Ldone
    mov bl, byte ptr [eax+ecx]
    mov byte ptr [edx+ecx], bl
    test bl, bl
    je .Ldone
    inc ecx
    jmp .Lloop
.Ldone:
    mov byte ptr [edx+ecx], 0
    leave
    ret
"""

ASM_NOOP = r"""
.intel_syntax noprefix
.text
.globl repair_entry
repair_entry:
    ret
"""

ASM_NO_NUL = r"""
.intel_syntax noprefix
.text
.globl repair_entry
repair_entry:
    push ebp
    mov ebp, esp
    sub esp, 32
    mov eax, dword ptr [ebp+8]
    lea edx, [ebp-16]
    xor ecx, ecx
.Lloop:
    cmp ecx, 15
    jae .Ldone
    mov bl, byte ptr [eax+ecx]
    mov byte ptr [edx+ecx], bl
    inc ecx
    jmp .Lloop
.Ldone:
    leave
    ret
"""

ASM_WRONG_DEST = r"""
.intel_syntax noprefix
.text
.globl repair_entry
repair_entry:
    push ebp
    mov ebp, esp
    sub esp, 32
    mov eax, dword ptr [ebp+8]
    lea edx, [ebp-8]
    xor ecx, ecx
.Lloop:
    cmp ecx, 15
    jae .Ldone
    mov bl, byte ptr [eax+ecx]
    mov byte ptr [edx+ecx], bl
    test bl, bl
    je .Ldone
    inc ecx
    jmp .Lloop
.Ldone:
    mov byte ptr [edx+ecx], 0
    leave
    ret
"""


class FakeClient:
    model = "scripted-blind-spot"
    ai_mode = "scripted"

    def __init__(self, payload: dict):
        self.payload = payload

    def chat_json(self, messages, **kwargs):
        return SimpleNamespace(
            content=json.dumps(self.payload), model=self.model,
            usage={"prompt_tokens": 0, "completion_tokens": 0}, request_id="blind",
        )


def _sha(data: bytes | None) -> str | None:
    return hashlib.sha256(data).hexdigest() if data else None


def _asm_case(name: str, assembly: str, *, semantic_deviation: bool) -> dict:
    outcome = asm_repair(
        ELF_I386.read_bytes(), client=FakeClient({"schema_version": 1, "assembly": assembly}),
    )
    report = outcome.report
    return {
        "case": name,
        "path": "asm_roundtrip",
        "semantic_deviation": semantic_deviation,
        "candidate_sha256": _sha(outcome.candidate),
        "disposition": report.disposition,
        "verified": outcome.verified,
        "ai_status": outcome.ai.get("status"),
        "error": report.error,
        "gate": ((report.verification or {}).get("gate") or {}).get("outcome"),
        "gate_caught": bool(semantic_deviation and not outcome.verified),
        "blind_spot": bool(semantic_deviation and outcome.verified),
    }


def _direct_extra_edit_case() -> dict:
    data = ELF_MEMCPY.read_bytes()
    container = detect_container(data)
    sink = analyze(data).patchable()[0]
    length_offset = int(sink.length_offset)
    # Pick an executable byte outside the selected length immediate; the AI
    # validator accepts same-length edits anywhere in an executable section.
    extra_offset = None
    for section in container.sections:
        if not section.executable:
            continue
        start, end = int(section.offset), int(section.offset + section.size)
        for offset in range(start, min(end, len(data) - 1)):
            if offset in range(length_offset, length_offset + 4):
                continue
            if data[offset] != data[offset + 1]:
                extra_offset = offset
                break
        if extra_offset is not None:
            break
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "edits": [
            {
                "offset": length_offset,
                "before_hex": data[length_offset:length_offset + 4].hex(),
                "after_hex": (16).to_bytes(4, "little").hex(),
            },
            {
                "offset": extra_offset,
                "before_hex": data[extra_offset:extra_offset + 1].hex(),
                "after_hex": bytes([data[extra_offset] ^ 0x01]).hex(),
            },
        ],
    }
    outcome = ai_repair(data, path=DIRECT_PATH, client=FakeClient(payload))
    report = outcome.report
    return {
        "case": "direct_extra_unrelated_executable_edit",
        "path": "binary_direct",
        "semantic_deviation": True,
        "candidate_sha256": _sha(outcome.candidate),
        "disposition": report.disposition,
        "verified": outcome.verified,
        "ai_status": outcome.ai.get("status"),
        "error": report.error,
        "gate": ((report.verification or {}).get("gate") or {}).get("outcome"),
        "gate_caught": not outcome.verified,
        "blind_spot": bool(outcome.verified),
        "extra_offset": extra_offset,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    cases = [
        _asm_case("asm_correct_copy_without_puts_side_effect", ASM_CORRECT_NO_PUTS,
                  semantic_deviation=True),
        _asm_case("asm_noop_ret", ASM_NOOP, semantic_deviation=True),
        _asm_case("asm_copy_without_terminator", ASM_NO_NUL, semantic_deviation=True),
        _asm_case("asm_wrong_destination", ASM_WRONG_DEST, semantic_deviation=True),
        _direct_extra_edit_case(),
    ]
    summary = {
        "schema_version": 1,
        "note": (
            "Structurally valid but semantically deviant candidates.  "
            "gate_caught=True means the deterministic runtime/gate rejected or "
            "did not verify the candidate; blind_spot=True means it was verified."
        ),
        "cases": cases,
        "caught": sum(1 for case in cases if case["gate_caught"]),
        "blind_spots": sum(1 for case in cases if case["blind_spot"]),
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    sums = []
    for item in sorted(out.iterdir()):
        if item.is_file() and item.name != "SHA256SUMS":
            sums.append(f"{hashlib.sha256(item.read_bytes()).hexdigest()}  {item.name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
