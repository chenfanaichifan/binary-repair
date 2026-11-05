"""Evidence-envelope validation for acceptance.

A persisted ``passed`` result is only meaningful when its artifact row has bytes
on disk that match the recorded hash and belong to this job/attempt.  The pure
acceptance engine remains I/O-free; this module is the boundary that turns a
declaration into validated evidence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.db.connection import connect


class EvidenceError(ValueError):
    """Evidence is missing, outside the job store, or has the wrong bytes."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_store_path(data_dir: str | Path, relative_path: str) -> Path:
    root = Path(data_dir).resolve()
    candidate = (root / relative_path).resolve()
    job_root = (root / "jobs").resolve()
    try:
        candidate.relative_to(job_root)
    except ValueError as exc:
        raise EvidenceError(f"artifact path escapes the job store: {relative_path}") from exc
    if candidate.is_symlink():
        raise EvidenceError(f"artifact path is a symlink: {relative_path}")
    return candidate


def verify_artifact(
    *,
    data_dir: str | Path,
    job_id: str,
    attempt_id: str,
    artifact_id: str,
    gate: str,
) -> dict[str, Any]:
    """Return the verified artifact row or raise EvidenceError.

    V0 may use a job-level original artifact (attempt_id NULL).  V1-V5 must be
    bound to this attempt, so evidence copied from another attempt cannot pass.
    """

    connection = connect(data_dir)
    try:
        row = connection.execute(
            "SELECT * FROM artifacts WHERE id = ? AND job_id = ?",
            (artifact_id, job_id),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise EvidenceError(f"{gate} evidence artifact is not part of job {job_id}: {artifact_id}")
    bound_attempt = row["attempt_id"]
    if gate == "V0":
        if bound_attempt not in (None, attempt_id):
            raise EvidenceError(f"{gate} evidence belongs to another attempt: {bound_attempt}")
    elif bound_attempt != attempt_id:
        raise EvidenceError(f"{gate} evidence belongs to another attempt: {bound_attempt}")

    path = _resolve_store_path(data_dir, str(row["relative_path"]))
    if not path.is_file():
        raise EvidenceError(f"{gate} evidence file is missing: {path}")
    actual_size = path.stat().st_size
    if actual_size != int(row["size_bytes"]):
        raise EvidenceError(
            f"{gate} evidence size mismatch: recorded {row['size_bytes']}, actual {actual_size}"
        )
    actual_hash = _sha256(path)
    if actual_hash != str(row["sha256"]):
        raise EvidenceError(f"{gate} evidence hash mismatch: {actual_hash} != {row['sha256']}")
    return {
        "id": str(row["id"]),
        "attempt_id": bound_attempt,
        "relative_path": str(row["relative_path"]),
        "sha256": actual_hash,
        "size_bytes": actual_size,
    }


def verify_evidence_map(
    *,
    data_dir: str | Path,
    job_id: str,
    attempt_id: str,
    evidence: dict[str, str],
) -> dict[str, dict[str, Any]]:
    verified = {}
    for gate, artifact_id in evidence.items():
        if not artifact_id:
            continue
        verified[gate] = verify_artifact(
            data_dir=data_dir,
            job_id=job_id,
            attempt_id=attempt_id,
            artifact_id=artifact_id,
            gate=gate,
        )
    return verified


__all__ = ["EvidenceError", "verify_artifact", "verify_candidate_binding", "verify_evidence_map"]


def verify_candidate_binding(
    *,
    data_dir: str | Path,
    job_id: str,
    attempt_id: str,
    candidate_sha256: str,
    evidence: dict[str, str],
) -> dict[str, Any]:
    """Require at least one verified artifact to be the declared candidate bytes.

    A string in result JSON is not a binding; the bytes must exist in the job
    store under this attempt and hash to the declared candidate.
    """
    verified = verify_evidence_map(
        data_dir=data_dir, job_id=job_id, attempt_id=attempt_id, evidence=evidence
    )
    for gate, record in verified.items():
        if record["sha256"] == candidate_sha256:
            return record
    raise EvidenceError(
        f"candidate_sha256 {candidate_sha256} is not bound to any verified evidence artifact"
    )
