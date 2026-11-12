"""Bounded AI adjudication: veto-only, never promote missing evidence."""
from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from app.services.ai_adjudication import (
    GateResult, PolicyViolation, adjudicate, guard_model_payload,
    preflight_key_binding, supervisor_step,
)

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200

HASH = "a" * 64


def gate(success: bool):
    return GateResult(
        success=success,
        outcome="success_within_scope" if success else "inconclusive",
        reason="" if success else "required_check_not_run",
        required_checks=3,
        required_not_run=0 if success else 1,
        evidence_sha256=HASH if success else None,
    )


def test_ai_accept_cannot_promote_failed_gate():
    decision = adjudicate(gate(False), "accept")
    assert decision.success is False
    assert decision.outcome == "inconclusive"
    assert decision.reason == "ai_accept_cannot_promote_gate"
    assert decision.authority == "deterministic_gate"


def test_ai_reject_vetoes_successful_gate():
    decision = adjudicate(gate(True), "reject")
    assert decision.success is False
    assert decision.outcome == "rejected"
    assert decision.authority == "ai_veto"


def test_ai_accept_and_gate_success_is_joint_success():
    decision = adjudicate(gate(True), "accept")
    assert decision.success is True
    assert decision.authority == "deterministic_gate+ai_accept"


def test_repair_step_retries_but_does_not_succeed():
    result = supervisor_step(gate=gate(False), ai_action="repair", attempt=1, max_attempts=3)
    assert result["state"] == "retry"
    assert result["decision"]["success"] is False


def test_model_verdict_fields_are_rejected():
    try:
        guard_model_payload({"action": "accept", "verdict": "success_within_scope"})
    except PolicyViolation as exc:
        assert "verdict" in str(exc)
    else:
        raise AssertionError("model verdict field was not rejected")


def test_custom_key_env_mismatch_fails_closed():
    result = preflight_key_binding(
        key_file_configured=True, env_present=True, adapter_reads_same_env=False
    )
    assert result["ok"] is False
    assert result["reason"] == "adapter_env_mismatch"


def test_boundary_and_adjudication_api():
    boundary = client.get("/api/ai/boundary")
    assert boundary.status_code == 200
    assert boundary.json()["authority"] == "deterministic_gate"
    failed = client.post(
        "/api/ai/adjudicate",
        headers={"X-CSRF-Token": CSRF_TOKEN},
        json={
            "gate": {"success": False, "outcome": "inconclusive", "required_not_run": 1},
            "ai": {"action": "accept"},
        },
    )
    assert failed.status_code == 200
    assert failed.json()["decision"]["success"] is False
    veto = client.post(
        "/api/ai/adjudicate",
        headers={"X-CSRF-Token": CSRF_TOKEN},
        json={
            "gate": {"success": True, "outcome": "success_within_scope", "evidence_sha256": HASH},
            "ai": {"action": "reject"},
        },
    )
    assert veto.status_code == 200
    assert veto.json()["decision"]["authority"] == "ai_veto"
    forbidden = client.post(
        "/api/ai/adjudicate",
        headers={"X-CSRF-Token": CSRF_TOKEN},
        json={
            "gate": {"success": False, "outcome": "inconclusive"},
            "ai": {"action": "accept", "verdict": "success_within_scope"},
        },
    )
    assert forbidden.status_code == 422
