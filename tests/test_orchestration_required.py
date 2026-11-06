from __future__ import annotations

from app.services.orchestration import build_obligations


def test_v2_v4_cannot_be_made_optional() -> None:
    results = {f"V{i}": "not_run" for i in range(6)}
    obligations = build_obligations(
        results,
        required={"V0": False, "V2": False, "V4": False},
    )
    by_kind = {item.kind: item for item in obligations}
    assert by_kind["identity"].required is False
    assert by_kind["interface"].required is True
    assert by_kind["symbolic"].required is True


def test_v2_v4_remain_required_even_when_results_pass() -> None:
    results = {"V0": "passed", "V1": "passed", "V2": "passed", "V3": "passed", "V4": "passed", "V5": "passed"}
    obligations = build_obligations(results, required={"V2": False, "V4": False})
    by_kind = {item.kind: item for item in obligations}
    assert by_kind["interface"].required is True
    assert by_kind["symbolic"].required is True


def test_evaluate_attempt_cannot_disable_v2_v4(tmp_path) -> None:
    from app.domain.outcomes import Outcome
    from app.services import jobs, orchestration

    data_dir = tmp_path / "var"
    job = jobs.create_job(
        original_bytes=b"\x7fELF evaluate-required",
        filename="required.elf",
        defect_description="required gate test",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="test",
        data_dir=data_dir,
        input_sha256=job.original_sha256,
    )
    run = jobs.start_run(
        job.id,
        approval=approval,
        idempotency_key="required-gates",
        data_dir=data_dir,
    )
    attempt = next(
        item for item in jobs.list_attempts(run.id, data_dir=data_dir)
        if item.route == "route_b"
    )
    verdict = orchestration.evaluate_attempt(
        job.id,
        run.id,
        attempt_id=attempt.id,
        results={"V0": "passed", "V1": "passed", "V2": "not_run",
                 "V3": "passed", "V4": "not_run", "V5": "passed"},
        data_dir=data_dir,
        candidate_sha256=job.original_sha256,
        required={"V2": False, "V4": False},
    )
    assert verdict.outcome is Outcome.INCONCLUSIVE
    assert verdict.failing_obligation == "interface"
