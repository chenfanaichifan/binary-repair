"""T8.1 persistence and the stable T8.2 planner seam."""

from __future__ import annotations

import json
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
            "SELECT * FROM assistant_plans WHERE job_id = ? AND superseded_by IS NULL "
            "ORDER BY rowid DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if row is None:
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
        "version": row["version"], "message_id": row["message_id"],
        "superseded_by": row["superseded_by"],
        "created_at": row["created_at"],
    }


def save_plan(job_id: str, plan: AssistantPlan, *, data_dir: str | Path,
              model: str | None = None, usage: dict | None = None,
              message_id: str | None = None) -> dict[str, Any]:
    plan_id = plan.plan_id
    connection = connect(data_dir)
    try:
        with connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM assistant_plans WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            version = int(row["v"]) + 1
            previous = connection.execute(
                "SELECT id FROM assistant_plans WHERE job_id = ? AND superseded_by IS NULL "
                "ORDER BY rowid DESC LIMIT 1",
                (job_id,),
            ).fetchone()
            if previous is not None:
                connection.execute(
                    "UPDATE assistant_plans SET superseded_by = ? WHERE id = ?",
                    (plan_id, previous["id"]),
                )
            connection.execute(
                "INSERT INTO assistant_plans "
                "(id, job_id, mode, plan_json, model, usage_json, version, message_id, superseded_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                (plan_id, job_id, plan.mode, plan.model_dump_json(),
                 model or plan.model,
                 json.dumps(usage, sort_keys=True) if usage else None,
                 version, message_id, _now()),
            )
    finally:
        connection.close()
    return {"id": plan_id, "job_id": job_id, "mode": plan.mode,
            "plan": plan.model_dump(), "model": model or plan.model,
            "usage": usage, "version": version, "message_id": message_id,
            "superseded_by": None}


def append_message(job_id: str, role: str, content: str, *,
                   data_dir: str | Path, plan_id: str | None = None) -> dict[str, Any]:
    if role not in {"user", "assistant", "system"}:
        raise ValueError("invalid assistant message role")
    if not content.strip():
        raise ValueError("assistant message content must not be empty")
    message_id = uuid.uuid4().hex
    connection = connect(data_dir)
    try:
        with connection:
            connection.execute(
                "INSERT INTO assistant_messages (id, job_id, role, content, plan_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, job_id, role, content, plan_id, _now()),
            )
    finally:
        connection.close()
    return {"id": message_id, "job_id": job_id, "role": role,
            "content": content, "plan_id": plan_id}


def list_messages(job_id: str, *, data_dir: str | Path) -> list[dict[str, Any]]:
    connection = connect(data_dir)
    try:
        rows = connection.execute(
            "SELECT * FROM assistant_messages WHERE job_id = ? ORDER BY rowid",
            (job_id,),
        ).fetchall()
    finally:
        connection.close()
    return [{"id": row["id"], "job_id": row["job_id"], "role": row["role"],
             "content": row["content"], "plan_id": row["plan_id"],
             "created_at": row["created_at"]} for row in rows]


def assistant_context(job: Any, *, data_dir: str | Path) -> dict[str, Any]:
    return {
        "id": job.id,
        "filename": job.filename,
        "defect_description": job.defect_description,
        "phase": job.phase,
        "original_sha256": job.original_sha256,
    }


def generate_plan(description: str | None = None, *, context: dict | None = None,
                  client: Any | None = None, job_id: str | None = None,
                  data_dir: str | Path | None = None,
                  planner: Any | None = None,
                  mode: str | None = None) -> AssistantPlan:
    """Return a plan; when job_id/data_dir are supplied, persist it.

    T8.2 owns the ``client`` branch.  Without a client this is the pure
    deterministic planner and never reads the environment.
    """
    if mode not in (None, "deterministic", "llm"):
        raise ValueError(f"unknown assistant mode: {mode!r}")
    if description is None:
        if job_id is None or data_dir is None:
            raise ValueError("description or job_id+data_dir is required")
        job = jobs.get_job(job_id, data_dir=data_dir)
        if job is None:
            raise ValueError("job not found")
        description = job.defect_description
        if context is None:
            context = assistant_context(job, data_dir=data_dir)

    if planner is not None:
        plan = planner(description=description, context=context, client=client)
    elif client is not None:
        from app.services.assistant_llm import generate_plan as llm_plan
        plan = llm_plan(description, context=context, client=client, mode="llm")
    else:
        plan = deterministic_plan(description, context)

    if not isinstance(plan, AssistantPlan):
        plan = AssistantPlan.model_validate(plan)
    if job_id is not None and data_dir is not None:
        save_plan(job_id, plan, data_dir=data_dir)
    return plan


__all__ = ["append_message", "assistant_context", "generate_plan", "get_plan",
           "list_messages", "save_plan"]
