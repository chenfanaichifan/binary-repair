#!/usr/bin/env python3
"""Scripted acceptance evidence for the two AI direct-binary repair paths.

This is intentionally a *scripted* model: it proves the protocol, validators,
writer integration and deterministic gate, not the quality of a particular LLM.
No network/provider is used.  Run with ``--out`` to build the evidence bundle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai_binary_repair import (  # noqa: E402
    AI_PATHS,
    ASM_PATH,
    DIRECT_PATH,
    ai_repair,
)
from app.services.binary_pipeline import repair_any  # noqa: E402
from app.services.containers import detect_container  # noqa: E402
from app.services.repair.analyzer import analyze  # noqa: E402
from app.services.repair.guards import abi_for, build_guard  # noqa: E402

FIXTURES = (
    ("pe-x86_64-guard", ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"),
    ("pe-arm64-guard", ROOT / "fixtures" / "pe" / "vuln-strcpy-arm64.exe"),
    ("elf-i386-guard", ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf"),
    ("elf-x86_64-guard", ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"),
    ("elf-arm64-guard", ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf"),
    ("elf-i386-memcpy", ROOT / "fixtures" / "elf" / "vuln-memcpy-x86.elf"),
)
if platform.system() == "Darwin":
    FIXTURES += (
        ("macho-x86_64-guard", ROOT / "fixtures" / "macho" / "vuln-strcpy-x86_64"),
        ("macho-arm64-guard", ROOT / "fixtures" / "macho" / "vuln-strcpy-arm64"),
    )

ASM_I386 = r"""
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

ASM_X86_64 = r"""
.intel_syntax noprefix
.text
.globl repair_entry
repair_entry:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov rsi, rdi
    lea rdi, [rbp-16]
    xor ecx, ecx
.Lloop:
    cmp ecx, 15
    jae .Ldone
    mov al, byte ptr [rsi+rcx]
    mov byte ptr [rdi+rcx], al
    test al, al
    je .Ldone
    inc ecx
    jmp .Lloop
.Ldone:
    mov byte ptr [rdi+rcx], 0
    leave
    ret
"""

ASM_ARM64 = r"""
.text
.globl repair_entry
repair_entry:
    sub sp, sp, #32
    add x2, sp, #16
    mov x3, #0
.Lloop:
    cmp x3, #15
    b.hs .Ldone
    ldrb w4, [x0, x3]
    strb w4, [x2, x3]
    cbz w4, .Ldone
    add x3, x3, #1
    b .Lloop
.Ldone:
    strb wzr, [x2, x3]
    add sp, sp, #32
    ret
"""


class ScriptedClient:
    """Deterministic stand-in for a model; records the packet it saw."""

    ai_mode = "scripted"
    ai_provider = "scripted"
    model = "scripted-binary-repair"

    def __init__(self, payload: dict):
        self.payload = payload
        self.packet: dict | None = None

    def chat_json(self, messages, **kwargs):
        self.packet = json.loads(messages[-1]["content"])
        return SimpleNamespace(
            content=json.dumps(self.payload),
            model=self.model,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            request_id="scripted",
        )


def _asm_payload(data: bytes) -> dict | None:
    container = detect_container(data)
    if container.format != "elf" or container.arch not in {"i386", "x86_64", "arm64"}:
        return None
    sink = analyze(data).patchable()[0]
    if sink.kind != "unbounded_copy":
        return None
    assembly = {
        "i386": ASM_I386,
        "x86_64": ASM_X86_64,
        "arm64": ASM_ARM64,
    }[container.arch]
    return {"schema_version": 1, "assembly": assembly}


def _bytes_payload(data: bytes) -> dict:
    container = detect_container(data)
    sink = analyze(data).patchable()[0]
    if sink.kind == "unbounded_copy":
        abi = abi_for(container.format, container.arch)
        code = build_guard(abi, sink.callee, int(sink.capacity or 0))
        return {
            "schema_version": 1,
            "sink_index": 0,
            "inject": {"code_hex": code.hex()},
        }
    width = 4
    offset = int(sink.length_offset or 0)
    before = data[offset:offset + width]
    after = int(sink.capacity or 0).to_bytes(width, "little")
    return {
        "schema_version": 1,
        "sink_index": 0,
        "edits": [{
            "offset": offset,
            "before_hex": before.hex(),
            "after_hex": after.hex(),
        }],
    }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record(path: str, data: bytes, outcome, fixture: Path | None = None,
            deterministic: dict | None = None) -> dict:
    report = outcome.report
    packet_sha = None
    if isinstance(report.ai.get("validation"), dict):
        packet_sha = report.ai.get("plan_sha256")
    return {
        "path": path,
        "input": str(fixture) if fixture is not None else "",
        "input_sha256": _sha(data),
        "candidate_sha256": _sha(outcome.candidate) if outcome.candidate else None,
        "verified": outcome.verified,
        "download_allowed": outcome.download_allowed,
        "disposition": report.disposition,
        "status": report.status,
        "strategy": report.strategy,
        "actions": report.actions,
        "ai": outcome.ai,
        "verification": report.verification,
        "runtime": report.runtime,
        "limitations": report.limitations,
        "warnings": report.warnings,
        "deterministic_baseline": deterministic,
        "report": report.to_dict(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    paths = list(AI_PATHS)
    records: dict[str, dict] = {}
    for name, fixture in FIXTURES:
        if not fixture.is_file():
            print(json.dumps({"skipped": str(fixture)}))
            continue
        data = fixture.read_bytes()
        baseline = repair_any(data)
        baseline_sha = (
            hashlib.sha256(baseline.candidate).hexdigest()
            if baseline.candidate is not None else None
        )
        deterministic = {
            "disposition": baseline.report.disposition,
            "verified": baseline.verified,
            "candidate_sha256": baseline_sha,
        }
        for path in paths:
            if path == ASM_PATH:
                payload = _asm_payload(data)
                if payload is None:
                    continue
            else:
                payload = _bytes_payload(data)
            client = ScriptedClient(payload)
            outcome = ai_repair(data, path=path, client=client)
            record = _record(path, data, outcome, fixture, deterministic)
            record["fixture"] = name
            record["client_packet_keys"] = sorted(client.packet or {})
            target = out / f"{path}-{name}.json"
            target.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
            records[f"{path}:{name}"] = record
            print(json.dumps({
                "fixture": name, "path": path,
                "disposition": record["disposition"],
                "verified": record["verified"],
                "candidate_sha256": record["candidate_sha256"],
            }, ensure_ascii=False))
    # Negative control: a structurally valid but semantically empty injected
    # guard must be refused by the deterministic runtime gate.
    pe = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"
    if pe.is_file():
        client = ScriptedClient({"schema_version": 1, "sink_index": 0,
                                 "inject": {"code_hex": "c3"}})
        outcome = ai_repair(pe.read_bytes(), path=DIRECT_PATH, client=client)
        record = _record(DIRECT_PATH, pe.read_bytes(), outcome, pe)
        record["fixture"] = "pe-x86_64-guard"
        record["negative_control"] = "no-op injected guard must not be verified"
        (out / "negative-bytes-noop-guard.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
        )
        print(json.dumps({"negative_control": "no-op guard",
                          "verified": outcome.verified,
                          "disposition": outcome.report.disposition}, ensure_ascii=False))
        summary_negative = {
            "fixture": "pe-x86_64-guard",
            "verified": outcome.verified,
            "disposition": outcome.report.disposition,
            "candidate_sha256": None,
        }
    else:
        summary_negative = None
    summary = {
        "schema_version": 1,
        "provider": "scripted",
        "note": (
            "Scripted deterministic model; proves the two AI repair protocols, "
            "validators, direct byte writeback and deterministic gate.  It does "
            "not measure LLM quality and performs no network call."
        ),
        "paths": list(paths),
        "no_assembly_or_decompile_roundtrip": True,
        "negative_control": summary_negative,
        "measured_increment": (
            "not measured: the scripted model is a deterministic stand-in.  "
            "Direct-path candidates coincide with the v5 deterministic baseline; "
            "assembly-path candidates differ in representation but do not prove "
            "extra vulnerability coverage.  A real-provider, gate-blind/PoC "
            "increment experiment remains future work."
        ),
        "records": {
            key: {
                "disposition": value["disposition"],
                "verified": value["verified"],
                "candidate_sha256": value["candidate_sha256"],
                "deterministic_disposition": (value.get("deterministic_baseline") or {}).get("disposition"),
                "deterministic_candidate_sha256": (value.get("deterministic_baseline") or {}).get("candidate_sha256"),
                "same_candidate_as_deterministic": (
                    value["candidate_sha256"] is not None
                    and value["candidate_sha256"] == (value.get("deterministic_baseline") or {}).get("candidate_sha256")
                ),
            }
            for key, value in records.items()
        },
    }
    (out / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    sums = []
    for item in sorted(out.iterdir()):
        if item.is_file() and item.name != "SHA256SUMS":
            sums.append(f"{hashlib.sha256(item.read_bytes()).hexdigest()}  {item.name}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "records": len(records),
                      "all_verified": all(v["verified"] for v in records.values())},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
