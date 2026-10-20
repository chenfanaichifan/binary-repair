"""Minimal job controller for the identity contract.

First delivery only: ``create_job`` and ``get_job``. Approval, run start, and
idempotency are deliberately not implemented yet; their contract tests skip
until those functions exist.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.db.connection import connect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class JobRecord:
    """A job identity plus the immutable input bytes it describes."""

    id: str
    original_sha256: str
    phase: str
    filename: str
    defect_description: str
    original_bytes: bytes
    created_at: str


def _job_dir(data_dir: str | Path, job_id: str) -> Path:
    return Path(data_dir) / "jobs" / job_id


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def create_job(
    *,
    original_bytes: bytes,
    filename: str,
    defect_description: str,
    data_dir: str | Path,
) -> JobRecord:
    """Persist the input bytes once and return the new job identity."""

    if not isinstance(original_bytes, (bytes, bytearray)):
        raise TypeError("original_bytes must be bytes")
    payload = bytes(original_bytes)
    job_id = uuid.uuid4().hex
    sha256 = hashlib.sha256(payload).hexdigest()
    relative_path = f"jobs/{job_id}/original.bin"
    _write_atomic(Path(data_dir) / relative_path, payload)

    created_at = _now()
    connection = connect(data_dir)
    try:
        with connection:
            connection.execute(
                "INSERT INTO jobs "
                "(id, original_sha256, filename, defect_description, phase, created_at) "
                "VALUES (?, ?, ?, ?, 'draft', ?)",
                (job_id, sha256, filename, defect_description, created_at),
            )
            connection.execute(
                "INSERT INTO artifacts "
                "(id, job_id, role, relative_path, sha256, size_bytes, created_at) "
                "VALUES (?, ?, 'original', ?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    job_id,
                    relative_path,
                    sha256,
                    len(payload),
                    created_at,
                ),
            )
    finally:
        connection.close()

    return JobRecord(
        id=job_id,
        original_sha256=sha256,
        phase="draft",
        filename=filename,
        defect_description=defect_description,
        original_bytes=payload,
        created_at=created_at,
    )


def get_job(job_id: str, *, data_dir: str | Path) -> JobRecord | None:
    """Read a job by id; return ``None`` when it does not exist."""

    connection = connect(data_dir)
    try:
        row = connection.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if row is None:
            return None
        artifact = connection.execute(
            "SELECT relative_path FROM artifacts WHERE job_id = ? AND role = 'original'",
            (job_id,),
        ).fetchone()
    finally:
        connection.close()

    original = b""
    if artifact is not None:
        path = Path(data_dir) / artifact["relative_path"]
        if path.exists():
            original = path.read_bytes()

    return JobRecord(
        id=row["id"],
        original_sha256=row["original_sha256"],
        phase=row["phase"],
        filename=row["filename"],
        defect_description=row["defect_description"],
        original_bytes=original,
        created_at=row["created_at"],
    )


__all__ = ["JobRecord", "create_job", "get_job"]
