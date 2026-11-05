from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.db.connection import connect
from app.services import jobs, obligations


def _setup(tmp_path: Path):
    data = tmp_path / "var"
    job = jobs.create_job(original_bytes=b"\x7fELF evidence", filename="s.elf",
                          defect_description="overflow", data_dir=data)
    approval = jobs.approve_contract(job.id, contract_revision=1, reviewer_label="t",
                                     data_dir=data, input_sha256=job.original_sha256,
                                     manifest_sha256="1" * 64)
    run = jobs.start_run(job.id, approval=approval, idempotency_key="ev", data_dir=data)
    attempt = next(a for a in jobs.list_attempts(run.id, data_dir=data) if a.route == "route_a")
    return data, job, run, attempt


def _artifact(data: Path, job_id: str, attempt_id: str, *, content: bytes,
              relative: str, attempt_binding: str | None = None) -> str:
    target = data / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    artifact_id = "art-" + digest[:12]
    connection = connect(data)
    try:
        with connection:
            connection.execute(
                "INSERT INTO artifacts (id, job_id, attempt_id, relative_path, sha256, size_bytes, media_type, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'application/octet-stream', 'evidence', '2026-11-01T00:00:00+00:00')",
                (artifact_id, job_id, attempt_binding or attempt_id, relative, digest, len(content)),
            )
    finally:
        connection.close()
    return artifact_id


def test_passed_evidence_missing_file_is_rejected(tmp_path: Path) -> None:
    data, job, run, attempt = _setup(tmp_path)
    relative = f"jobs/{job.id}/evidence/{attempt.id}/missing.bin"
    artifact = _artifact(data, job.id, attempt.id, content=b"x", relative=relative)
    (data / relative).unlink()
    with pytest.raises(obligations.ObligationWriteError, match="missing"):
        obligations.persist_obligations(
            data_dir=data, job_id=job.id, attempt_id=attempt.id,
            results={"V1": "passed"}, evidence={"V1": artifact},
        )


def test_evidence_from_another_attempt_is_rejected(tmp_path: Path) -> None:
    data, job, run, attempt = _setup(tmp_path)
    other = next(a for a in jobs.list_attempts(run.id, data_dir=data) if a.id != attempt.id)
    relative = f"jobs/{job.id}/evidence/{other.id}/cross.bin"
    artifact = _artifact(data, job.id, other.id, content=b"cross", relative=relative)
    with pytest.raises(obligations.ObligationWriteError, match="another attempt"):
        obligations.persist_obligations(
            data_dir=data, job_id=job.id, attempt_id=attempt.id,
            results={"V1": "passed"}, evidence={"V1": artifact},
        )


def test_candidate_hash_must_match_a_real_artifact(tmp_path: Path) -> None:
    from app.domain.evidence import EvidenceError, verify_candidate_binding
    data, job, run, attempt = _setup(tmp_path)
    relative = f"jobs/{job.id}/evidence/{attempt.id}/candidate.bin"
    artifact = _artifact(data, job.id, attempt.id, content=b"not the candidate", relative=relative)
    with pytest.raises(EvidenceError, match="not bound"):
        verify_candidate_binding(
            data_dir=data, job_id=job.id, attempt_id=attempt.id,
            candidate_sha256="a" * 64, evidence={"V0": artifact},
        )
