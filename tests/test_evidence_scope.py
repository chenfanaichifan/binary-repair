"""Evidence scope: every result says what it actually proves.

Pins the GUI half of the review item "distinguish round-trip, tests and symbolic
evidence": model-level symbolic proof must not read like a binary-level result,
and round-trip evidence must not count as repair evidence.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_module
from app.backend import build_export_bundle
from app.evidence_domains import evidence_domain
from app.main import SESSION_TOKEN, app

OBLIGATIONS = [
    {"id": "V0", "kind": "identity", "required": True, "result": "passed",
     "evidence_artifact_id": "artifact-original", "detail": "V0 identity: passed"},
    {"id": "V1", "kind": "structure", "required": True, "result": "passed",
     "evidence_artifact_id": "artifact-candidate", "detail": "V1 structure: passed"},
    {"id": "V2", "kind": "interface", "required": True, "result": "passed",
     "evidence_artifact_id": "artifact-candidate", "detail": "V2 interface: passed"},
    {"id": "V3", "kind": "behaviour", "required": True, "result": "failed",
     "evidence_artifact_id": "artifact-candidate", "detail": "V3 behaviour: failed"},
    {"id": "V4", "kind": "symbolic", "required": True, "result": "not_run",
     "evidence_artifact_id": None, "detail": "V4 symbolic: not_run"},
    {"id": "V5", "kind": "reproducibility", "required": True, "result": "not_run",
     "evidence_artifact_id": None, "detail": "V5 reproducibility: not_run"},
]

SNAPSHOT = {
    "id": "job-scope",
    "demo": True,
    "filename": "sample.bin",
    "original_sha256": "a" * 64,
    "phase": "finished",
    "cancelled": False,
    "created_at": "2026-11-05T00:00:00+00:00",
    "contract": {"revision": 1, "sha256": "b" * 64, "approved": True},
    "routes": {
        "A": {
            "name": "route_a",
            "outcome": "inconclusive",
            "verdict": {"outcome": "inconclusive", "reason": "required_check_not_run",
                        "failing_obligation": "behaviour"},
            "verification": "not_run",
            "compatibility": "not_run",
            "tests": {"passed": 0, "total": 8},
            "stages": [],
            "changed_regions": [],
            "elapsed_s": 0,
            "manual_interventions": 0,
            "ai_usage": "unavailable",
            "evidence": "persisted",
            "obligations": OBLIGATIONS,
        },
        "B": {
            "name": "route_b",
            "outcome": "inconclusive",
            "verdict": {"outcome": "inconclusive", "reason": "required_check_not_run",
                        "failing_obligation": "behaviour"},
            "verification": "not_run",
            "compatibility": "not_run",
            "tests": {"passed": 0, "total": 8},
            "stages": [],
            "changed_regions": [],
            "elapsed_s": 0,
            "manual_interventions": 0,
            "ai_usage": "unavailable",
            "evidence": "persisted",
            "obligations": OBLIGATIONS,
        },
    },
    "verdict": {"outcome": "inconclusive", "reason": "required_check_not_run"},
}


class _ScopeBackend:
    mode = "mock"
    base_url = ""

    def get_snapshot(self, job_id: str) -> dict:
        return SNAPSHOT

    def get_obligations(self, job_id: str) -> dict:
        return {"A": OBLIGATIONS, "B": OBLIGATIONS}

    def get_artifacts(self, job_id: str) -> dict:
        return {"A": [], "B": []}

    def export_bundle(self, job_id: str) -> dict:
        return build_export_bundle(
            SNAPSHOT, {"A": OBLIGATIONS, "B": OBLIGATIONS}, {"A": [], "B": []}, demo=True
        )


def test_symbolic_is_model_level_and_does_not_grant_repair_credit():
    domain = evidence_domain("symbolic")
    assert domain["level"] == "model"
    assert domain["repair_credit"] is False
    assert "model" in domain["scope_en"]
    assert "机器指令" in domain["scope_zh"]


def test_round_trip_never_counts_as_repair_evidence():
    round_trip = evidence_domain("round_trip")
    repaired = evidence_domain("repaired_behaviour")
    assert round_trip["repair_credit"] is False
    assert round_trip["level"] == "binary"
    assert repaired["repair_credit"] is True
    assert "not repair evidence" in round_trip["scope_en"]


def test_unknown_kind_is_reported_as_unknown_not_guessed():
    domain = evidence_domain("something_new")
    assert domain["level"] == "unknown"
    assert domain["repair_credit"] is False
    assert "did not label" in domain["scope_en"]


def test_human_labels_resolve_to_their_domain():
    # Producers may send the display label instead of the short V0-V5 kind.
    assert evidence_domain("Bounded symbolic security")["level"] == "model"
    assert evidence_domain("Concrete behavior")["level"] == "binary"
    assert evidence_domain("Identity and preconditions")["level"] == "metadata"
    assert evidence_domain("Repaired behaviour")["repair_credit"] is True
    # Round-trip preservation must never be promoted to repair evidence.
    assert evidence_domain("Round-trip behaviour")["repair_credit"] is False


def _client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main_module, "BACKEND", _ScopeBackend())
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def test_evidence_page_labels_each_domain_and_scope(monkeypatch):
    client = _client(monkeypatch)
    page = client.get("/jobs/job-scope/evidence")
    assert page.status_code == 200
    body = page.text

    assert "证据域" in body
    assert "符号验证" in body
    assert "模型级" in body
    assert "行为测试" in body
    assert "二进制级" in body
    # The legend must say model-level proof is not a binary-level guarantee.
    assert "不证明机器指令正确实现" in body
    assert 'data-evidence-level="model"' in body
    assert 'data-evidence-level="binary"' in body


def test_report_page_shows_evidence_domain_and_level(monkeypatch):
    client = _client(monkeypatch)
    page = client.get("/jobs/job-scope/report")
    assert page.status_code == 200
    body = page.text
    assert "Evidence domain" in body
    assert "Bounded symbolic security" in body
    assert "Concrete behaviour" in body
