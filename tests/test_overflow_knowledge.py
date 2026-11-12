"""Candidate memory: status + classification, explicitly not a verdict."""
from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from pathlib import Path

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200


def test_status_reports_synthetic_memory_and_limits():
    response = client.get("/api/knowledge/overflow")
    assert response.status_code == 200
    payload = response.json()
    assert payload["available"] is True
    assert payload["corpus"]["seeds"] == 12
    assert payload["corpus"]["variants"] == 1200
    assert "CWE-121" in payload["classes"]
    assert any("Synthetic" in item for item in payload["limits"])


def test_classifies_seed_as_candidate_without_verdict():
    code = (Path(__file__).resolve().parents[1] / "data" / "overflow-corpus" / "seeds" / "01_stack_strcpy.c").read_text(encoding="utf-8")
    response = client.post(
        "/api/knowledge/classify",
        headers={"X-CSRF-Token": CSRF_TOKEN},
        json={"code": code},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["not_verdict"] is True
    assert payload["classification"]["available"] is True
    assert payload["classification"]["candidate_only"] is True
    assert payload["classification"]["cwe"] == "CWE-121"


def test_classify_rejects_missing_code_with_csrf():
    response = client.post(
        "/api/knowledge/classify",
        headers={"X-CSRF-Token": CSRF_TOKEN},
        json={},
    )
    assert response.status_code == 422


def test_out_of_distribution_code_yields_no_candidate():
    response = client.post(
        "/api/knowledge/classify",
        headers={"X-CSRF-Token": CSRF_TOKEN},
        json={"code": "int main(void) { return 0; }"},
    )
    assert response.status_code == 200
    result = response.json()["classification"]
    assert result["cwe"] is None
    assert result["novelty"] is True
    assert result["confidence"] == 0.0
