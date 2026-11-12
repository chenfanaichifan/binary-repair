"""Read-only AI review: typed failures, veto-only combination and audit rows."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.db.connection import connect
from app.services import binary_repair_engine as engine
from app.services.binary_review import run_direct_repair

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"


class FakeReviewer:
    model = "fake-model"
    review_mode = None

    def __init__(self, payload: dict | None = None, *, exc: BaseException | None = None):
        self.payload = payload or {}
        self.exc = exc
        self.messages: list[dict[str, str]] | None = None

    def chat_json(self, messages, **kwargs):
        self.messages = messages
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(
            content=json.dumps(self.payload),
            model=self.model,
            usage={"prompt_tokens": 11, "completion_tokens": 7},
            request_id="req-test",
        )


def _payload(recommendation: str, **overrides) -> dict:
    body = {
        "recommendation": recommendation,
        "summary": "The evidence supports the stated scope.",
        "concerns": [],
        "missing_evidence": [],
        "further_checks": [],
    }
    body.update(overrides)
    return body


def _run(raw: bytes, reviewer: FakeReviewer | None, *, data_dir=None):
    return run_direct_repair(
        raw,
        request_review=True,
        client=reviewer,
        data_dir=data_dir,
    )


def test_accept_concurs_but_deterministic_gate_is_authority():
    outcome = _run(VULN.read_bytes(), FakeReviewer(_payload("accept")))
    assert outcome.review.called is True
    assert outcome.review.status == "review_ok"
    assert outcome.review.recommendation == "accept"
    assert outcome.decision["success"] is True
    assert outcome.decision["authority"] == "deterministic_gate"
    assert outcome.decision["ai_effect"] == "concurred"
    assert outcome.decision["reason"] == "gate_success_ai_review_concurred"
    assert outcome.decision["evidence_sha256"] == outcome.verification.gate.evidence_sha256


def test_hold_vetoes_a_passing_gate():
    outcome = _run(
        VULN.read_bytes(),
        FakeReviewer(
            _payload(
                "hold",
                summary="Runtime evidence is emulation only.",
                concerns=[{"check_id": "runtime.available", "why": "no host-kernel replay"}],
            )
        ),
    )
    assert outcome.decision["success"] is False
    assert outcome.decision["outcome"] == "rejected"
    assert outcome.decision["authority"] == "ai_veto"
    assert outcome.decision["ai_effect"] == "veto"
    assert outcome.review.contribution["changed"] is True
    assert outcome.to_payload(filename="x.elf").get("patched_base64") is None


def test_needs_more_checks_is_inconclusive():
    outcome = _run(
        VULN.read_bytes(),
        FakeReviewer(
            _payload(
                "needs_more_checks",
                summary="Partial reads were not exercised.",
                further_checks=["run partial-read cases"],
            )
        ),
    )
    assert outcome.decision["success"] is False
    assert outcome.decision["outcome"] == "inconclusive"
    assert outcome.decision["authority"] == "ai_requested_more_checks"


def test_accept_cannot_promote_unsupported_input():
    outcome = _run(PE.read_bytes(), FakeReviewer(_payload("accept")))
    assert outcome.review.recommendation == "accept"
    assert outcome.decision["success"] is False
    assert outcome.decision["outcome"] == "unsupported"
    assert outcome.decision["reason"] == "review_accept_cannot_promote_gate"
    assert outcome.to_payload(filename="x.exe").get("patched_base64") is None


def test_accept_cannot_promote_missing_evidence(monkeypatch):
    monkeypatch.setattr(
        engine,
        "_runtime_summary",
        lambda patched, capacity: {"available": False, "error": "simulated evidence gap"},
    )
    outcome = _run(VULN.read_bytes(), FakeReviewer(_payload("accept")))
    assert outcome.decision["success"] is False
    assert outcome.decision["outcome"] == "inconclusive"
    assert outcome.decision["reason"] == "review_accept_cannot_promote_gate"
    assert outcome.verification.gate.required_not_run >= 1


def test_forbidden_verdict_payload_is_ignored():
    outcome = _run(
        VULN.read_bytes(),
        FakeReviewer(_payload("accept", verdict="success_within_scope")),
    )
    assert outcome.review.status == "review_invalid_response"
    assert outcome.review.recommendation is None
    assert outcome.decision["success"] is True
    assert outcome.decision["authority"] == "deterministic_gate"
    assert outcome.decision["ai_action"] is None


def test_unknown_check_reference_is_invalid():
    outcome = _run(
        VULN.read_bytes(),
        FakeReviewer(
            _payload(
                "hold",
                concerns=[{"check_id": "does.not.exist", "why": "unknown reference"}],
            )
        ),
    )
    assert outcome.review.status == "review_invalid_response"
    assert outcome.review.recommendation is None
    assert outcome.decision["success"] is True


def test_timeout_is_typed_and_gate_unchanged():
    outcome = _run(VULN.read_bytes(), FakeReviewer(exc=TimeoutError("slow")))
    assert outcome.review.called is True
    assert outcome.review.status == "review_timeout"
    assert outcome.review.recommendation is None
    assert outcome.decision["success"] is True
    assert outcome.decision["ai_effect"] == "none"


def test_no_client_is_not_configured_and_gate_unchanged():
    outcome = _run(VULN.read_bytes(), None)
    assert outcome.review.requested is True
    assert outcome.review.called is False
    assert outcome.review.status == "review_not_configured"
    assert outcome.decision["success"] is True
    assert outcome.decision["reason"] == "review_not_configured"


def test_prompt_contains_the_same_packet_but_not_raw_bytes():
    reviewer = FakeReviewer(_payload("accept"))
    outcome = _run(VULN.read_bytes(), reviewer)
    assert reviewer.messages is not None
    assert len(reviewer.messages) == 2
    assert "read-only verification reviewer" in reviewer.messages[0]["content"]
    user = reviewer.messages[1]["content"]
    assert "\x7fELF" not in user
    assert "vuln.elf" not in user
    packet = json.loads(user)
    assert packet["report_sha256"] == outcome.verification.packet["report_sha256"]
    assert packet["checks"] == outcome.verification.packet["checks"]


def test_model_call_is_recorded_for_audit(tmp_path):
    data = tmp_path / "var"
    outcome = _run(VULN.read_bytes(), FakeReviewer(_payload("accept")), data_dir=data)
    assert outcome.review.recorded is True
    assert outcome.review.call_id
    connection = connect(data)
    try:
        row = connection.execute(
            "SELECT route, status, model_requested, model_returned, prompt_tokens, completion_tokens "
            "FROM model_calls WHERE route = 'binary_review'"
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    assert row["status"] == "review_ok"
    assert row["model_requested"] == "fake-model"
    assert row["prompt_tokens"] == 11
    assert row["completion_tokens"] == 7


def test_contribution_counts_only_new_information():
    known = "Runtime evidence is Unicorn x86-64 emulation with modeled syscalls, not a host-kernel run."
    reviewer = FakeReviewer(
        _payload(
            "hold",
            concerns=[{"check_id": "runtime.available", "why": known}],
            missing_evidence=[known],
            further_checks=[known],
        )
    )
    outcome = _run(VULN.read_bytes(), reviewer)
    contribution = outcome.review.contribution
    assert contribution["new_concerns"] == 0
    assert contribution["new_missing_evidence"] == 0
    assert contribution["new_further_checks"] == 0

    reviewer2 = FakeReviewer(
        _payload(
            "hold",
            concerns=[{"check_id": "runtime.available", "why": "no host-kernel replay"}],
            missing_evidence=["a real host-kernel run"],
            further_checks=["partial-read cases"],
        )
    )
    outcome2 = _run(VULN.read_bytes(), reviewer2)
    assert outcome2.review.contribution["new_concerns"] == 1
    assert outcome2.review.contribution["new_missing_evidence"] == 1
    assert outcome2.review.contribution["new_further_checks"] == 1
