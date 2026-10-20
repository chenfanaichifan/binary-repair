"""Contract tests for the V0-V5 -> Verdict orchestration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import jobs, orchestration


def _started(tmp_path: Path):
    data_dir = tmp_path / "var"
    record = jobs.create_job(
        original_bytes=b"\x7fELF orchestration bytes",
        filename="sample.elf",
        defect_description="stack buffer overflow in copy_input",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        record.id,
        input_sha256=record.original_sha256,
        contract_revision=1,
        manifest_sha256="1" * 64,
        scope_sha256="2" * 64,
        reviewer_label="test",
        data_dir=data_dir,
    )
    run = jobs.start_run(
        record.id,
        approval=approval,
        idempotency_key="run-1",
        data_dir=data_dir,
    )
    return data_dir, record, run


def test_missing_gates_become_inconclusive_not_success(tmp_path: Path) -> None:
    data_dir, record, run = _started(tmp_path)
    verdict = orchestration.evaluate_attempt(
        record.id,
        run.id,
        results={"V0": "passed"},
        data_dir=data_dir,
        candidate_sha256=record.original_sha256,
    )
    assert verdict.outcome.value == "inconclusive"
    assert verdict.reason.value == "required_check_not_run"

    path = data_dir / "jobs" / record.id / "runs" / run.id / "verdict.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["obligations"]) == 6
    assert payload["verdict"]["outcome"] == "inconclusive"
    assert payload["verdict"]["failing_obligation"] == "structure"


def test_all_v0_v5_passed_is_success(tmp_path: Path) -> None:
    data_dir, record, run = _started(tmp_path)
    results = {gate: "passed" for gate, _, _ in orchestration.GATES}
    verdict = orchestration.evaluate_attempt(
        record.id,
        run.id,
        results=results,
        data_dir=data_dir,
        candidate_sha256=record.original_sha256,
    )
    assert verdict.outcome.value == "success_within_scope"


def test_candidate_hash_mismatch_is_inconclusive(tmp_path: Path) -> None:
    data_dir, record, run = _started(tmp_path)
    results = {gate: "passed" for gate, _, _ in orchestration.GATES}
    verdict = orchestration.evaluate_attempt(
        record.id,
        run.id,
        results=results,
        data_dir=data_dir,
        candidate_sha256="9" * 64,
    )
    assert verdict.outcome.value == "inconclusive"
    assert verdict.reason.value == "hash_mismatch"


def test_run_requires_both_routes(tmp_path: Path) -> None:
    data_dir, record, run_a = _started(tmp_path)
    results = {gate: "passed" for gate, _, _ in orchestration.GATES}
    route_a = orchestration.evaluate_attempt(
        record.id,
        run_a.id,
        results=results,
        data_dir=data_dir,
        candidate_sha256=record.original_sha256,
    )

    approval = jobs.approve_contract(
        record.id,
        input_sha256=record.original_sha256,
        contract_revision=1,
        manifest_sha256="1" * 64,
        scope_sha256="2" * 64,
        reviewer_label="test",
        data_dir=data_dir,
    )
    run_b = jobs.start_run(
        record.id,
        approval=approval,
        idempotency_key="run-2",
        data_dir=data_dir,
    )
    route_b = orchestration.evaluate_attempt(
        record.id,
        run_b.id,
        results={**results, "V3": "failed"},
        data_dir=data_dir,
        candidate_sha256=record.original_sha256,
    )
    assert route_b.outcome.value == "rejected"

    run_verdict = orchestration.evaluate_run(
        record.id,
        route_a=route_a,
        route_b=route_b,
        data_dir=data_dir,
    )
    assert run_verdict.outcome.value == "rejected"
    assert jobs.get_job(record.id, data_dir=data_dir).phase == "finished"

    path = data_dir / "jobs" / record.id / "run-verdict.json"
    assert path.exists()


def test_unknown_run_is_rejected(tmp_path: Path) -> None:
    data_dir, record, _ = _started(tmp_path)
    with pytest.raises(ValueError):
        orchestration.evaluate_attempt(
            record.id,
            "missing-run",
            results={},
            data_dir=data_dir,
            candidate_sha256=record.original_sha256,
        )
