"""Job controller for the identity/state contract.

Implements the §4.2 behaviours:

* ``create_job`` / ``get_job`` - identity from immutable input bytes;
* ``approve_contract`` - bind the input hash, contract revision, manifest hash,
  and scope hash;
* ``start_run`` - idempotent start; the same key returns the same run;
* restart recovery - all state is persisted in SQLite, and a fresh job is
  ``draft`` (never ``finished``).

This is the controller slice only. It contains no GUI code and no acceptance
logic; the GUI and the acceptance engine call it through this module.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True)
class Approval:
    """A reviewer approval bound to one contract revision."""

    job_id: str
    contract_id: str
    contract_revision: int
    input_sha256: str
    manifest_sha256: str
    scope_sha256: str
    reviewer_label: str
    approved_at: str


@dataclass(frozen=True)
class RunRecord:
    """One started attempt. ``id`` is stable across duplicate starts."""

    id: str
    job_id: str
    contract_id: str
    idempotency_key: str
    phase: str
    started_at: str


def _job_dir(data_dir: str | Path, job_id: str) -> Path:
    return Path(data_dir) / "jobs" / job_id


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _validate_sha256(name: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} must be a 64-character hex digest")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{name} must be a 64-character hex digest") from exc


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


def approve_contract(
    job_id: str,
    *,
    input_sha256: str,
    contract_revision: int,
    manifest_sha256: str,
    scope_sha256: str,
    reviewer_label: str,
    data_dir: str | Path,
) -> Approval:
    """Record a reviewer approval bound to the job's input and contract revision.

    A stale or mismatched input hash is rejected: approving one artifact and
    running another is exactly the failure this gate exists to prevent.
    """

    if contract_revision < 1:
        raise ValueError("contract_revision must be >= 1")
    _validate_sha256("input_sha256", input_sha256)
    _validate_sha256("manifest_sha256", manifest_sha256)
    _validate_sha256("scope_sha256", scope_sha256)

    connection = connect(data_dir)
    try:
        job = connection.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if job is None:
            raise ValueError(f"unknown job id: {job_id}")
        if input_sha256 != job["original_sha256"]:
            raise ValueError("approved input hash does not match the stored job bytes")

        with connection:
            existing = connection.execute(
                "SELECT * FROM contracts WHERE job_id = ? AND revision = ?",
                (job_id, contract_revision),
            ).fetchone()
            if existing is not None:
                if (
                    existing["input_sha256"] != input_sha256
                    or existing["manifest_sha256"] != manifest_sha256
                    or existing["scope_sha256"] != scope_sha256
                ):
                    raise ValueError(
                        "contract revision already exists with different approval content"
                    )
                contract_id = existing["id"]
                approved_at = existing["approved_at"]
            else:
                contract_id = uuid.uuid4().hex
                approved_at = _now()
                connection.execute(
                    "INSERT INTO contracts "
                    "(id, job_id, revision, input_sha256, manifest_sha256, "
                    " scope_sha256, reviewer_label, approved_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        contract_id,
                        job_id,
                        contract_revision,
                        input_sha256,
                        manifest_sha256,
                        scope_sha256,
                        reviewer_label,
                        approved_at,
                    ),
                )
                connection.execute(
                    "UPDATE jobs SET phase = 'awaiting_review' WHERE id = ?",
                    (job_id,),
                )
    finally:
        connection.close()

    return Approval(
        job_id=job_id,
        contract_id=contract_id,
        contract_revision=contract_revision,
        input_sha256=input_sha256,
        manifest_sha256=manifest_sha256,
        scope_sha256=scope_sha256,
        reviewer_label=reviewer_label,
        approved_at=approved_at,
    )


def _approval_field(approval: Any, name: str) -> Any:
    if isinstance(approval, dict):
        return approval.get(name)
    return getattr(approval, name, None)


def start_run(
    job_id: str,
    *,
    approval: Approval | dict[str, Any] | None,
    idempotency_key: str,
    data_dir: str | Path,
) -> RunRecord:
    """Start (or return) the run for one job and one idempotency key.

    The duplicate-start check and the insert happen in one ``BEGIN IMMEDIATE``
    transaction, so two callers racing on the same key still get one run.
    """

    if approval is None:
        raise ValueError("start_run requires an approval")
    if not idempotency_key:
        raise ValueError("idempotency_key must not be empty")
    if _approval_field(approval, "job_id") != job_id:
        raise ValueError("approval belongs to a different job")

    connection = connect(data_dir)
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                "SELECT * FROM runs WHERE job_id = ? AND idempotency_key = ?",
                (job_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                connection.commit()
                return RunRecord(
                    id=existing["id"],
                    job_id=existing["job_id"],
                    contract_id=existing["contract_id"],
                    idempotency_key=existing["idempotency_key"],
                    phase=existing["phase"],
                    started_at=existing["started_at"],
                )

            job = connection.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if job is None:
                raise ValueError(f"unknown job id: {job_id}")
            if _approval_field(approval, "input_sha256") != job["original_sha256"]:
                raise ValueError("approval input hash does not match the stored job bytes")

            contract_id = _approval_field(approval, "contract_id")
            contract = connection.execute(
                "SELECT * FROM contracts WHERE id = ? AND job_id = ?",
                (contract_id, job_id),
            ).fetchone()
            if contract is None:
                raise ValueError("approval contract is not part of this job")

            run_id = uuid.uuid4().hex
            started_at = _now()
            connection.execute(
                "INSERT INTO runs "
                "(id, job_id, contract_id, idempotency_key, phase, started_at) "
                "VALUES (?, ?, ?, ?, 'queued', ?)",
                (run_id, job_id, contract_id, idempotency_key, started_at),
            )
            connection.execute(
                "UPDATE jobs SET phase = 'queued' WHERE id = ?",
                (job_id,),
            )
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    finally:
        connection.close()

    return RunRecord(
        id=run_id,
        job_id=job_id,
        contract_id=contract_id,
        idempotency_key=idempotency_key,
        phase="queued",
        started_at=started_at,
    )


def cancel_job(job_id: str, *, data_dir: str | Path) -> JobRecord:
    """Mark a job and its runs as cancelled; state is persisted for restart."""

    connection = connect(data_dir)
    try:
        with connection:
            row = connection.execute(
                "SELECT id FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"unknown job id: {job_id}")
            connection.execute(
                "UPDATE jobs SET phase = 'cancelled' WHERE id = ?",
                (job_id,),
            )
            connection.execute(
                "UPDATE runs SET phase = 'cancelled' WHERE job_id = ?",
                (job_id,),
            )
    finally:
        connection.close()

    record = get_job(job_id, data_dir=data_dir)
    if record is None:
        raise ValueError(f"unknown job id: {job_id}")
    return record


__all__ = [
    "Approval",
    "JobRecord",
    "RunRecord",
    "approve_contract",
    "cancel_job",
    "create_job",
    "get_job",
    "start_run",
]
