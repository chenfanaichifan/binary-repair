"""Evidence observability scorecard: coverage only, never a verdict."""
from fastapi.testclient import TestClient

from app import demo
from app.main import SESSION_TOKEN, app
from app.services.evaluation import evaluate

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200


def _snapshot(**overrides):
    snapshot = {
        "id": "job-eval",
        "original_sha256": "a" * 64,
        "phase": "finished",
        "created_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:01:40Z",
        "verdict": {"outcome": "success_within_scope", "reason": "ok"},
        "routes": {
            "A": {
                "name": "Route A",
                "phase": "finished",
                "tests": {"passed": 4, "total": 4},
                "verification": "same",
                "compatibility": "same",
                "changed_regions": [1, 2],
                "elapsed_s": 80,
                "ai_usage": {"calls": 3, "tokens": 1200, "cost_usd": 0.021},
                "attempt_id": "att-1",
                "obligations": [
                    {"id": "o1", "result": "pass"},
                    {"id": "o2", "result": "pass"},
                    {"id": "o3", "result": "not_run"},
                ],
            }
        },
    }
    snapshot.update(overrides)
    return snapshot


def test_scorecard_reports_coverage_without_inventing_a_pass():
    payload = evaluate(
        _snapshot(),
        artifacts={"A": [{"id": "patch", "role": "candidate"}]},
        evidence_by_attempt={"att-1": {"v3": {"valid": {"passed": 4, "total": 4}}, "gates": []}},
        comparison_available=True,
    )
    assert payload["not_verdict"] is True
    assert payload["counts"]["obligations"]["total"] == 3
    assert payload["counts"]["obligations"]["pass"] == 2
    assert payload["counts"]["obligations"]["not_run"] == 1
    assert payload["scorecard"]["obligation_pass_rate"] == 66.7
    assert payload["scorecard"]["test_pass_rate"] == 100.0
    assert payload["scorecard"]["elapsed_seconds"] == 100.0
    assert payload["scorecard"]["observability_index"] > 0
    assert {row["level"] for row in payload["levels"] if row["available"]} >= {"V0", "V3", "V5"}


def test_zero_or_missing_denominators_are_na_not_pass():
    payload = evaluate({"id": "job-empty", "routes": {"A": {"tests": {"passed": 0, "total": 0}}}})
    assert payload["counts"]["tests"]["pass_rate"] is None
    assert payload["scorecard"]["test_pass_rate"] is None
    assert payload["scorecard"]["obligation_pass_rate"] is None
    assert any(item["kind"] == "no_tests" for item in payload["bottlenecks"])
    assert any(item["kind"] == "no_verdict" for item in payload["bottlenecks"])


def test_evaluation_route_is_read_only_and_available_for_a_mock_job():
    job = demo.create_job(
        original_sha256="b" * 64,
        filename="sample.elf",
        defect="stack overflow",
        valid_tests="hello",
        environment="local",
        valid_domain="input length 0-64",
        forbidden="out-of-bounds write",
        invalid_outcome="returns 1",
        assumptions="none",
    )
    response = client.get("/api/jobs/" + job["id"] + "/evaluation")
    assert response.status_code == 200
    payload = response.json()
    assert payload["not_verdict"] is True
    assert payload["job_id"] == job["id"]
    assert payload["scorecard"]["formula"]
    assert payload["levels"][0]["level"] == "V0"


def test_evaluation_route_404_is_explicit():
    response = client.get("/api/jobs/no-such-job/evaluation")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
