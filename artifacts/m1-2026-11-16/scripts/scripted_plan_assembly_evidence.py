#!/usr/bin/env python3
"""P0-1 auxiliary evidence: scripted plan -> assembly -> injection, no live model.

Deterministic stand-in only: a fixed RepairSpec v2 (planner stand-in) and the
repository reference assembly (assembly stand-in).  The native PoC gate is NOT
run here; the gate evidence is cwe121-failure-behavior-evidence.json and the
independent verification under independent-verification-cwe121/.
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

from app.services.repair.abi import check_block as check_abi  # noqa: E402
from app.services.repair_spec import (  # noqa: E402
    failure_behavior_of, spec_from_plan, validate_spec,
)
from scripts.run_hard_benchmark import (  # noqa: E402
    _ai_plan_attempt, _ai_prompt_attempt, _controlled_calls_for, _inject_target,
    _poc_failure_contract, _poc_spec,
)

OUT = Path(__file__).resolve().parents[1]
CASE_ID = "cwe121-unchecked-strcpy"
TARGET = "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink"
STDERR = "ERROR: input exceeds destination capacity\n"


class _Client:
    model = "scripted-standin"

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def chat_json(self, messages, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            content=json.dumps(self.payload),
            model=self.model,
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            request_id="scripted",
        )


def _plan():
    return {
        "schema_version": 2,
        "vulnerability": {"type": "CWE121", "cwe": "CWE-121",
                          "root_cause": "unchecked strcpy into char[50]"},
        "program_context": {
            "function": TARGET, "addresses": [], "registers": ["rdi"],
            "memory": ["stack:50"], "capacity": 50, "allowed_calls": [],
        },
        "security_invariants": ["len+1 <= 50"],
        "repair": {
            "strategy": "guard_input_length",
            "failure_behavior": {
                "exit_code": 1, "stdout": None,
                "stderr": STDERR, "stdout_hex": None,
            },
            "expected_behavior": "valid input printed unchanged",
        },
        "abi": {"architecture": "x86_64", "calling_convention": "sysv_amd64"},
        "verification": {
            "security_conditions": ["oversized rejected"],
            "regression_conditions": ["valid preserved"],
        },
        "confidence": 0.9,
        "evidence_refs": ["static.target"],
    }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    cases = {c["id"]: c for c in json.loads(
        (ROOT / "fixtures" / "hard-cases" / "cases.json").read_text())["cases"]}
    case = cases[CASE_ID]
    data = (ROOT / case["binary"]).read_bytes()
    poc_spec = _poc_spec(case)
    assembly_path = ROOT / case["reference_fix_asm"]
    assembly = assembly_path.read_text(encoding="utf-8")

    plan_client = _Client(_plan())
    plan_result = _ai_plan_attempt(
        plan_client, data, case, "full", False, None)
    spec = spec_from_plan(plan_result["plan"]) if plan_result["plan"] else None
    contract = failure_behavior_of(spec) if spec is not None else None

    asm_client = _Client({"schema_version": 1, "assembly": assembly})
    prompt = _ai_prompt_attempt(
        asm_client, data, case, "full", False, None, repair_spec=spec)
    calls = _controlled_calls_for(data, case, contract) if contract else []
    patched, injection = (None, {})
    abi = None
    if prompt["assembly"] is not None:
        patched, injection = _inject_target(
            data, case["target"], int(case["capacity"]), prompt["assembly"],
            calls, failure_behavior=contract,
        )
        if patched is not None:
            from app.services.containers import detect_container
            abi = check_abi(
                bytes.fromhex(injection["code_hex"]),
                detect_container(data).arch,
            ).to_dict()

    evidence = {
        "schema_version": 1,
        "kind": "m1_p0_1_scripted_plan_assembly_evidence",
        "authority": (
            "auxiliary protocol evidence; no live model was called and the "
            "native PoC gate is NOT evaluated in this file"),
        "stand_in": {
            "planner": "fixed RepairSpec v2 (scripted stand-in)",
            "assembly": {
                "path": case["reference_fix_asm"],
                "sha256": _sha(assembly_path.read_bytes()),
                "note": "repository reference assembly, not model output",
            },
        },
        "case": {"id": CASE_ID, "target": case["target"],
                 "original_sha256": _sha(data),
                 "poc_manifest": case["poc"]},
        "planner": {
            "client": plan_client.model,
            "calls": plan_client.calls,
            "plan_valid": plan_result["plan"] is not None,
            "plan_error": plan_result["plan_error"],
            "failure_behavior": plan_result.get("failure_behavior"),
            "failure_behavior_source": plan_result.get(
                "failure_behavior_source"),
            "poc_failure_contract": plan_result.get("poc_failure_contract"),
        },
        "assembly": {
            "client": asm_client.model,
            "calls": asm_client.calls,
            "returned": prompt["assembly"] is not None,
            "validation_error": prompt.get("validation_error"),
            "controlled_templates": prompt.get("controlled_templates"),
        },
        "injection": {
            "ok": patched is not None,
            "meta": {key: injection.get(key) for key in (
                "target_va", "cave_va", "method", "code_bytes",
                "call_relocations", "failure_behavior", "error_class",
                "error")},
            "abi": abi,
        },
        "candidate_sha256": _sha(patched) if patched is not None else None,
    }
    path = OUT / "scripted-plan-assembly-evidence.json"
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "evidence": str(path),
        "plan_valid": evidence["planner"]["plan_valid"],
        "plan_error": evidence["planner"]["plan_error"],
        "templates": [item["name"] for item in
                      evidence["assembly"]["controlled_templates"] or []],
        "injection_ok": evidence["injection"]["ok"],
        "abi_ok": (abi or {}).get("ok"),
    }))
    return 0 if patched is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
