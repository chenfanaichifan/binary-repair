"""Orchestration: turn V0-V5 evidence into one persisted Verdict.

Who calls what, and when:

1. After ``create_job`` / ``approve_contract`` / ``start_run``, the run executor
   performs the V0-V5 checks and persists their raw results.
2. It calls :func:`evaluate_attempt` exactly once per route. That function builds
   the ``Obligation`` list (missing gates become ``not_run``, never dropped),
   calls ``decide_attempt_outcome`` with the final candidate hash, the approved
   hash, and the reviewed scope hash, then persists the ``Verdict``.
3. After both routes finish, the controller calls :func:`evaluate_run`, which
   uses ``decide_run_outcome``. One successful route is not a successful run.

The acceptance engine is the only decision point. This module only assembles
inputs and persists the result; it does not contain a second success rule.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.db.connection import connect
from app.domain.acceptance import Obligation, Verdict, decide_attempt_outcome, decide_run_outcome
from app.domain.outcomes import CheckResult, ReasonCode

# Gate id -> shared kind name (V0-V5), fixed by the §4.1 confirmation.
GATES: tuple[tuple[str, str, bool], ...] = (
    ("V0", "identity", True),
    ("V1", "structure", True),
    ("V2", "interface", True),
    ("V3", "behaviour", True),
    ("V4", "symbolic", True),
    ("V5", "reproducibility", True),
)


def _gate_result(value: str | CheckResult) -> CheckResult:
    if isinstance(value, CheckResult):
        return value
    try:
        return CheckResult(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown check result: {value!r}") from exc


def build_obligations(
    results: Mapping[str, str | CheckResult],
    *,
    required: Mapping[str, bool] | None = None,
) -> list[Obligation]:
    """Build V0-V5 obligations; a missing gate is ``not_run``, never dropped."""

    required = required or {}
    obligations: list[Obligation] = []
    for gate, kind, default_required in GATES:
        result = _gate_result(results.get(gate, CheckResult.NOT_RUN))
        obligations.append(
            Obligation(
                kind=kind,
                required=required.get(gate, default_required),
                result=result,
                detail=f"{gate} {kind}: {result.value}",
            )
        )
    return obligations


def _verdict_payload(verdict: Verdict) -> dict[str, Any]:
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


def _run_context(job_id: str, run_id: str, data_dir: str | Path) -> tuple[Any, Any]:
    connection = connect(data_dir)
    try:
        run = connection.execute(
            "SELECT * FROM runs WHERE id = ? AND job_id = ?",
            (run_id, job_id),
        ).fetchone()
        if run is None:
            raise ValueError(f"unknown run id for job {job_id}: {run_id}")
        contract = connection.execute(
            "SELECT * FROM contracts WHERE id = ? AND job_id = ?",
            (run["contract_id"], job_id),
        ).fetchone()
        if contract is None:
            raise ValueError("run has no contract / approval")
    finally:
        connection.close()
    return run, contract


def evaluate_attempt(
    job_id: str,
    run_id: str,
    *,
    results: Mapping[str, str | CheckResult],
    data_dir: str | Path,
    candidate_sha256: str,
    required: Mapping[str, bool] | None = None,
    cancelled: bool = False,
    error_reason: ReasonCode | None = None,
    error_detail: str = "",
    unsupported_reason: ReasonCode | None = None,
    unsupported_detail: str = "",
) -> Verdict:
    """Decide one route's attempt and persist the verdict.

    Call this once, after the V0-V5 results for the attempt are persisted.
    """

    run, contract = _run_context(job_id, run_id, data_dir)
    obligations = build_obligations(results, required=required)
    verdict = decide_attempt_outcome(
        obligations=obligations,
        candidate_sha256=candidate_sha256,
        expected_sha256=contract["input_sha256"],
        reviewed_scope_sha256=contract["scope_sha256"],
        cancelled=cancelled,
        error_reason=error_reason,
        error_detail=error_detail,
        unsupported_reason=unsupported_reason,
        unsupported_detail=unsupported_detail,
    )

    payload = {
        "job_id": job_id,
        "run_id": run_id,
        "candidate_sha256": candidate_sha256,
        "expected_sha256": contract["input_sha256"],
        "reviewed_scope_sha256": contract["scope_sha256"],
        "obligations": [
            {
                "kind": obligation.kind,
                "required": obligation.required,
                "result": obligation.result.value,
                "detail": obligation.detail,
            }
            for obligation in obligations
        ],
        "verdict": _verdict_payload(verdict),
    }
    _write_json(
        Path(data_dir) / "jobs" / job_id / "runs" / run_id / "verdict.json",
        payload,
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
    route_a: Verdict,
    route_b: Verdict,
    data_dir: str | Path,
) -> Verdict:
    """Decide the whole run (both routes) and persist the run verdict."""

    verdict = decide_run_outcome(route_a=route_a, route_b=route_b)
    payload = {
        "job_id": job_id,
        "route_a": _verdict_payload(route_a),
        "route_b": _verdict_payload(route_b),
        "verdict": _verdict_payload(verdict),
    }
    _write_json(Path(data_dir) / "jobs" / job_id / "run-verdict.json", payload)

    connection = connect(data_dir)
    try:
        with connection:
            connection.execute(
                "UPDATE jobs SET phase = 'finished' WHERE id = ?",
                (job_id,),
            )
    finally:
        connection.close()
    return verdict


__all__ = ["GATES", "build_obligations", "evaluate_attempt", "evaluate_run"]
