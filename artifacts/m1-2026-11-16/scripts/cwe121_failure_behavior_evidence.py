#!/usr/bin/env python3
"""P0-1 evidence: CWE-121 structured failure_behavior through the real pipeline.

Deterministic stand-in (the repository reference assembly), NOT model output.
The native/guest PoC runner (run_poc) remains the only acceptance authority;
the field-by-field comparison below is auxiliary evidence only.

Run from the repository root:
    .venv/bin/python artifacts/m1-2026-11-16/scripts/cwe121_failure_behavior_evidence.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.poc_runner import run_poc  # noqa: E402
from scripts.run_hard_benchmark import (  # noqa: E402
    _controlled_calls_for, _failure_behavior_assertions, _inject_target,
    _poc_failure_contract, _poc_spec,
)

OUT = Path(__file__).resolve().parents[1]
CASE_ID = "cwe121-unchecked-strcpy"
FIELDS = ("exit_code", "stdout", "stderr", "stdout_hex")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    cases = {c["id"]: c for c in json.loads(
        (ROOT / "fixtures" / "hard-cases" / "cases.json").read_text())["cases"]}
    case = cases[CASE_ID]
    data = (ROOT / case["binary"]).read_bytes()
    poc_spec = _poc_spec(case)
    contract = _poc_failure_contract(poc_spec)
    calls = _controlled_calls_for(data, case, contract)
    assembly_path = ROOT / case["reference_fix_asm"]
    assembly = assembly_path.read_text(encoding="utf-8")

    evidence: dict = {
        "schema_version": 1,
        "kind": "m1_p0_1_failure_behavior_evidence",
        "stand_in": {
            "kind": "repository reference assembly (deterministic, not model output)",
            "path": case["reference_fix_asm"],
            "sha256": _sha(assembly_path.read_bytes()),
            "claim_scope": (
                "protocol/pipeline validation of the structured failure_behavior "
                "contract and the controlled-call templates; NOT an AI quality claim"
            ),
        },
        "case": {
            "id": CASE_ID,
            "target": case["target"],
            "binary": case["binary"],
            "original_sha256": _sha(data),
            "poc_manifest": case["poc"],
            "poc_manifest_sha256": _sha((ROOT / case["poc"]).read_bytes()),
        },
        "failure_behavior_contract": contract,
        "controlled_calls": [
            getattr(item, "to_dict", lambda: {})() for item in calls
        ],
        "auxiliary_scope": (
            "field comparison is auxiliary evidence; the gate decision comes "
            "only from the native/guest PoC runner"
        ),
    }

    patched, injection = _inject_target(
        data, case["target"], int(case["capacity"]), assembly, calls,
        failure_behavior=contract,
    )
    evidence["injection"] = {
        "ok": patched is not None,
        "meta": {key: injection.get(key) for key in (
            "target_va", "cave_va", "method", "code_bytes",
            "call_relocations", "error_class", "error")},
    }
    if patched is None:
        evidence["gate"] = {"decision": "not_run", "reason": "injection failed"}
        evidence["field_comparison"] = {"all_matched": None, "checks": []}
        (OUT / "cwe121-failure-behavior-evidence.json").write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
        return 1

    evidence["candidate_sha256"] = _sha(patched)
    (OUT / "cwe121-reference-candidate.bin").write_bytes(patched)

    poc = run_poc(data, patched, poc_spec)
    gate_decision = {"pass": "pass", "fail": "fail"}.get(poc.status, "unavailable")
    evidence["gate"] = {
        "decision": gate_decision,
        "status": poc.status,
        "runner": poc.runner,
        "tier": poc.tier,
        "limitations": list(poc.limitations),
        "lock_blocked": bool(poc.lock_blocked),
        "authority": "run_poc (native/qemu/lima PoC runner) is the only gate",
    }
    rows: list[dict] = []
    for group, items in (("poc", poc.cases), ("regression", poc.regression)):
        for row in items:
            rows.append({
                "group": group,
                "case_id": row.case_id,
                "executable": row.executable,
                "exit_code": row.exit_code,
                "crashed": row.crashed,
                "stdout": row.stdout,
                "stderr": row.stderr,
                "timed_out": row.timed_out,
                "expected_ok": row.expected_ok,
                "error": row.error,
            })
    evidence["poc_rows"] = rows
    evidence["field_comparison"] = _failure_behavior_assertions(
        case,
        {"poc": {
            "poc": [row for row in rows if row["executable"] == "candidate"
                    and row["group"] == "poc"],
            "regression": [row for row in rows
                           if row["executable"] == "candidate"
                           and row["group"] == "regression"],
        }},
    )
    evidence["verdict"] = {
        "gate": gate_decision,
        "field_comparison_all_matched": evidence["field_comparison"].get(
            "all_matched"),
        "claim": (
            "candidate passes the native PoC gate (independent of the field "
            "comparison)" if gate_decision == "pass"
            else "gate did not pass; recorded honestly as not_verified"),
    }
    path = OUT / "cwe121-failure-behavior-evidence.json"
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({
        "evidence": str(path),
        "gate": gate_decision,
        "runner": poc.runner,
        "tier": poc.tier,
        "field_comparison_all_matched": evidence["field_comparison"].get(
            "all_matched"),
        "poc_rows": len(rows),
    }, ensure_ascii=False))
    return 0 if gate_decision == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
