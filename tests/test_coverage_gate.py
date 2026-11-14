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
            }
            for gap_id in ids
        ]
    }


def _audit(gaps: list[dict]) -> dict:
    return {"gaps": gaps, "mode": "static"}


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
    ok = gate.evaluate(
        _audit([_gap("EG-target-scope", "open", "medium")]),
        _claims(["NG-dummy"]), "", allowed_open=allowed)
    assert ok["violations"] == []
    bad = gate.evaluate(
        _audit([_gap("EG-new-open", "open", "medium")]),
        _claims(["NG-dummy"]), "", allowed_open=allowed)
    assert any("ALLOWED_OPEN" in item for item in bad["violations"])


def test_unmapped_non_goal_is_a_violation_and_doc_or_claims_maps_it() -> None:
    audit = _audit([_gap("NG-test-1", "non_goal", "info", "non_goal")])
    unmapped = gate.evaluate(audit, _claims(["NG-other"]), "")
    assert any("not mapped" in item for item in unmapped["violations"])
    via_claims = gate.evaluate(audit, _claims(["NG-test-1"]), "")
    assert via_claims["violations"] == []
    via_doc = gate.evaluate(audit, _claims(["NG-other"]),
                            "see NG-test-1 in this page")
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
