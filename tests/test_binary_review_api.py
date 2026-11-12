"""HTTP contract for the read-only direct-ELF review endpoint."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main_module
from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from app.services import binary_repair_engine as engine

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"


class FakeReviewer:
    model = "fake-model"
    review_mode = None

    def __init__(self, recommendation: str = "accept"):
        self.recommendation = recommendation

    def chat_json(self, messages, **kwargs):
        payload = {
            "recommendation": self.recommendation,
            "summary": "Review complete.",
            "concerns": [],
            "missing_evidence": [],
            "further_checks": [],
        }
        return SimpleNamespace(
            content=json.dumps(payload),
            model=self.model,
            usage={"prompt_tokens": 5, "completion_tokens": 3},
            request_id="req-api",
        )


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.get("/?token=" + SESSION_TOKEN)
    assert response.status_code == 200
    return client


def _post(client: TestClient, data: bytes, name: str, *, ai: bool = False):
    return client.post(
        "/api/binary/repair-review",
        files={"binary": (name, data, "application/octet-stream")},
        data={"csrf": CSRF_TOKEN, "ai_review": "1" if ai else "0"},
    )


def test_strict_fixture_without_ai_is_successful_and_downloadable(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    client = _client()
    response = _post(client, VULN.read_bytes(), "vuln.elf")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["decision"]["success"] is True
    assert payload["review"]["requested"] is False
    assert payload["review"]["called"] is False
    assert payload["verification"]["gate"]["success"] is True
    assert payload["patched_base64"].startswith("f0VMR")  # base64 of ELF magic
    assert len(payload["verification"]["checks"]) >= 8


def test_unsupported_input_with_ai_accept_stays_non_successful(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setattr(main_module, "client_from_env", lambda: FakeReviewer("accept"))
    client = _client()
    response = _post(client, PE.read_bytes(), "cli.exe", ai=True)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["decision"]["success"] is False
    assert payload["decision"]["reason"] == "review_accept_cannot_promote_gate"
    assert payload["review"]["called"] is True
    assert payload["review"]["recommendation"] == "accept"
    assert "patched_base64" not in payload


def test_missing_evidence_with_ai_accept_stays_non_successful(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setattr(main_module, "client_from_env", lambda: FakeReviewer("accept"))
    monkeypatch.setattr(
        engine,
        "_runtime_summary",
        lambda patched, capacity: {"available": False, "error": "simulated evidence gap"},
    )
    client = _client()
    response = _post(client, VULN.read_bytes(), "vuln.elf", ai=True)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["decision"]["outcome"] == "inconclusive"
    assert payload["decision"]["reason"] == "review_accept_cannot_promote_gate"
    assert payload["review"]["recommendation"] == "accept"
    assert payload["verification"]["gate"]["required_not_run"] >= 1
    assert "patched_base64" not in payload


def test_ai_hold_vetoes_download_but_keeps_gate_success(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setattr(main_module, "client_from_env", lambda: FakeReviewer("hold"))
    client = _client()
    response = _post(client, VULN.read_bytes(), "vuln.elf", ai=True)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["decision"]["outcome"] == "rejected"
    assert payload["decision"]["authority"] == "ai_veto"
    assert payload["verification"]["gate"]["success"] is True
    assert payload["candidate_available"] is True
    assert payload["download_allowed"] is False
    assert "patched_base64" not in payload


def test_ai_unavailable_does_not_block_a_passing_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    monkeypatch.setattr(main_module, "client_from_env", lambda: None)
    client = _client()
    response = _post(client, VULN.read_bytes(), "vuln.elf", ai=True)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["review"]["called"] is False
    assert payload["review"]["status"] == "review_not_configured"
    assert payload["decision"]["reason"] == "review_not_configured"


def test_csrf_is_required():
    client = _client()
    response = client.post(
        "/api/binary/repair-review",
        files={"binary": ("vuln.elf", VULN.read_bytes(), "application/octet-stream")},
        data={"csrf": "wrong", "ai_review": "0"},
    )
    assert response.status_code == 403


def test_review_contract_is_review_only():
    client = _client()
    response = client.get("/api/binary/review-contract")
    assert response.status_code == 200
    payload = response.json()
    assert payload["review_only"] is True
    assert payload["authority"] == "deterministic_gate"
    assert "promote_gate_failure" in payload["ai_may_not"]
    assert payload["hold_effect"] == "veto_gate_success"
    assert payload["accept_effect"] == "cannot_promote_failed_gate"
    assert payload["review_unavailable_effect"] == "gate_outcome_unchanged"
    assert payload["review_can_only_tighten"] is True
    assert payload["download_requires"] == "decision.success"
    assert payload["patched_bytes_requires"] == "decision.success"
    assert payload["gate_evidence_immutable"] is True
