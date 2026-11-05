from __future__ import annotations

import hashlib
from pathlib import Path

from app.db.connection import connect
from app.services import jobs, obligations


def _setup(tmp_path: Path):
    data = tmp_path / "var"
    job = jobs.create_job(
        original_bytes=b"\x7fELF v3 kind",
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
    run = jobs.start_run(job.id, approval=approval, idempotency_key="v3k", data_dir=data)
    attempt = next(
        a for a in jobs.list_attempts(run.id, data_dir=data) if a.route == "route_a"
    )
    return data, job, run, attempt


def _artifact(data: Path, job_id: str, attempt_id: str, *, content: bytes) -> str:
    relative = f"jobs/{job_id}/evidence/{attempt_id}/repaired.bin"
    target = data / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    artifact_id = "art-" + digest[:12]
    connection = connect(data)
    try:
        with connection:
            connection.execute(
                "INSERT INTO artifacts (id, job_id, attempt_id, relative_path, sha256, "
                "size_bytes, media_type, role, created_at) VALUES "
                "(?, ?, ?, ?, ?, ?, 'application/octet-stream', 'routeb_manifest_repaired', "
                "'2026-11-01T00:00:00+00:00')",
                (artifact_id, job_id, attempt_id, relative, digest, len(content)),
            )
    finally:
        connection.close()
    return artifact_id


def test_round_trip_is_persisted_as_its_own_kind(tmp_path: Path) -> None:
    data, job, _run, attempt = _setup(tmp_path)
    obligations.persist_obligations(
        data_dir=data,
        job_id=job.id,
        attempt_id=attempt.id,
        results={"V3": "not_run"},
        details={"V3": "round-trip only; not repair V3", "V3_kind": "round_trip"},
    )

    rows = {row["kind"]: row for row in jobs.list_obligations(attempt.id, data_dir=data)}
    assert rows["round_trip"]["required"] is False
    assert rows["round_trip"]["scope"] == "replay"
    assert rows["round_trip"]["result"] == "not_run"
    # The gate row stays not_run: an unchanged trip never earns V3.
    assert rows["behaviour"]["result"] == "not_run"
    assert "repaired_behaviour" not in rows


def test_repaired_behaviour_row_carries_the_v3_evidence(tmp_path: Path) -> None:
    data, job, _run, attempt = _setup(tmp_path)
    artifact = _artifact(data, job.id, attempt.id, content=b"repaired elf")
    obligations.persist_obligations(
        data_dir=data,
        job_id=job.id,
        attempt_id=attempt.id,
        results={"V3": "passed"},
        evidence={"V3": artifact},
        details={"V3": "runtime manifest passed", "V3_kind": "repaired_behaviour"},
    )

    rows = {row["kind"]: row for row in jobs.list_obligations(attempt.id, data_dir=data)}
    assert rows["behaviour"]["result"] == "passed"
    assert rows["repaired_behaviour"]["required"] is False
    assert rows["repaired_behaviour"]["evidence_artifact_id"] == artifact
    assert rows["repaired_behaviour"]["scope"] == "replay"
    assert "round_trip" not in rows
