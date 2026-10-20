"""Orchestration: V0-V5 -> acceptance engine -> persisted Verdict.

The acceptance engine lives in ``app/domain`` and is supplied by step ② of the
integration. This module imports it lazily, so the controller-only branch can
exist before that step lands; calling the orchestration without the domain is an
ImportError, not a silent fallback.

Sequence:

1. after start, the run executor persists V0-V5 results;
2. ``evaluate_attempt`` is called once per route;
3. after both routes, ``evaluate_run`` is called once.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.db.connection import connect

GATES: tuple[tuple[str, str, bool], ...] = (
    ("V0", "identity", True),
    ("V1", "structure", True),
    ("V2", "interface", True),
    ("V3", "behaviour", True),
    ("V4", "symbolic", True),
    ("V5", "reproducibility", True),
)


def _gate_result(value: str | Any) -> Any:
    from app.domain.outcomes import CheckResult

    if isinstance(value, CheckResult):
        return value
    try:
        return CheckResult(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown check result: {value!r}") from exc


def build_obligations(
    results: Mapping[str, str | Any],
    *,
    required: Mapping[str, bool] | None = None,
) -> list[Any]:
    from app.domain.acceptance import Obligation

    required = required or {}
    obligations = []
    for gate, kind, default_required in GATES:
        result = _gate_result(results.get(gate, "not_run"))
        obligations.append(
            Obligation(
                kind=kind,
                required=required.get(gate, default_required),
                result=result,
                detail=f"{gate} {kind}: {result.value}",
            )
        )
    return obligations


def _verdict_payload(verdict: Any) -> dict[str, Any]:
    return {
        "outcome": verdict.outcome.value,
        "reason": verdict.reason.value if verdict.reason is not None else None,
        "failing_obligation": verdict.failing_obligation,
        "detail": verdict.detail,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp.replace(path)


def _run_context(job_id: str, run_id: str, data_dir: str | Path) -> tuple[Any, dict[str, Any]]:
    connection = connect(data_dir)
    try:
        run = connection.execute(
            "SELECT * FROM runs WHERE id = ? AND job_id = ?",
            (run_id, job_id),
        ).fetchone()
        if run is None:
            raise ValueError(f"unknown run id for job {job_id}: {run_id}")
        job = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if job is None:
            raise ValueError(f"unknown job id: {job_id}")
    finally:
        connection.close()
    return run, {
        "input_sha256": job["original_sha256"],
        "scope_sha256": run["reviewed_scope_sha256"],
    }


def evaluate_attempt(
    job_id: str,
    run_id: str,
    *,
    results: Mapping[str, str | Any],
    data_dir: str | Path,
    candidate_sha256: str,
    required: Mapping[str, bool] | None = None,
    cancelled: bool = False,
    error_reason: Any = None,
    error_detail: str = "",
    unsupported_reason: Any = None,
    unsupported_detail: str = "",
) -> Any:
    from app.domain.acceptance import decide_attempt_outcome

    run, body = _run_context(job_id, run_id, data_dir)
    obligations = build_obligations(results, required=required)
    verdict = decide_attempt_outcome(
        obligations=obligations,
        candidate_sha256=candidate_sha256,
        expected_sha256=body.get("input_sha256"),
        reviewed_scope_sha256=body.get("scope_sha256"),
        cancelled=cancelled,
        error_reason=error_reason,
        error_detail=error_detail,
        unsupported_reason=unsupported_reason,
        unsupported_detail=unsupported_detail,
    )
    _write_json(
        Path(data_dir) / "jobs" / job_id / "runs" / run_id / "verdict.json",
        {
            "job_id": job_id,
            "run_id": run_id,
            "candidate_sha256": candidate_sha256,
            "expected_sha256": body.get("input_sha256"),
            "reviewed_scope_sha256": body.get("scope_sha256"),
            "obligations": [
                {
                    "kind": item.kind,
                    "required": item.required,
                    "result": item.result.value,
                    "detail": item.detail,
                }
                for item in obligations
            ],
            "verdict": _verdict_payload(verdict),
        },
    )
    connection = connect(data_dir)
    try:
        with connection:
            connection.execute(
                "UPDATE runs SET phase = 'finished' WHERE id = ? AND job_id = ?",
                (run_id, job_id),
            )
    finally:
        connection.close()
    return verdict


def evaluate_run(
    job_id: str,
    *,
    route_a: Any,
    route_b: Any,
    data_dir: str | Path,
) -> Any:
    from app.domain.acceptance import decide_run_outcome

    verdict = decide_run_outcome(route_a=route_a, route_b=route_b)
    _write_json(
        Path(data_dir) / "jobs" / job_id / "run-verdict.json",
        {
            "job_id": job_id,
            "route_a": _verdict_payload(route_a),
            "route_b": _verdict_payload(route_b),
            "verdict": _verdict_payload(verdict),
        },
    )
    connection = connect(data_dir)
    try:
        with connection:
            connection.execute("UPDATE jobs SET phase = 'finished' WHERE id = ?", (job_id,))
    finally:
        connection.close()
    return verdict


__all__ = ["GATES", "build_obligations", "evaluate_attempt", "evaluate_run"]
