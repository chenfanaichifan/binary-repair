#!/usr/bin/env python3
"""Hard-case AI increment benchmark (real provider, target-function mode).

Deterministic baseline and AI assembly-target repair are run on cases whose
sink is deliberately outside the deterministic analyzer's templates.  The only
acceptance authority is the native/qemu PoC+regression runner.  The script also
supports --reference to validate the harness with a known-good assembly fix.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.ai_assembly_repair import (  # noqa: E402
    ASM_MAX_TOKENS, ASM_SYSTEM_PROMPT, _assemble, _assembly_packet,
    _apply_call_relocations, _assemble_with_relocations, _disassemble_function,
    _inject_blob, _patch_binary_call_relocations, _redirect_function,
    _validate_assembly_text, _validate_code,
)
from app.services.ai_binary_repair import _ai_base, _call_model, _sha  # noqa: E402
from app.services.binary_pipeline import repair_any  # noqa: E402
from app.services.containers import detect_container  # noqa: E402
from app.services.poc_runner import run_poc  # noqa: E402
from app.services.repair.analyzer import Sink  # noqa: E402
from app.services.repair.call_targets import discover_allowed_calls  # noqa: E402
from app.services.repair.writer import repair_with_sinks  # noqa: E402


def _target_va(container: Any, target: str) -> int | None:
    symbols = getattr(container, "symbols", {}) or {}
    for va, name in symbols.items():
        if name == target:
            return int(va)
    for va, name in symbols.items():
        if target in str(name):
            return int(va)
    return None


def _inject_target(data: bytes, target: str, capacity: int, assembly: str,
                   allowed_calls: list[Any] | None = None) -> tuple[bytes | None, dict[str, Any]]:
    allowed_calls = list(allowed_calls or [])
    container = detect_container(data)
    va = _target_va(container, target)
    if va is None:
        return None, {"error": f"target {target!r} not found"}
    sink = Sink(
        kind="unbounded_copy", arch=container.arch, function_va=va,
        capacity=capacity, patchable=True,
    )
    try:
        clean = _validate_assembly_text(assembly, container.arch, allowed_calls)
        if allowed_calls:
            code, relocs = _assemble_with_relocations(clean, container.arch)
        else:
            code, relocs = _assemble(clean, container.arch), []
    except Exception as exc:  # noqa: BLE001
        return None, {"error": f"assembly validation: {type(exc).__name__}: {exc}"}
    patched, cave_va, method = _inject_blob(container, data, code)
    if patched is None or cave_va is None:
        return None, {"error": f"injection failed: {method}"}
    try:
        if relocs:
            patched = _patch_binary_call_relocations(
                patched, cave_va, container.arch, code, relocs, allowed_calls,
            )
            resolved = _apply_call_relocations(
                code, container.arch, int(cave_va), relocs, allowed_calls,
            )
            _validate_code(resolved, container.arch, allowed_calls, base_va=int(cave_va))
        else:
            _validate_code(code, container.arch)
    except Exception as exc:  # noqa: BLE001
        return None, {"error": f"call relocation: {type(exc).__name__}: {exc}"}
    patched = _redirect_function(patched, container, sink, cave_va)
    if patched is None:
        return None, {"error": "function entry redirect failed"}
    return patched, {
        "target_va": hex(va), "cave_va": hex(cave_va), "method": method,
        "code_bytes": len(code), "assembly_sha256": hashlib.sha256(clean.encode()).hexdigest(),
        "call_targets": [getattr(item, "to_dict", lambda: {})() for item in allowed_calls],
        "call_relocations": len(relocs),
    }


def _prompt_packet(data: bytes, target: str, capacity: int, contract: str,
                   contract_level: str = "full",
                   allowed_calls: list[Any] | None = None) -> dict[str, Any]:
    container = detect_container(data)
    va = _target_va(container, target)
    if va is None:
        raise ValueError(f"target not found: {target}")
    sink = Sink(kind="unbounded_copy", arch=container.arch, function_va=va,
                capacity=capacity, patchable=True)
    listing = _disassemble_function(data, container, sink)
    allowed_calls = list(allowed_calls or [])
    packet = _assembly_packet(data, container, sink, listing, allowed_calls)
    packet["target_function"] = target
    call_rule = (
        "no external calls, syscalls, privileged instructions or indirect jumps"
        if not allowed_calls else
        "only direct calls to the exact target addresses in allowed_calls are allowed; "
        "no other calls, syscalls, privileged instructions or indirect jumps"
    )
    if contract_level == "full":
        packet["hard_case_contract"] = contract
        packet["rules"] = [
            "return a complete replacement function assembly",
            "preserve the calling convention and write at most capacity-1 bytes plus NUL",
            "preserve the observable behaviour for valid inputs",
            call_rule,
            "terminate with ret",
        ]
    elif contract_level == "generic":
        packet["hard_case_contract"] = (
            "Repair the vulnerability in the target function while preserving its "
            "normal observable behaviour."
        )
        packet["rules"] = [
            "return a complete replacement function assembly",
            "preserve the calling convention and observable behaviour",
            call_rule,
            "terminate with ret",
        ]
        packet["sink"] = {"kind": "unbounded_copy"}
    else:  # none: target and disassembly only; no repair-strategy contract
        packet.pop("hard_case_contract", None)
        packet["sink"] = {"kind": "unbounded_copy"}
        packet["rules"] = [
            "return a complete replacement function assembly",
            call_rule,
            "terminate with ret",
        ]
    return packet


def _baseline_target_attempt(data: bytes, target: str, capacity: int, poc: dict) -> dict[str, Any]:
    """Give the deterministic writer the same target/function hint.

    It is still template-driven; the attempt is recorded rather than claimed.
    """
    container = detect_container(data)
    va = _target_va(container, target)
    if va is None:
        return {"attempted": False, "reason": "target not found"}
    sink = Sink(kind="unbounded_copy", arch=container.arch, function_va=va,
                capacity=capacity, patchable=True)
    try:
        result = repair_with_sinks(data, container, [sink])
    except Exception as exc:  # noqa: BLE001
        return {"attempted": True, "verified": False,
                "reason": f"{type(exc).__name__}: {exc}"}
    if result.patched is None:
        return {"attempted": True, "verified": False,
                "reason": result.limitations[-1] if result.limitations else "no candidate"}
    evidence = _evaluate(data, result.patched, poc, {})
    return {
        "attempted": True,
        "verified": evidence.get("gate") == "pass",
        "gate": evidence.get("gate"),
        "reason": "",
    }


def _fake_client(assembly: str) -> Any:
    class FakeClient:
        model = "scripted-reference"
        ai_mode = "scripted"

        def chat_json(self, messages, **kwargs):
            return SimpleNamespace(
                content=json.dumps({"schema_version": 1, "assembly": assembly}),
                model=self.model, usage={}, request_id="reference",
            )
    return FakeClient()


def _evaluate(data: bytes, patched: bytes | None, poc: dict, case: dict) -> dict:
    if patched is None:
        return {"gate": "no_candidate", "poc_status": "not_run"}
    evidence = run_poc(data, patched, poc)
    return {
        "gate": "pass" if evidence.passed else "fail",
        "poc_status": evidence.status,
        "runner": evidence.runner,
        "candidate_sha256": _sha(patched),
        "poc": evidence.to_dict(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--client", choices=("real", "reference"), default="real")
    ap.add_argument("--case", default="")
    ap.add_argument("--contract-level", choices=("full", "generic", "none"), default="full")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--allow-calls", action="store_true",
                    help="allow only calls already present in the target function")
    args = ap.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    cases = json.loads((ROOT / "fixtures" / "hard-cases" / "cases.json").read_text())["cases"]
    if args.case:
        cases = [case for case in cases if case["id"] == args.case]
    client = None
    if args.client == "real":
        from app.services.assistant_llm import client_from_env
        client = client_from_env()
    results = []
    for case in cases:
        data = (ROOT / case["binary"]).read_bytes()
        poc = json.loads((ROOT / case["poc"]).read_text())
        baseline = repair_any(data, verify=True)
        record: dict[str, Any] = {
            "case": case,
            "input_sha256": _sha(data),
            "baseline": {
                "disposition": baseline.report.disposition,
                "verified": baseline.verified,
                "error": baseline.report.error,
            },
            "baseline_increment_zero": not baseline.verified,
            "baseline_target_aware": _baseline_target_attempt(
                data, case["target"], int(case["capacity"]), poc,
            ),
            "ai_blind": None,
        }
        if client is not None:
            from app.services.ai_binary_repair import ASM_PATH, ai_repair
            blind = ai_repair(data, path=ASM_PATH, client=client, verify=True)
            record["ai_blind"] = {
                "status": blind.ai.get("status"),
                "disposition": blind.report.disposition,
                "verified": blind.verified,
            }
        assembly = None
        ai_meta: dict[str, Any] = _ai_base("hard_target_asm")
        injection: dict[str, Any] = {}
        if args.client == "reference":
            reference = (ROOT / case["reference_fix"])
            if reference.suffix == ".S":
                assembly = reference.read_text(encoding="utf-8")
            else:
                ai_meta.update({"status": "not_attempted", "error": "reference is not assembly"})
        else:
            ai_meta = _ai_base("hard_target_asm")
            if client is None:
                ai_meta.update({"status": "unavailable", "error": "no provider configured"})
            else:
                allowed_calls = []
                if args.allow_calls:
                    container = detect_container(data)
                    target_va = _target_va(container, case["target"])
                    if target_va is not None:
                        allowed_calls = discover_allowed_calls(data, container, target_va)
                record["allowed_calls"] = [item.to_dict() for item in allowed_calls]
                packet = _prompt_packet(
                    data, case["target"], int(case["capacity"]), case["contract"],
                    args.contract_level, allowed_calls,
                )
                parsed, error = _call_model(
                    client, system_prompt=ASM_SYSTEM_PROMPT, packet=packet,
                    max_tokens=ASM_MAX_TOKENS, ai=ai_meta,
                )
                if parsed is not None and isinstance(parsed.get("assembly"), str):
                    assembly = parsed["assembly"]
                    ai_meta["status"] = "accepted"
                else:
                    ai_meta["status"] = ai_meta.get("status") or "invalid"
                    ai_meta["error"] = error or ai_meta.get("error")
        if assembly is not None:
            call_targets = record.get("allowed_calls") or []
            # Reference mode has no packet; discover only when explicitly enabled.
            if args.allow_calls and not call_targets:
                container = detect_container(data)
                target_va = _target_va(container, case["target"])
                if target_va is not None:
                    call_targets = [item.to_dict() for item in discover_allowed_calls(data, container, target_va)]
                    record["allowed_calls"] = call_targets
            allowed_objects = []
            if args.allow_calls:
                from app.services.repair.call_targets import AllowedCall
                allowed_objects = [AllowedCall(name=item["name"], target_va=int(item["target_va"], 16), source=item["source"]) for item in call_targets]
            patched, injection = _inject_target(
                data, case["target"], int(case["capacity"]), assembly, allowed_objects,
            )
            record["injection"] = injection
            record["candidate"] = _evaluate(data, patched, poc, case)
            if patched is not None:
                (out / f"{case['id']}-candidate.bin").write_bytes(patched)
        record["ai"] = ai_meta
        record["contract_level"] = args.contract_level
        record["repeats"] = args.repeats
        record["ai_increment"] = bool(
            not baseline.verified and record.get("candidate", {}).get("gate") == "pass"
        )
        results.append(record)
        print(json.dumps({
            "case": case["id"], "baseline": record["baseline"]["disposition"],
            "ai_status": ai_meta.get("status"),
            "ai_gate": record.get("candidate", {}).get("gate"),
            "increment": record["ai_increment"],
        }, ensure_ascii=False), flush=True)
    summary = {
        "schema_version": 1,
        "provider": args.client,
        "cases": results,
        "baseline_verified": sum(1 for r in results if r["baseline"]["verified"]),
        "ai_verified": sum(1 for r in results if r.get("candidate", {}).get("gate") == "pass"),
        "ai_increment": sum(1 for r in results if r["ai_increment"]),
        "note": (
            "baseline is deterministic; AI target assembly is accepted only by "
            "native/qemu PoC+regression. baseline_target_aware receives the same "
            "target/capacity hint; ai_blind uses the public AI path without target. "
            "allow_calls only permits direct calls already present in the target function."
        ),
        "contract_level": args.contract_level,
        "repeats": args.repeats,
        "baseline_target_aware_verified": sum(
            1 for r in results if r["baseline_target_aware"].get("verified")
        ),
        "ai_blind_verified": sum(
            1 for r in results if (r.get("ai_blind") or {}).get("verified")
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"out": str(out), **{k: summary[k] for k in ("baseline_verified", "ai_verified", "ai_increment")}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
