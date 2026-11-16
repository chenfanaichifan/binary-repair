#!/usr/bin/env python3
"""P0-2 evidence: CWE-134 plan-invalid field diagnostics + minimal format fix.

Deterministic stand-in only; no live model. Two parts:

1. plan diagnostics: the historical v2 plan shape (callee printf VA listed in
   program_context.addresses) is rejected with a field-level diagnostic, and
   the in-scope variant is accepted with strategy=format_string;
2. minimal format-string fix: a scripted assembly block (fixed "%s" format)
   is injected through the real pipeline and evaluated by the native PoC
   runner (Lima guest). Gate authority is run_poc only.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.containers import detect_container  # noqa: E402
from app.services.poc_runner import run_poc  # noqa: E402
from app.services.repair.abi import check_block as check_abi  # noqa: E402
from app.services.repair.call_targets import discover_allowed_calls  # noqa: E402
from scripts.run_hard_benchmark import (  # noqa: E402
    _ai_plan_attempt, _failure_behavior_assertions, _inject_target,
    _poc_failure_contract, _poc_spec, _target_va,
)

OUT = Path(__file__).resolve().parents[1]
CASE_ID = "cwe134-format-string"
TARGET = "cwe134_bad"

MINIMAL_FIX_ASM = "\n".join([
    ".intel_syntax noprefix",
    ".text",
    "sub rsp, 8",
    "mov rsi, rdi",
    "mov word ptr [rsp], 0x7325",
    "mov byte ptr [rsp + 2], 0",
    "mov rdi, rsp",
    "xor eax, eax",
    "call printf",
    "add rsp, 8",
    "ret",
    "",
])


class _Client:
    model = "scripted-standin"

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0
        self.messages = []

    def chat_json(self, messages, **kwargs):
        self.calls += 1
        self.messages.append(messages)
        return SimpleNamespace(
            content=json.dumps(self.payload), model=self.model,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            request_id="scripted")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _plan(addresses):
    return {
        "schema_version": 2,
        "vulnerability": {
            "type": "CWE-134", "cwe": "CWE-134",
            "root_cause": "caller data used as the printf format string",
        },
        "program_context": {
            "function": TARGET, "addresses": addresses,
            "registers": ["rdi", "rsi"], "memory": ["[rbp-8]"],
            "capacity": 16, "allowed_calls": [],
        },
        "security_invariants": [
            "the printf format string is a program-controlled literal",
        ],
        "repair": {
            "strategy": "format_string",
            "failure_behavior": "caller data is never a format string",
            "expected_behavior": "benign input printed unchanged",
        },
        "abi": {"architecture": "x86_64",
                "calling_convention": "sysv_amd64"},
        "verification": {
            "security_conditions": ["fixed format literal"],
            "regression_conditions": ["valid output preserved"],
        },
        "confidence": 0.9,
        "evidence_refs": ["static.target"],
    }


def main() -> int:
    # The CWE-134 case is part of the Path A 12-case expansion manifest used
    # by the historical P16-R3 run (read-only input for this evidence).
    manifest = (ROOT / "artifacts" / "repair-benchmark-expansion-2026-11-16"
                / "cases.json")
    cases = {c["id"]: c for c in json.loads(manifest.read_text())["cases"]}
    case = cases[CASE_ID]
    data = (ROOT / case["binary"]).read_bytes()
    poc_spec = _poc_spec(case)

    # --- part 1: plan diagnostics -------------------------------------
    historical_addresses = {
        "function_va": "0x401156", "call_va": "0x401177",
        "callee_va": "0x401050", "ret_va": "0x40117e",
    }
    client_bad = _Client(_plan(historical_addresses))
    bad_result = _ai_plan_attempt(
        client_bad, data, case, "full", False, None)
    packet = json.loads(client_bad.messages[0][-1]["content"])

    client_good = _Client(_plan(["0x401156", "0x401177", "0x40117e"]))
    good_result = _ai_plan_attempt(
        client_good, data, case, "full", False, None)

    plan_evidence = {
        "authority": "auxiliary typed diagnostics; no acceptance decision",
        "historical_plan": {
            "addresses": historical_addresses,
            "plan_error": bad_result["plan_error"],
            "plan_invalid": bad_result["plan_invalid"],
            "attempt_1": (bad_result.get("attempts") or [{}])[0].get(
                "diagnostics"),
        },
        "planner_packet": {
            "target_scope": packet.get("target_scope"),
            "target_scope_rule": packet.get("target_scope_rule"),
        },
        "repaired_plan": {
            "addresses": ["0x401156", "0x401177", "0x40117e"],
            "plan_valid": good_result["plan"] is not None,
            "plan_error": good_result["plan_error"],
            "strategy": ((good_result.get("plan") or {}).get("repair") or {})
            .get("strategy"),
            "plan_invalid": good_result.get("plan_invalid"),
        },
    }

    # --- part 2: minimal format-string fix through the real gate ------
    container = detect_container(data)
    target_va = _target_va(container, TARGET)
    calls = discover_allowed_calls(data, container, target_va)
    patched, injection = _inject_target(
        data, TARGET, int(case["capacity"]), MINIMAL_FIX_ASM, calls)
    gate = {"decision": "not_run", "reason": "injection failed"}
    assertions = {"all_matched": None, "checks": []}
    rows: list[dict] = []
    if patched is not None:
        (OUT / "cwe134-reference-candidate.bin").write_bytes(patched)
        poc = run_poc(data, patched, poc_spec)
        gate = {
            "decision": {"pass": "pass", "fail": "fail"}.get(
                poc.status, "unavailable"),
            "status": poc.status,
            "runner": poc.runner,
            "tier": poc.tier,
            "limitations": list(poc.limitations),
            "lock_blocked": bool(poc.lock_blocked),
            "authority": "run_poc (native/guest PoC runner) is the only gate",
        }
        for group, items in (("poc", poc.cases), ("regression", poc.regression)):
            for row in items:
                rows.append({
                    "group": group, "case_id": row.case_id,
                    "executable": row.executable,
                    "exit_code": row.exit_code, "crashed": row.crashed,
                    "stdout": row.stdout, "stderr": row.stderr,
                    "timed_out": row.timed_out,
                    "expected_ok": row.expected_ok, "error": row.error,
                })
        assertions = _failure_behavior_assertions(
            case,
            {"poc": {
                "poc": [row for row in rows
                        if row["executable"] == "candidate"
                        and row["group"] == "poc"],
                "regression": [row for row in rows
                               if row["executable"] == "candidate"
                               and row["group"] == "regression"],
            }},
        )

    assembly_evidence = {
        "stand_in": "scripted fixed-format assembly (not model output)",
        "assembly": MINIMAL_FIX_ASM,
        "allowed_calls": [item.to_dict() for item in calls],
        "injection": {
            "ok": patched is not None,
            "meta": {key: injection.get(key) for key in (
                "target_va", "cave_va", "method", "code_bytes",
                "call_relocations", "error_class", "error")},
            "abi": (check_abi(bytes.fromhex(injection["code_hex"]),
                              container.arch).to_dict()
                    if patched is not None else None),
        },
        "candidate_sha256": _sha(patched) if patched is not None else None,
        "gate": gate,
        "poc_rows": rows,
        "field_comparison": assertions,
    }

    evidence = {
        "schema_version": 1,
        "kind": "m1_p0_2_cwe134_plan_diagnostics_evidence",
        "case": {
            "id": CASE_ID, "target": TARGET,
            "binary": case["binary"], "original_sha256": _sha(data),
            "poc_manifest": case["poc"],
            "poc_manifest_sha256": _sha((ROOT / case["poc"]).read_bytes()),
        },
        "plan_diagnostics": plan_evidence,
        "minimal_format_string_fix": assembly_evidence,
        "claim": {
            "gate": gate["decision"],
            "plan_invalid_now_typed": bool(
                (bad_result.get("plan_invalid") or {}).get("field")),
            "gate_authority": "native PoC runner only",
            "model_quality": "not_run (no live model)",
        },
    }
    path = OUT / "cwe134-plan-diagnostics-evidence.json"
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "evidence": str(path),
        "plan_error_before": bad_result["plan_error"],
        "diagnostic_field": (bad_result.get("plan_invalid") or {}).get("field"),
        "plan_valid_after": good_result["plan"] is not None,
        "strategy": plan_evidence["repaired_plan"]["strategy"],
        "fixed_injection_ok": patched is not None,
        "gate": gate["decision"],
        "gate_runner": gate.get("runner"),
        "assertions_all_matched": assertions.get("all_matched"),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
