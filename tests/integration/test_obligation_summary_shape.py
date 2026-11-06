from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.controller_api import _obligation_summary, app
from app.services import jobs, obligations


def _attempt(tmp_path: Path):
    data = tmp_path / "var"
    job = jobs.create_job(
        original_bytes=b"\x7fELF summary",
        filename="s.elf",
        defect_description="overflow",
        data_dir=data,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="t",
        data_dir=data,
        input_sha256=job.original_sha256,
        manifest_sha256="1" * 64,
    )
    run = jobs.start_run(job.id, approval=approval, idempotency_key="sum", data_dir=data)
    attempt = next(
        a for a in jobs.list_attempts(run.id, data_dir=data) if a.route == "route_a"
    )
    return data, job, run, attempt


def test_evidence_summary_is_zero_invalid_and_marks_v3_as_a_gate(
    tmp_path: Path, monkeypatch
) -> None:
    data, job, _run, attempt = _attempt(tmp_path)
    # Only V0 can pass without extra evidence: it falls back to the job's
    # original artifact. V1/V2/V4 are re-validated against their own evidence
    # (structure, interface, typed symbolic), so a bare "passed" is downgraded
    # to not_run instead of being written as a pass. That is the shape this
    # test needs to observe, not a workaround.
    obligations.persist_obligations(
        data_dir=data,
        job_id=job.id,
        attempt_id=attempt.id,
        results={
            "V0": "passed",
            "V1": "not_run",
            "V2": "not_run",
            "V3": "not_run",
            "V4": "not_run",
            "V5": "not_run",
        },
    )
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(data))

    response = TestClient(app, base_url="http://127.0.0.1").get(
        f"/api/attempts/{attempt.id}/evidence"
    )
    assert response.status_code == 200, response.text
    body = response.json()

    summary = body["summary"]
    assert summary["invalid"] == {"total": 0, "items": []}
    assert summary["total"] == 6
    assert summary["required_total"] == 6
    assert summary["gate_ids"] == ["V0", "V1", "V2", "V3", "V4", "V5"]
    assert summary["by_result"] == {
        "passed": 1,
        "failed": 0,
        "not_run": 5,
        "unknown": 0,
        "timed_out": 0,
    }

    rows = {row["id"]: row for row in body["obligations"]["A"]}
    assert set(rows) == {"V0", "V1", "V2", "V3", "V4", "V5"}
    v3 = rows["V3"]
    assert v3["kind"] == "behaviour"
    assert v3["required"] is True
    assert v3["gate"] is True
    assert v3["scope"] == "replay"
    assert v3["result"] == "not_run"
    assert body["obligations"]["B"] == []


def test_summary_reports_an_unmappable_kind_as_invalid() -> None:
    summary = _obligation_summary(
        [
            {
                "kind": "mystery",
                "scope": "metadata",
                "required": True,
                "result": "passed",
                "evidence_artifact_id": None,
                "detail": "",
            }
        ]
    )
    assert summary["invalid"]["total"] == 1
    assert summary["invalid"]["items"][0]["kind"] == "mystery"
    assert summary["gate_ids"] == []
