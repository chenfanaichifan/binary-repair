"""Tests for the coverage regression gate (fast, deterministic, no network)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import verify_coverage_gate as gate  # noqa: E402


def _gap(gap_id: str, status: str, severity: str = "info",
         category: str = "engine_gap") -> dict:
    return {
        "gap_id": gap_id,
        "category": category,
        "severity": severity,
        "status": status,
        "symptom": "test gap",
        "evidence": ["test:evidence"],
        "next_step": "none",
        "detector": "test",
        "lead_ref": "",
        "novel": False,
    }


def _claims(ids: list[str]) -> dict:
    return {
        "non_goals": [
            {
                "id": gap_id,
                "category": "non_goal",
                "enforcement": "unsupported",
                "claim": "test claim",
                "owner": "test-owner",
                "review_by": "2027-01-31",
                "productization_criteria": "test criteria",
                "fallback": "test fallback",
            }
            for gap_id in ids
        ]
    }


def _universe() -> dict:
    cell = {
        "container": "elf", "arch": "x86_64", "bits": "64",
        "endian": "little", "strategy": "guard",
        "sink_class": "unbounded_copy", "destination_kind": "stack",
        "evidence_profile": "emulated_instruction",
        "runtime_tier": "emulated_run", "provider": "deterministic",
        "proof_scope": "target_scoped", "status": "supported",
        "reason": "test cell", "claims_non_goal_id": "",
    }
    return {
        "cells": [cell],
        "dimensions": {key: [cell[key]] for key in (
            "container", "arch", "bits", "endian", "strategy", "sink_class",
            "destination_kind", "evidence_profile", "runtime_tier",
            "provider", "proof_scope")},
        "statuses": ["verified", "supported", "non_goal", "unavailable",
                     "unknown"],
        "counts": {"verified": 0, "supported": 1, "non_goal": 0,
                   "unavailable": 0, "unknown": 0},
        "cell_count": 1,
        "unknown": 0,
        "unmapped_non_goal_ids": [],
        "missing_reason_count": 0,
        "missing_reason_cells": [],
    }


def _audit(gaps: list[dict]) -> dict:
    return {"gaps": gaps, "mode": "static", "universe": _universe()}


def test_real_tree_static_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_coverage_gate.py"),
         "--static-only"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "coverage-gate: mode=static" in result.stdout
    assert "violations=0" in result.stdout


def test_evaluate_detects_detector_error() -> None:
    summary = gate.evaluate(
        _audit([_gap("GM-detector-error::claims_docs", "open", "medium")]),
        _claims([]), "")
    assert summary["violations"]
    assert any("detector error" in item for item in summary["violations"])


def test_evaluate_detects_high_severity_open() -> None:
    summary = gate.evaluate(
        _audit([_gap("EG-something", "open", "high")]),
        _claims([]), "")
    assert any("high-severity" in item for item in summary["violations"])


def test_allowlist_accepts_known_residual_and_rejects_new() -> None:
    allowed = ("EG-target-scope",)
    measured = [
        _gap("EG-target-scope", "open", "medium"),
        _gap("NG-dummy", "non_goal", "info", "non_goal"),
    ]
    ok = gate.evaluate(_audit(measured), _claims(["NG-dummy"]), "",
                       allowed_open=allowed)
    assert ok["violations"] == []
    bad = gate.evaluate(
        _audit([_gap("EG-new-open", "open", "medium"),
                _gap("NG-dummy", "non_goal", "info", "non_goal")]),
        _claims(["NG-dummy"]), "", allowed_open=allowed)
    assert any("ALLOWED_OPEN" in item for item in bad["violations"])


def test_unmapped_non_goal_is_a_violation_and_doc_or_claims_maps_it() -> None:
    audit = _audit([_gap("NG-test-1", "non_goal", "info", "non_goal")])
    unmapped = gate.evaluate(audit, _claims(["NG-other"]), "")
    assert any("not mapped" in item for item in unmapped["violations"])
    via_claims = gate.evaluate(audit, _claims(["NG-test-1"]), "")
    assert via_claims["violations"] == []
    via_doc = gate.evaluate(
        _audit([_gap("NG-test-1", "non_goal", "info", "non_goal"),
                _gap("NG-other", "non_goal", "info", "non_goal")]),
        _claims(["NG-other"]), "see NG-test-1 in this page")
    assert via_doc["violations"] == []


def test_claims_structure_validation() -> None:
    compact = {"non_goals": [{"id": "NG-x"}]}
    summary = gate.evaluate(_audit([]), compact, "")
    assert any("missing fields" in item for item in summary["violations"])
    not_a_list = {"non_goals": {"id": "NG-x"}}
    summary = gate.evaluate(_audit([]), not_a_list, "")
    assert any("non_goals" in item for item in summary["violations"])
    summary = gate.evaluate(_audit([]), None, "")
    assert any("claims.json" in item for item in summary["violations"])


def test_local_allowlist_must_be_tight_and_acceptance_required(tmp_path: Path) -> None:
    allowed = ("EG-target-scope", "RG-closed-now")
    audit = _audit([_gap("EG-target-scope", "open", "medium")])
    summary = gate.evaluate(audit, _claims([]), "", allowed_open=allowed,
                            local=True)
    assert any("no longer measured open" in item for item in summary["violations"])
    missing = gate.check_acceptance(tmp_path / "missing.json")
    assert missing
    passed = tmp_path / "passed.json"
    passed.write_text(json.dumps({"passed": True, "failures": []}), encoding="utf-8")
    assert gate.check_acceptance(passed) == []
    failed = tmp_path / "failed.json"
    failed.write_text(json.dumps({"passed": False}), encoding="utf-8")
    assert gate.check_acceptance(failed)


def test_cli_injected_bad_audit_fails(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(_audit([
        _gap("GM-detector-error::x", "open", "medium"),
        _gap("EG-new-open", "open", "low"),
    ])), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_coverage_gate.py"),
         "--audit-json", str(audit_path),
         "--claims", str(ROOT / "docs" / "status" / "claims.json"),
         "--non-goals", str(ROOT / "docs" / "acceptance"
                            / "non-goals-2026-11-14.md")],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode != 0
    assert "VIOLATION" in result.stdout


def test_manifest_route_detection_ignores_signature_declaration() -> None:
    """A `poc_manifest: ... = None` parameter is not a routing guard."""
    from app.services import coverage_audit

    source = """
def repair_any(
    data: bytes,
    *,
    poc_manifest: dict[str, Any] | None = None,
    verify: bool = True,
) -> RepairOutcome:
    # Repair any input.
    container = detect_container(data)
    from app.services.binary_repair_engine import repair_elf
    patched, raw = repair_elf(data)
    report = _from_elf_legacy(container, data, patched, raw, verify=verify,
                              external_poc=poc_manifest)
    return report


def _from_elf_legacy(container, data, patched, raw, *, verify,
                     external_poc=None):
    if external_poc is not None:
        report.limitations.append("cannot consume it")
    return report


def _select_runtime(data, container, sink):
    return None
"""
    evidence = coverage_audit._manifest_route_evidence(source)
    assert evidence["routed"] is False
    assert evidence["disclosed"] is True
    assert "poc_manifest is not None" not in evidence["guard_patterns"]


def test_manifest_route_detection_requires_guard_before_legacy_engine() -> None:
    """A real control-flow guard that routes before repair_elf is measured."""
    from app.services import coverage_audit

    source = """
def repair_any(
    data: bytes,
    *,
    poc_manifest: dict[str, Any] | None = None,
    verify: bool = True,
) -> RepairOutcome:
    # Repair any input.
    container = detect_container(data)
    if poc_manifest is not None:
        return _attempt_capacity(data, container, poc_manifest=poc_manifest)
    from app.services.binary_repair_engine import repair_elf
    patched, raw = repair_elf(data)
    return patched


def _from_elf_legacy(container, data, patched, raw, *, verify,
                     external_poc=None):
    return None


def _select_runtime(data, container, sink):
    return None
"""
    evidence = coverage_audit._manifest_route_evidence(source)
    assert evidence["routed"] is True
    assert evidence["guard_position"] < evidence["legacy_position"]
    assert "_attempt_capacity" in evidence["route_helpers"]
    assert "return" in evidence["route_helpers"]


def test_repo_claims_parse_and_preserve_invariants() -> None:
    claims = json.loads((ROOT / "docs" / "status" / "claims.json")
                        .read_text(encoding="utf-8"))
    assert claims["product_paths"] == ["asm_roundtrip", "binary_direct"]
    assert "not universal repair" in claims["scope"]
    assert any("paradigm A" in item
               for item in claims["explicitly_unimplemented"])
    ids, violations = gate.claims_non_goal_ids(claims)
    assert not violations
    assert len(ids) == 11


def test_dynamic_unverified_is_allowed_static_but_rejected_local() -> None:
    audit = _audit([_gap("EG-target-scope", "dynamic_unverified")])
    static = gate.evaluate(audit, _claims([]), "", local=False)
    assert not any("dynamic_unverified" in item
                   for item in static["violations"])
    local = gate.evaluate(audit, _claims([]), "", local=True)
    assert any("dynamic_unverified_count==0" in item
               for item in local["violations"])


def test_universe_unknown_or_unmapped_is_a_violation() -> None:
    audit = _audit([])
    audit["universe"]["unknown"] = 2
    result = gate.evaluate(audit, _claims([]), "")
    assert any("unknown count" in item for item in result["violations"])

    audit = _audit([])
    cell = dict(audit["universe"]["cells"][0])
    cell.update({"status": "non_goal", "reason": "reserved",
                 "claims_non_goal_id": "NG-not-in-claims"})
    audit["universe"]["cells"] = [cell]
    audit["universe"]["counts"] = {"verified": 0, "supported": 0,
                                   "non_goal": 1, "unavailable": 0,
                                   "unknown": 0}
    result = gate.evaluate(audit, _claims([]), "")
    assert any("claims.json non_goals" in item for item in result["violations"])


def test_claims_productization_fields_are_required() -> None:
    audit = _audit([_gap("NG-x", "non_goal", "info", "non_goal")])
    claims = _claims(["NG-x"])
    del claims["non_goals"][0]["owner"]
    result = gate.evaluate(audit, claims, "")
    assert any("missing fields" in item for item in result["violations"])

    claims = _claims(["NG-x"])
    claims["non_goals"][0]["review_by"] = "2028-01-01"
    result = gate.evaluate(audit, claims, "")
    assert any("review_by" in item for item in result["violations"])


def test_static_gate_json_exposes_phase3_sections() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_coverage_gate.py"),
         "--static-only", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["dynamic_unverified_count"] >= 1
    assert payload["universe"]["unknown"] == 0
    assert payload["meta_audit"]["ok"] is True
    assert payload["meta_audit"]["recall"] >= 0.8
    assert payload["invariants"]["ok"] is True
    assert payload["invariants"]["packets_checked"] > 0
    assert payload["acceptance"]["ok"] is True


def test_meta_audit_and_invariants_runners_are_exposed() -> None:
    meta = gate.run_meta_audit_check()
    assert meta["ok"] is True and meta["passed"] is True
    invariants = gate.run_invariant_check()
    assert invariants["ok"] is True
    assert invariants["packets_checked"] > 0
