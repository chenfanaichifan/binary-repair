"""Persistence and mode selection for assistant plans."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.db.connection import connect
from app.domain.assistant import AssistantPlan, deterministic_plan
from app.services import jobs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_plan(job_id: str, *, data_dir: str | Path) -> dict[str, Any] | None:
    connection = connect(data_dir)
    try:
        row = connection.execute(
            "SELECT * FROM assistant_plans WHERE job_id = ? ORDER BY rowid DESC LIMIT 1",
            (job_id,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    return {
        "id": row["id"], "job_id": row["job_id"], "mode": row["mode"],
        "plan": json.loads(row["plan_json"]), "model": row["model"],
        "usage": json.loads(row["usage_json"]) if row["usage_json"] else None,
        "created_at": row["created_at"],
    }


def save_plan(job_id: str, plan: AssistantPlan, *, data_dir: str | Path,
              model: str | None = None, usage: dict | None = None) -> dict[str, Any]:
    if plan.job_id != job_id:
        raise ValueError("plan job_id does not match job")
    plan_id = uuid.uuid4().hex
    connection = connect(data_dir)
    try:
        with connection:
            connection.execute(
                "INSERT INTO assistant_plans "
                "(id, job_id, mode, plan_json, model, usage_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (plan_id, job_id, plan.mode, plan.model_dump_json(),
                 model, json.dumps(usage, sort_keys=True) if usage else None, _now()),
            )
    finally:
        connection.close()
    return {"id": plan_id, "job_id": job_id, "mode": plan.mode,
            "plan": plan.model_dump(), "model": model, "usage": usage}


def assistant_context(job: Any, *, data_dir: str | Path) -> dict[str, Any]:
    return {
        "id": job.id,
        "filename": job.filename,
        "defect_description": job.defect_description,
        "phase": job.phase,
        "original_sha256": job.original_sha256,
    }


def generate_plan(job_id: str, *, data_dir: str | Path,
                  mode: str | None = None, client: Any | None = None,
                  planner: Any | None = None) -> dict[str, Any]:
    """Generate a plan.

    T8.2 owner is M2.  The stable seam is ``planner`` (and its optional
    ``client``); M2 can change ``app.services.assistant_llm`` without editing
    this file.  Any planner exception falls back to the deterministic plan.
    """
    job = jobs.get_job(job_id, data_dir=data_dir)
    if job is None:
        raise ValueError("job not found")
    selected = (mode or os.environ.get("BINARYREPAIR_ASSISTANT_MODE", "scripted")).strip().lower()
    if selected == "scripted":
        return save_plan(job.id, deterministic_plan(assistant_context(job, data_dir=data_dir)),
                         data_dir=data_dir)
    if selected == "llm":
        try:
            selected_planner = planner
            if selected_planner is None:
                from app.services.assistant_llm import generate_llm_plan
                selected_planner = generate_llm_plan
            return selected_planner(job_id=job.id, data_dir=data_dir, client=client)
        except Exception as exc:
            fallback = deterministic_plan(assistant_context(job, data_dir=data_dir))
            fallback.fallback_reason = f"llm unavailable: {type(exc).__name__}: {exc}"[:500]
            return save_plan(job.id, fallback, data_dir=data_dir,
                             usage={"fallback": True})
    raise ValueError(f"unknown assistant mode: {selected!r}")


__all__ = ["assistant_context", "generate_plan", "get_plan", "save_plan"]
