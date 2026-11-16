"""Phase-8D promotion gate policy tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services import promotion_gate as gate  # noqa: E402
import evaluate_promotion as promotion_cli  # noqa: E402

REF = "artifacts/phase8c-benchmark-2026-11-16/samples/stack-strcpy-x86_64/verifier-report.json"


def _record(state: str, **overrides):
    base = {
        "record_id": "test-capability",
        "current_state": state,
        "prior_state_evidence_complete": True,
        "prior_evidence_refs": [REF],
        "status": "open",
    }
    base.update(overrides)
    return base


def _analysis_evidence():
    return {
        "discovery": {"evidence_refs": ["benchmark/phase8c/manifest.json#samples"],
                      "discovery_source": "phase8c_public_benchmark"},
        "analysis": {
            "artifact_sha256": "a" * 64,
            "evidence_refs": ["artifacts/phase8c-benchmark-2026-11-16/README.md"],
            "limitations": ["fixture scope"],
        },
    }


def _candidate_evidence():
    return {"candidate": {
        "candidate_sha256": "b" * 64,
        "patch_plan_sha256": "c" * 64,
        "integrity_evidence_refs": ["artifacts/phase8c-benchmark-2026-11-16/samples/x/outcome.json"],
    }}


def _verification_evidence():
    return {"verification": {
        "decision": "verified",
        "independent": True,
        "oracle_executed": True,
        "false_verified": 0,
        "false_verified_internal": 0,
        "regression_pass": True,
        "evidence_refs": [REF],
    }}


def _generalization_evidence():
    return {"generalization": {
        "public_verified": True,
        "public_verified_count": 2,
        "hidden_verified": True,
        "hidden_verified_count": 2,
        "holdout_verified": True,
        "regression_pass": True,
        "false_verified": 0,
        "hidden_commitment_sha256": "d" * 64,
        "hidden_aggregate_sha256": "e" * 64,
        "evidence_refs": ["benchmark/phase8c/hidden-commitment.json",
                          "artifacts/phase8c-hidden-2026-11-16/aggregate.json"],
        "no_unresolved_blockers": True,
    }}


def _approval():
    return {"approval": {
        "approved_by": "independent-reviewer-1",
        "independent": True,
        "role": "independent-reviewer",
        "approval_ref": "docs/release/approval-2026-11-17.md",
        "approved_at": "2026-11-17",
    }}


def _assert_allowed(result):
    assert result["decision"] == "allowed", result["violations"]
    assert result["ok"] is True
    assert result["not_run_is_pass"] is False


def test_each_legal_transition_allowed_with_required_evidence():
    _assert_allowed(gate.evaluate_transition(
        _record("discovered"), target="analysis_only", evidence=_analysis_evidence()))
    _assert_allowed(gate.evaluate_transition(
        _record("analysis_only"), target="candidate_generated",
        evidence=_candidate_evidence()))
    _assert_allowed(gate.evaluate_transition(
        _record("candidate_generated"), target="independently_verified",
        evidence=_verification_evidence()))
    _assert_allowed(gate.evaluate_transition(
        _record("independently_verified"), target="generalized",
        evidence=_generalization_evidence()))
    promoted_evidence = {**_generalization_evidence(), **_approval(),
                         "generalized_evidence_complete": True}
    _assert_allowed(gate.evaluate_transition(
        _record("generalized"), target="promoted", evidence=promoted_evidence))


def test_skipping_a_level_is_denied():
    result = gate.evaluate_transition(
        _record("discovered"), target="candidate_generated",
        evidence=_candidate_evidence())
    assert result["decision"] == "denied"
    assert any("illegal transition" in item for item in result["violations"])
    result = gate.evaluate_transition(
        _record("independently_verified"), target="promoted",
        evidence={**_generalization_evidence(), **_approval(),
                  "generalized_evidence_complete": True})
    assert result["decision"] == "denied"
    assert any("legal next is 'generalized'" in item for item in result["violations"])


def test_not_run_or_blocked_evidence_is_never_a_pass():
    evidence = _verification_evidence()
    evidence["verification"]["decision"] = "not_run"
    result = gate.evaluate_transition(
        _record("candidate_generated"), target="independently_verified",
        evidence=evidence)
    assert result["decision"] == "denied"
    assert any("not_run" in item for item in result["violations"])
    evidence = _verification_evidence()
    evidence["verification"]["evidence_refs"] = ["blocked"]
    evidence["verification"]["decision"] = "blocked"
    result = gate.evaluate_transition(
        _record("candidate_generated"), target="independently_verified",
        evidence=evidence)
    assert result["decision"] == "denied"


def test_false_verified_nonzero_blocks_verification_and_promotion():
    evidence = _verification_evidence()
    evidence["verification"]["false_verified"] = 1
    result = gate.evaluate_transition(
        _record("candidate_generated"), target="independently_verified",
        evidence=evidence)
    assert result["decision"] == "denied"
    assert any("false_verified" in item for item in result["violations"])

    evidence = _generalization_evidence()
    evidence["generalization"]["false_verified"] = 1
    result = gate.evaluate_transition(
        _record("independently_verified"), target="generalized", evidence=evidence)
    assert result["decision"] == "denied"


def test_generalization_requires_hidden_and_holdout_evidence():
    evidence = _generalization_evidence()
    evidence["generalization"]["hidden_verified"] = False
    evidence["generalization"]["hidden_verified_count"] = 0
    evidence["generalization"]["holdout_verified"] = False
    result = gate.evaluate_transition(
        _record("independently_verified"), target="generalized", evidence=evidence)
    assert result["decision"] == "denied"
    failed = {check["id"] for check in result["checks"] if check["status"] == "failed"}
    assert {"generalization.hidden_verified", "generalization.hidden_verified_count",
            "generalization.holdout_verified"}.issubset(failed)


def test_promotion_requires_human_independent_approval_and_no_blockers():
    evidence = {**_generalization_evidence(),
                "generalized_evidence_complete": True}
    evidence["generalization"]["no_unresolved_blockers"] = True
    result = gate.evaluate_transition(
        _record("generalized"), target="promoted", evidence=evidence)
    assert result["decision"] == "denied"
    assert any("approval.approved_by" in item for item in result["violations"])

    approval = _approval()
    approval["approval"]["independent"] = False
    result = gate.evaluate_transition(
        _record("generalized"), target="promoted",
        evidence={**_generalization_evidence(), **approval,
                  "generalized_evidence_complete": True})
    assert result["decision"] == "denied"
    assert any("approval.independent" in item for item in result["violations"])


def test_auto_promotion_is_denied():
    evidence = {**_generalization_evidence(), **_approval(),
                "generalized_evidence_complete": True}
    result = gate.evaluate_transition(
        _record("generalized"), target="promoted", evidence=evidence,
        auto_promotion=True)
    assert result["decision"] == "denied"
    assert any("auto-promotion" in item for item in result["violations"])
    result = gate.evaluate_transition(
        _record("generalized", auto_promotion=True), target="promoted",
        evidence=evidence)
    assert result["decision"] == "denied"


def test_history_cannot_skip_a_level():
    result = gate.validate_history([
        "discovered", "candidate_generated", "independently_verified"])
    assert result["ok"] is False
    assert any("illegal jump" in item for item in result["violations"])
    result = gate.evaluate_transition(
        _record("independently_verified",
                state_history=["discovered", "independently_verified"]),
        target="generalized", evidence=_generalization_evidence())
    assert result["decision"] == "denied"


def test_chain_stops_at_first_denied_transition():
    incomplete = _generalization_evidence()
    incomplete["generalization"]["hidden_verified"] = False
    incomplete["generalization"]["hidden_verified_count"] = 0
    chain = gate.evaluate_chain(
        _record("independently_verified"),
        steps=[
            {"target": "generalized", "evidence": incomplete},
            {"target": "promoted",
             "evidence": {**_generalization_evidence(), **_approval(),
                          "generalized_evidence_complete": True}},
        ])
    assert chain["final_state"] == "independently_verified"
    assert chain["decisions"][0]["decision"] == "denied"
    assert len(chain["decisions"]) == 1
    assert chain["history_validation"]["ok"] is True


def test_phase8c_evaluation_denies_everything_and_promotes_nothing():
    payload = promotion_cli.build_payload()
    assert payload["summary"]["decision_count"] == 4
    assert payload["summary"]["denied_count"] == 4
    assert payload["summary"]["promoted_count"] == 0
    assert payload["capability_promotion"] is False
    assert all(item["decision"] == "denied" for item in payload["decisions"])
    assert payload["summary"]["hidden_verified_count"] == 0
    assert payload["summary"]["published_false_verified"] == 0
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/evaluate_promotion.py"), "--check", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
