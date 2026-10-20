"""Job controller on the shared member-5 schema.

This is the controller-only slice: no GUI, no duplicate schema. It stores the
immutable input bytes under ``<data_dir>/jobs/<job_id>/`` and the presentation
fields (filename / defect description) in a sidecar ``meta.json`` because the
shared ``jobs`` table intentionally has no such columns.

Approval is persisted in ``contracts.body_json`` + ``contracts.sha256``; run
idempotency is scoped with a ``job_id:key`` prefix because ``runs.idempotency_key``
is globally unique in the shared schema.
"""

from __future__ import annotations

import hashlib
import json
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
    id: str
    original_sha256: str
    phase: str
    filename: str
    defect_description: str
    original_bytes: bytes
    created_at: str
    classification: str = "public"
    cancel_requested: int = 0


@dataclass(frozen=True)
class Approval:
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_atomic(
        path,
        json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2).encode("utf-8"),
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _meta_path(data_dir: str | Path, job_id: str) -> Path:
    return _job_dir(data_dir, job_id) / "meta.json"


def read_meta(job_id: str, *, data_dir: str | Path) -> dict[str, Any]:
    return _read_json(_meta_path(data_dir, job_id))


def write_meta(job_id: str, payload: dict[str, Any], *, data_dir: str | Path) -> None:
    _write_json(_meta_path(data_dir, job_id), payload)


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
    if not isinstance(original_bytes, (bytes, bytearray)):
        raise TypeError("original_bytes must be bytes")
    payload = bytes(original_bytes)
    job_id = uuid.uuid4().hex
    sha256 = hashlib.sha256(payload).hexdigest()
    relative_path = f"jobs/{job_id}/original.bin"
    _write_atomic(Path(data_dir) / relative_path, payload)
    _write_json(
        _meta_path(data_dir, job_id),
        {"filename": filename, "defect_description": defect_description},
    )

    created_at = _now()
    connection = connect(data_dir)
    try:
        with connection:
            connection.execute(
                "INSERT INTO jobs "
                "(id, original_sha256, classification, created_at, phase, cancel_requested) "
                "VALUES (?, ?, 'public', ?, 'draft', 0)",
                (job_id, sha256, created_at),
            )
            connection.execute(
                "INSERT INTO artifacts "
                "(id, job_id, attempt_id, relative_path, sha256, size_bytes, media_type, role, created_at) "
                "VALUES (?, ?, NULL, ?, ?, ?, 'application/octet-stream', 'original', ?)",
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
    connection = connect(data_dir)
    try:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
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
    meta = read_meta(job_id, data_dir=data_dir)

    return JobRecord(
        id=row["id"],
        original_sha256=row["original_sha256"],
        phase=row["phase"],
        filename=str(meta.get("filename", "")),
        defect_description=str(meta.get("defect_description", "")),
        original_bytes=original,
        created_at=row["created_at"],
        classification=row["classification"],
        cancel_requested=int(row["cancel_requested"]),
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
    if contract_revision < 1:
        raise ValueError("contract_revision must be >= 1")
    _validate_sha256("input_sha256", input_sha256)
    _validate_sha256("manifest_sha256", manifest_sha256)
    _validate_sha256("scope_sha256", scope_sha256)

    connection = connect(data_dir)
    try:
        job = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            raise ValueError(f"unknown job id: {job_id}")
        if input_sha256 != job["original_sha256"]:
            raise ValueError("approved input hash does not match the stored job bytes")

        body = {
            "input_sha256": input_sha256,
            "manifest_sha256": manifest_sha256,
            "scope_sha256": scope_sha256,
        }
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        contract_sha256 = hashlib.sha256(body_json.encode("utf-8")).hexdigest()

        with connection:
            existing = connection.execute(
                "SELECT * FROM contracts WHERE job_id = ? AND revision = ?",
                (job_id, contract_revision),
            ).fetchone()
            if existing is not None:
                if existing["body_json"] != body_json:
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
                    "(id, job_id, revision, body_json, sha256, approved_at, reviewer_label) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        contract_id,
                        job_id,
                        contract_revision,
                        body_json,
                        contract_sha256,
                        approved_at,
                        reviewer_label,
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


def get_contract(job_id: str, revision: int, *, data_dir: str | Path) -> Any:
    connection = connect(data_dir)
    try:
        return connection.execute(
            "SELECT * FROM contracts WHERE job_id = ? AND revision = ?",
            (job_id, revision),
        ).fetchone()
    finally:
        connection.close()


def contract_body(row: Any) -> dict[str, Any]:
    try:
        payload = json.loads(row["body_json"])
    except (KeyError, TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def approval_from_contract(row: Any) -> Approval:
    body = contract_body(row)
    return Approval(
        job_id=row["job_id"],
        contract_id=row["id"],
        contract_revision=int(row["revision"]),
        input_sha256=str(body.get("input_sha256", "")),
        manifest_sha256=str(body.get("manifest_sha256", "")),
        scope_sha256=str(body.get("scope_sha256", "")),
        reviewer_label=str(row["reviewer_label"] or ""),
        approved_at=str(row["approved_at"] or ""),
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
    if approval is None:
        raise ValueError("start_run requires an approval")
    if not idempotency_key:
        raise ValueError("idempotency_key must not be empty")
    if _approval_field(approval, "job_id") != job_id:
        raise ValueError("approval belongs to a different job")

    scoped_key = f"{job_id}:{idempotency_key}"
    connection = connect(data_dir)
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            existing = connection.execute(
                "SELECT * FROM runs WHERE idempotency_key = ?",
                (scoped_key,),
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

            job = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
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
                "(id, job_id, contract_id, manifest_sha256, idempotency_key, phase, started_at) "
                "VALUES (?, ?, ?, ?, ?, 'queued', ?)",
                (
                    run_id,
                    job_id,
                    contract_id,
                    _approval_field(approval, "manifest_sha256"),
                    scoped_key,
                    started_at,
                ),
            )
            connection.execute("UPDATE jobs SET phase = 'queued' WHERE id = ?", (job_id,))
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
    connection = connect(data_dir)
    try:
        with connection:
            row = connection.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                raise ValueError(f"unknown job id: {job_id}")
            connection.execute(
                "UPDATE jobs SET phase = 'cancelled', cancel_requested = 1 WHERE id = ?",
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
    "approval_from_contract",
    "approve_contract",
    "cancel_job",
    "contract_body",
    "create_job",
    "get_contract",
    "get_job",
    "read_meta",
    "start_run",
    "write_meta",
]
