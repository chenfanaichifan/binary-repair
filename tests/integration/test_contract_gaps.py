"""Contract gaps M1 owned: attempt ids, obligation scope, honest ai_usage.

Each test starts from the real P3A/P3B packages so the rows under assertion are
produced by the worker, not fabricated.
"""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.controller_api import app
from app.db.connection import connect
from app.services import jobs, worker
from tools.route_bundle_ingest import ingest

REPO = Path(__file__).resolve().parents[2]
P3A = REPO / "artifacts" / "legacy-m5-evidence" / "P3A-routea-2026-10-31-v7.zip"
P3B = REPO / "artifacts" / "legacy-m5-evidence" / "P3B-package-v6-2026-10-31.zip"


def _unpack(archive: Path, target: Path) -> Path:
    with zipfile.ZipFile(archive) as handle:
        handle.extractall(target)
    return target


def _pipeline(tmp_path: Path) -> tuple[Path, object, object, dict[str, object]]:
    bundles = {
        "route_a": _unpack(P3A, tmp_path / "route_a"),
        "route_b": _unpack(P3B, tmp_path / "route_b"),
    }
    data = tmp_path / "var"
    original = (bundles["route_a"] / "original.elf").read_bytes()
    job = jobs.create_job(
        original_bytes=original,
        filename="sample.elf",
        defect_description="contract gap coverage",
        data_dir=data,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="m1",
        data_dir=data,
        input_sha256=job.original_sha256,
        manifest_sha256="2" * 64,
    )
    run = jobs.start_run(
        job.id, approval=approval, idempotency_key="contract-gaps", data_dir=data
    )
    attempts = {item.route: item for item in jobs.list_attempts(run.id, data_dir=data)}
    for route, bundle in bundles.items():
        ingest(
            data_dir=data,
            job_id=job.id,
            run_id=run.id,
            attempt_id=attempts[route].id,
            route=route,
            bundle=bundle,
            trigger=False,
        )
    worker.run_once(data_dir=data)
    return data, job, run, attempts


@pytest.fixture
def pipeline(tmp_path: Path, monkeypatch) -> tuple[TestClient, Path, object, object, dict]:
    data, job, run, attempts = _pipeline(tmp_path)
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(data))
    client = TestClient(app, base_url="http://127.0.0.1")
    return client, data, job, run, attempts


def test_attempts_endpoint_exposes_ids_that_open_evidence(pipeline) -> None:
    client, _data, job, run, attempts = pipeline
    payload = client.get(f"/api/jobs/{job.id}/attempts").json()

    rows = payload["attempts"]
    assert len(rows) == 2
    expected = {
        "id",
        "run_id",
        "route",
        "attempt_no",
        "status",
        "outcome",
        "started_at",
        "finished_at",
    }
    for row in rows:
        assert expected <= set(row)
        assert row["run_id"] == run.id
        assert row["attempt_no"] >= 0
        assert row["status"] == "finished"
        assert client.get(f"/api/attempts/{row['id']}/evidence").status_code == 200

    by_route = {row["route"]: row for row in rows}
    assert by_route["route_a"]["id"] == attempts["route_a"].id
    assert by_route["route_b"]["id"] == attempts["route_b"].id


def test_snapshot_routes_carry_the_attempt_id(pipeline) -> None:
    client, _data, job, _run, attempts = pipeline
    snapshot = client.get(f"/api/jobs/{job.id}").json()

    assert snapshot["routes"]["A"]["attempt_id"] == attempts["route_a"].id
    assert snapshot["routes"]["B"]["attempt_id"] == attempts["route_b"].id


def test_obligations_carry_the_scope_the_host_decided(pipeline) -> None:
    client, data, job, _run, attempts = pipeline

    expected = {
        "identity": "metadata",
        "structure": "binary",
        "interface": "binary",
        "behaviour": "replay",
        "symbolic": "model",
        "reproducibility": "replay",
    }
    groups = client.get(f"/api/jobs/{job.id}/obligations").json()
    for key in ("A", "B"):
        scopes = {row["kind"]: row["scope"] for row in groups[key]}
        assert scopes == expected, (key, scopes)

    # The stored value, not just the rendered one, carries the scope.
    connection = connect(data)
    try:
        stored = {
            row["kind"]: row["scope"]
            for row in connection.execute(
                "SELECT kind, scope FROM obligations WHERE attempt_id = ?",
                (attempts["route_a"].id,),
            )
        }
    finally:
        connection.close()
    assert stored == expected


def test_ai_usage_is_null_when_nothing_recorded_tokens(pipeline) -> None:
    client, _data, job, _run, _attempts = pipeline
    snapshot = client.get(f"/api/jobs/{job.id}").json()

    assert snapshot["routes"]["A"]["ai_usage"] is None
    assert snapshot["routes"]["B"]["ai_usage"] is None


def test_ai_usage_reports_recorded_tokens(pipeline) -> None:
    client, data, job, _run, _attempts = pipeline
    assert client.post(f"/api/jobs/{job.id}/assistant", json={}).status_code == 200

    connection = connect(data)
    try:
        connection.execute(
            "UPDATE assistant_plans SET usage_json = ? WHERE job_id = ?",
            (json.dumps({"input_tokens": 12, "output_tokens": 3}), job.id),
        )
        connection.commit()
    finally:
        connection.close()

    snapshot = client.get(f"/api/jobs/{job.id}").json()
    assert snapshot["routes"]["A"]["ai_usage"] == {
        "input_tokens": 12,
        "output_tokens": 3,
        "partial": False,
    }

def test_every_ingested_artifact_role_is_documented(pipeline) -> None:
    """A role the host writes must exist in the v1 table, or the UI is guessing."""
    _client, data, job, _run, _attempts = pipeline

    documented: set[str] = set()
    for line in (REPO / "docs" / "reference" / "interfaces" / "artifact-roles-v1.md").read_text(
        encoding="utf-8"
    ).splitlines():
        matched = re.match(r"^\|\s*`([a-z0-9_]+)`\s*\|", line)
        if matched:
            documented.add(matched.group(1))

    connection = connect(data)
    try:
        used = {
            row["role"]
            for row in connection.execute(
                "SELECT DISTINCT role FROM artifacts WHERE job_id = ?", (job.id,)
            )
        }
    finally:
        connection.close()

    assert used <= documented, sorted(used - documented)
    assert {"original", "v0_evidence", "v3_evidence"} <= used


def test_attempts_available_is_true_with_empty_list(pipeline) -> None:
    client, _data, _job, _run, _attempts = pipeline
    from app.services import jobs
    # Create a second job with no attempts; it must not be 404 or a fake list.
    job = jobs.create_job(
        original_bytes=b"\x7fELF empty attempts",
        filename="empty.elf",
        defect_description="no run yet",
        data_dir=_data,
    )
    payload = client.get(f"/api/jobs/{job.id}/attempts").json()
    assert payload == {"available": True, "job_id": job.id, "attempts": []}
