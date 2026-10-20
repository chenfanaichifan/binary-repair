"""HTTP API for the controller-only service.

Canonical routes follow Tech Design §7:

    POST /api/jobs
    GET  /api/jobs/{id}
    POST /api/jobs/{id}/approve
    POST /api/jobs/{id}/runs
    GET  /api/attempts/{id}/evidence

GUI compatibility aliases (same implementation, no second decision logic):

    POST /api/jobs/{id}/start
    POST /api/jobs/{id}/cancel
    GET  /api/jobs/{id}/obligations
    GET  /api/jobs/{id}/artifacts
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.db.connection import connect
from app.services import jobs

APP_ENV = "BINARYREPAIR_DATA_DIR"
DEFAULT_DATA_DIR = "var"

ROUTE_STAGES: dict[str, list[str]] = {
    "A": ["screening", "analyzing", "generating", "applying", "validating"],
    "B": ["screening", "analyzing", "roundtrip", "generating", "applying", "validating"],
}
ROUTE_NAMES: dict[str, str] = {
    "A": "Route A - Direct instruction repair",
    "B": "Route B - Recovered C reintegration",
}
_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
_CJK = re.compile(r"[\u2e80-\u2fff\u3000-\u303f\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]")


def _data_dir() -> Path:
    return Path(os.environ.get(APP_ENV, DEFAULT_DATA_DIR))


def _sha_json(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ascii_filename(name: str) -> str:
    base = Path(name or "").name
    if base and base.isascii() and _UNSAFE_FILENAME.search(base) is None:
        return base
    stem, dot, suffix = base.rpartition(".")
    stem_clean = _UNSAFE_FILENAME.sub("_", stem).strip("_-") if stem else ""
    suffix_clean = _UNSAFE_FILENAME.sub("", suffix) if dot else ""
    if not stem_clean:
        stem_clean = "uploaded-sample"
    return f"{stem_clean}.{suffix_clean}" if suffix_clean else stem_clean


def _require_english(fields: dict[str, str]) -> None:
    for name, value in fields.items():
        if value and any(ord(char) > 127 for char in value):
            raise HTTPException(
                status_code=422,
                detail=f"Field '{name}' must use English/ASCII characters only.",
            )


def _contract_body(
    *,
    valid_domain: str = "",
    forbidden: str = "",
    invalid_outcome: str = "",
    assumptions: str = "",
) -> dict[str, Any]:
    body = {
        "valid_domain": valid_domain.strip()
        or "Input length 0-64 bytes; out-of-range lengths rejected",
        "forbidden": forbidden.strip()
        or "Out-of-bounds write to the target buffer",
        "invalid_outcome": invalid_outcome.strip()
        or "Return error code 1 without out-of-bounds access",
        "assumptions": [
            line.strip()
            for line in (
                assumptions
                or "Single process\nLinux x86-64 ELF\nStack protector disabled"
            ).splitlines()
            if line.strip()
        ],
    }
    return {"revision": 1, "sha256": _sha_json(body), **body}


def _job_or_404(job_id: str) -> jobs.JobRecord:
    record = jobs.get_job(job_id, data_dir=_data_dir())
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return record


def _placeholder_routes(phase: str) -> dict[str, dict[str, Any]]:
    routes: dict[str, dict[str, Any]] = {}
    for key, stages in ROUTE_STAGES.items():
        routes[key] = {
            "name": ROUTE_NAMES[key],
            "phase": phase,
            "outcome": None,
            "outcome_reason": "",
            "stages": [{"name": name, "state": "pending"} for name in stages],
            "tests": {"passed": 0, "total": 0},
            "verification": "not_run",
            "compatibility": "not_run",
            "changed_regions": [],
            "manual_interventions": 0,
            "ai_usage": "unavailable",
            "elapsed_s": 0.0,
        }
    return routes


def _snapshot(record: jobs.JobRecord, meta: dict[str, Any]) -> dict[str, Any]:
    contract = meta.get("contract")
    if not isinstance(contract, dict):
        contract = _contract_body()
    return {
        "id": record.id,
        "demo": False,
        "data_source": "controller-http",
        "execution": "not_started" if record.phase == "draft" else record.phase,
        "filename": record.filename,
        "original_sha256": record.original_sha256,
        "defect": record.defect_description,
        "valid_tests": meta.get("valid_tests", []),
        "environment": meta.get("environment", ""),
        "created_at": record.created_at,
        "phase": record.phase,
        "cancelled": record.phase == "cancelled",
        "contract": contract,
        "routes": _placeholder_routes(record.phase),
    }


def _obligations() -> dict[str, list[dict[str, Any]]]:
    identity = {
        "id": "V0",
        "kind": "Identity and preconditions",
        "description": "Job record exists and the original hash matches the stored bytes",
        "required": True,
        "result": "passed",
        "scope": "controller job store",
        "reason": "Job record and original hash verified.",
    }
    pending = [
        {
            "id": f"V{index}",
            "kind": label,
            "description": description,
            "required": True,
            "result": "not_run",
            "scope": "n/a",
            "reason": "Repair execution is not implemented by the controller yet.",
        }
        for index, label, description in (
            (1, "Structure and placement", "Instruction boundaries, changed intervals, and branch targets are auditable"),
            (2, "Interface and compatibility", "Signature, stack/register conventions, and loader execution checks"),
            (3, "Concrete behavior", "Reproducer, invalid-input oracle, valid-input regression"),
            (4, "Bounded symbolic security", "Candidate-specific model, input domain, out-of-bounds access predicate"),
            (5, "Reproducibility", "Final hashes, versions, replay inputs, independent replay"),
        )
    ]
    return {
        "A": [dict(identity), *[dict(item) for item in pending]],
        "B": [dict(identity), *[dict(item) for item in pending]],
    }


class ApproveRequest(BaseModel):
    input_sha256: str = Field(min_length=64, max_length=64)
    contract_revision: int = Field(ge=1)
    manifest_sha256: str = Field(min_length=64, max_length=64)
    scope_sha256: str = Field(min_length=64, max_length=64)
    reviewer_label: str = Field(min_length=1, max_length=128)


class RunRequest(BaseModel):
    contract_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=128)


app = FastAPI(title="BinaryRepair Controller API", version="0.2.0")


@app.middleware("http")
async def local_only(request: Request, call_next):
    host = (request.headers.get("host") or "").split(":")[0].strip().lower()
    if host not in {"127.0.0.1", "localhost"}:
        return JSONResponse(
            {"detail": "Local access only (host check failed)."},
            status_code=403,
        )
    return await call_next(request)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "service": "binaryrepair-controller"}


@app.post("/api/jobs", status_code=201)
async def create_job(
    binary: UploadFile = File(...),
    defect: str = Form(""),
    valid_tests: str = Form(""),
    environment: str = Form(""),
    valid_domain: str = Form(""),
    forbidden: str = Form(""),
    invalid_outcome: str = Form(""),
    assumptions: str = Form(""),
) -> dict[str, Any]:
    _require_english(
        {
            "defect": defect,
            "valid_tests": valid_tests,
            "environment": environment,
            "valid_domain": valid_domain,
            "forbidden": forbidden,
            "invalid_outcome": invalid_outcome,
            "assumptions": assumptions,
        }
    )
    payload = await binary.read()
    if not payload:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")

    filename = _ascii_filename(binary.filename or "sample.bin")
    record = jobs.create_job(
        original_bytes=payload,
        filename=filename,
        defect_description=defect or "Defect description not provided.",
        data_dir=_data_dir(),
    )
    tests = [line.strip() for line in valid_tests.splitlines() if line.strip()]
    contract = _contract_body(
        valid_domain=valid_domain,
        forbidden=forbidden,
        invalid_outcome=invalid_outcome,
        assumptions=assumptions,
    )
    meta = jobs.read_meta(record.id, data_dir=_data_dir())
    meta.update(
        {
            "valid_tests": tests,
            "environment": environment.strip()
            or "Ubuntu x86-64 VM (execution not implemented)",
            "contract": contract,
            "manifest_sha256": _sha_json(tests),
            "scope_sha256": contract["sha256"],
        }
    )
    jobs.write_meta(record.id, meta, data_dir=_data_dir())
    return {"id": record.id, "original_sha256": record.original_sha256, "phase": record.phase}


@app.get("/api/jobs/{job_id}")
def get_snapshot(job_id: str) -> dict[str, Any]:
    record = _job_or_404(job_id)
    return _snapshot(record, jobs.read_meta(job_id, data_dir=_data_dir()))


@app.post("/api/jobs/{job_id}/approve")
def approve(job_id: str, body: ApproveRequest) -> dict[str, Any]:
    _job_or_404(job_id)
    try:
        approval = jobs.approve_contract(
            job_id,
            input_sha256=body.input_sha256,
            contract_revision=body.contract_revision,
            manifest_sha256=body.manifest_sha256,
            scope_sha256=body.scope_sha256,
            reviewer_label=body.reviewer_label,
            data_dir=_data_dir(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "job_id": approval.job_id,
        "contract_id": approval.contract_id,
        "contract_revision": approval.contract_revision,
        "input_sha256": approval.input_sha256,
        "manifest_sha256": approval.manifest_sha256,
        "scope_sha256": approval.scope_sha256,
        "reviewer_label": approval.reviewer_label,
        "approved_at": approval.approved_at,
    }


@app.post("/api/jobs/{job_id}/runs", status_code=202)
def start_run(job_id: str, body: RunRequest) -> dict[str, Any]:
    record = _job_or_404(job_id)
    if record.phase == "cancelled":
        raise HTTPException(status_code=409, detail="Job is cancelled; a new job is required.")
    contract = jobs.get_contract(job_id, body.contract_revision, data_dir=_data_dir())
    if contract is None:
        raise HTTPException(status_code=409, detail="No approval for this contract revision.")
    try:
        run = jobs.start_run(
            job_id,
            approval=jobs.approval_from_contract(contract),
            idempotency_key=body.idempotency_key,
            data_dir=_data_dir(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": run.id, "phase": run.phase}


@app.post("/api/jobs/{job_id}/start", status_code=202)
def start_alias(job_id: str) -> dict[str, Any]:
    """GUI compatibility alias: approve from the stored contract, then start."""

    record = _job_or_404(job_id)
    if record.phase == "cancelled":
        raise HTTPException(status_code=409, detail="Job is cancelled; a new job is required.")
    meta = jobs.read_meta(job_id, data_dir=_data_dir())
    contract = meta.get("contract")
    if not isinstance(contract, dict) or not meta.get("manifest_sha256") or not meta.get("scope_sha256"):
        raise HTTPException(status_code=409, detail="Job has no reviewed contract metadata.")
    try:
        approval = jobs.approve_contract(
            job_id,
            input_sha256=record.original_sha256,
            contract_revision=int(contract["revision"]),
            manifest_sha256=str(meta["manifest_sha256"]),
            scope_sha256=str(meta["scope_sha256"]),
            reviewer_label="controller-http",
            data_dir=_data_dir(),
        )
        run = jobs.start_run(
            job_id,
            approval=approval,
            idempotency_key="http-start-v1",
            data_dir=_data_dir(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"id": run.id, "phase": run.phase}


@app.post("/api/jobs/{job_id}/cancel", status_code=202)
def cancel(job_id: str) -> dict[str, Any]:
    try:
        record = jobs.cancel_job(job_id, data_dir=_data_dir())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc
    return {"id": record.id, "phase": record.phase}


@app.get("/api/jobs/{job_id}/obligations")
def obligations_alias(job_id: str) -> dict[str, list[dict[str, Any]]]:
    _job_or_404(job_id)
    return _obligations()


@app.get("/api/attempts/{attempt_id}/evidence")
def attempt_evidence(attempt_id: str) -> dict[str, Any]:
    connection = connect(_data_dir())
    try:
        attempt = connection.execute(
            "SELECT * FROM attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()
    finally:
        connection.close()
    if attempt is None:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    return {
        "attempt_id": attempt["id"],
        "run_id": attempt["run_id"],
        "route": attempt["route"],
        "candidate_sha256": attempt["candidate_sha256"],
        "outcome": attempt["outcome"],
        "reason_code": attempt["reason_code"],
        "obligations": _obligations(),
    }


@app.get("/api/jobs/{job_id}/artifacts")
def artifacts(job_id: str) -> dict[str, list[dict[str, Any]]]:
    _job_or_404(job_id)
    connection = connect(_data_dir())
    try:
        rows = connection.execute(
            "SELECT * FROM artifacts WHERE job_id = ? ORDER BY created_at",
            (job_id,),
        ).fetchall()
    finally:
        connection.close()
    return {
        "A": [
            {
                "name": Path(row["relative_path"]).name,
                "role": row["role"],
                "sha256": row["sha256"],
                "size_bytes": row["size_bytes"],
                "media_type": row["media_type"],
            }
            for row in rows
        ],
        "B": [],
    }
