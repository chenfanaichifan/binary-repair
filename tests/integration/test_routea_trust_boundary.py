"""Integration tests for the Route A host trust boundary (P0).

Production path under test: worker -> ``BINARYREPAIR_ATTEMPT_CMD`` ->
``app.services.attempt_driver`` -> ``attempt_writer --routea-bundle`` ->
host validator -> obligations -> acceptance engine.

Every negative test asserts the individual gate rows and the Route A attempt
result, not merely "the run is not a success".
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.db.connection import connect
from app.services import attempt_driver, jobs, worker
from tests.routea_fixtures import (
    CONTRACT,
    ORIGINAL_ELF,
    build_route_a_bundle,
    build_route_b_bundle,
    change_entry,
)

KINDS = ("identity", "structure", "interface", "behaviour", "symbolic", "reproducibility")


def _setup(tmp_path: Path):
    data = tmp_path / "var"
    job = jobs.create_job(
        original_bytes=ORIGINAL_ELF.read_bytes(),
        filename="p0-trust-boundary.elf",
        defect_description="P0 Route A trust boundary",
        data_dir=data,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="p0",
        data_dir=data,
        contract_body=CONTRACT,
        input_sha256=job.original_sha256,
    )
    run = jobs.start_run(
        job.id, approval=approval, idempotency_key="p0-trust", data_dir=data
    )
    attempts = {item.route: item for item in jobs.list_attempts(run.id, data_dir=data)}
    return data, job, run, attempts


def _set_driver(monkeypatch, root: Path) -> None:
    monkeypatch.setenv("BINARYREPAIR_ATTEMPT_CMD", f'"{sys.executable}" -m app.services.attempt_driver')
    monkeypatch.setenv("PYTHONPATH", str(root))


def _result_bundle(data: Path, job_id: str, run_id: str, attempt_id: str) -> Path:
    return data / "jobs" / job_id / "runs" / run_id / "attempts" / f"{attempt_id}.json"


def _run_row(data: Path, run_id: str) -> dict:
    connection = connect(data)
    try:
        row = connection.execute(
            "SELECT outcome, reason, failing_obligation FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    finally:
        connection.close()
    return dict(row) if row is not None else {}


def _attempt_row(data: Path, attempt_id: str) -> dict:
    connection = connect(data)
    try:
        row = connection.execute(
            "SELECT candidate_sha256, outcome, reason, failing_obligation, detail "
            "FROM attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()
    finally:
        connection.close()
    return dict(row) if row is not None else {}


def _required_gates(results: dict[str, str]) -> dict[str, str]:
    return {kind: result for kind, result in results.items() if kind in KINDS}


def _obligations(data: Path, attempt_id: str) -> dict[str, str]:
    return {
        row["kind"]: row["result"]
        for row in jobs.list_obligations(attempt_id, data_dir=data)
    }


def _details(data: Path, attempt_id: str) -> dict[str, str]:
    return {
        row["kind"]: row["detail"]
        for row in jobs.list_obligations(attempt_id, data_dir=data)
    }


def test_legit_route_a_and_legit_route_b_both_pass(tmp_path: Path, monkeypatch) -> None:
    data, job, run, attempts = _setup(tmp_path)
    build_route_a_bundle(
        attempt_driver.routea_bundle_dir(data, job.id, run.id, attempts["route_a"].id)
    )
    build_route_b_bundle(
        attempt_driver.routeb_bundle_dir(data, job.id, run.id, attempts["route_b"].id)
    )
    _set_driver(monkeypatch, tmp_path)

    worker.run_once(data_dir=data)

    route_a = jobs.get_attempt(attempts["route_a"].id, data_dir=data)
    route_b = jobs.get_attempt(attempts["route_b"].id, data_dir=data)
    assert route_a is not None and route_a.outcome == "success_within_scope", route_a
    assert route_b is not None and route_b.outcome == "success_within_scope", route_b
    assert _required_gates(_obligations(data, attempts["route_a"].id)) == {
        kind: "passed" for kind in KINDS
    }
    assert _required_gates(_obligations(data, attempts["route_b"].id)) == {
        kind: "passed" for kind in KINDS
    }
    run_after = jobs.get_run(run.id, data_dir=data)
    assert run_after is not None and run_after.phase == "finished"
    assert _run_row(data, run.id)["outcome"] == "success_within_scope"


def test_forged_route_a_is_rejected_while_legit_route_b_passes(
    tmp_path: Path, monkeypatch
) -> None:
    data, job, run, attempts = _setup(tmp_path)
    legit_route_b = build_route_b_bundle(
        attempt_driver.routeb_bundle_dir(data, job.id, run.id, attempts["route_b"].id)
    )
    forged = attempt_driver.routea_bundle_dir(data, job.id, run.id, attempts["route_a"].id)
    (forged / "route_a").mkdir(parents=True)
    candidate = change_entry(ORIGINAL_ELF.read_bytes())
    (forged / "route_a" / "candidate.elf").write_bytes(candidate)
    # The forged bundle claims a perfect result; the host must ignore the claim.
    (forged / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "route": "route_a",
                "candidate_sha256": __import__("hashlib").sha256(candidate).hexdigest(),
                "identity": {"candidate_sha256": __import__("hashlib").sha256(candidate).hexdigest()},
                "gates": {gate: {"status": "passed"} for gate in ("V0", "V1", "V2", "V3", "V4", "V5")},
            }
        ),
        encoding="utf-8",
    )
    (forged / "evidence" / "v2").mkdir(parents=True)
    (forged / "evidence" / "v2" / "interface.json").write_text(
        json.dumps({"status": "pass", "details": {"claim": "producer says pass"}}),
        encoding="utf-8",
    )
    _set_driver(monkeypatch, tmp_path)

    worker.run_once(data_dir=data)

    route_a = jobs.get_attempt(attempts["route_a"].id, data_dir=data)
    assert route_a is not None
    assert route_a.outcome == "rejected"
    assert route_a.reason == "regression_failed"
    assert route_a.failing_obligation == "interface"
    assert _obligations(data, attempts["route_a"].id) == {
        "identity": "not_run",
        "structure": "not_run",
        "interface": "failed",
        "behaviour": "not_run",
        "symbolic": "not_run",
        "reproducibility": "not_run",
    }
    route_a_details = _details(data, attempts["route_a"].id)
    assert route_a_details["identity"].startswith("V0 identity not verified:") or route_a_details["identity"].startswith("missing:")
    assert route_a_details["structure"].startswith("missing:")
    assert route_a_details["interface"].startswith("check_failed:")
    assert route_a_details["behaviour"].startswith("missing:")
    assert route_a_details["symbolic"].startswith("missing:")
    assert route_a_details["reproducibility"].startswith("missing:")

    route_b = jobs.get_attempt(attempts["route_b"].id, data_dir=data)
    assert route_b is not None and route_b.outcome == "success_within_scope"
    assert _attempt_row(data, attempts["route_b"].id)["candidate_sha256"] == legit_route_b["candidate_sha256"]
    run_after = jobs.get_run(run.id, data_dir=data)
    assert run_after is not None and run_after.phase == "finished"
    assert _run_row(data, run.id)["outcome"] == "rejected"


def test_missing_route_a_bundle_is_evidence_gap_not_tool_failure(
    tmp_path: Path, monkeypatch
) -> None:
    data, job, run, attempts = _setup(tmp_path)
    build_route_b_bundle(
        attempt_driver.routeb_bundle_dir(data, job.id, run.id, attempts["route_b"].id)
    )
    generic = tmp_path / "generic.json"
    generic.write_text(
        json.dumps(
            {
                "route": "route_a",
                "candidate_sha256": "a" * 64,
                "results": {f"V{i}": "passed" for i in range(6)},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("BINARYREPAIR_ATTEMPT_INPUT", str(generic))
    _set_driver(monkeypatch, tmp_path)

    worker.run_once(data_dir=data)

    route_a = jobs.get_attempt(attempts["route_a"].id, data_dir=data)
    assert route_a is not None
    assert route_a.outcome == "inconclusive"
    assert route_a.reason == "required_check_not_run"
    assert route_a.failing_obligation == "identity"
    assert _obligations(data, attempts["route_a"].id) == {kind: "not_run" for kind in KINDS}
    for detail in _details(data, attempts["route_a"].id).values():
        assert detail.startswith("missing:"), detail
    assert not _result_bundle(data, job.id, run.id, attempts["route_a"].id).exists()
    route_b = jobs.get_attempt(attempts["route_b"].id, data_dir=data)
    assert route_b is not None and route_b.outcome == "success_within_scope"
    run_after = jobs.get_run(run.id, data_dir=data)
    assert run_after is not None and run_after.phase == "finished"
    assert _run_row(data, run.id)["outcome"] == "inconclusive"


def test_route_a_bundle_without_candidate_is_evidence_gap(
    tmp_path: Path, monkeypatch
) -> None:
    data, job, run, attempts = _setup(tmp_path)
    bundle = attempt_driver.routea_bundle_dir(data, job.id, run.id, attempts["route_a"].id)
    bundle.mkdir(parents=True)
    _set_driver(monkeypatch, tmp_path)

    worker.run_once(data_dir=data)

    route_a = jobs.get_attempt(attempts["route_a"].id, data_dir=data)
    assert route_a is not None
    assert route_a.outcome == "inconclusive"
    assert route_a.reason == "required_check_not_run"
    details = _details(data, attempts["route_a"].id)
    assert all(detail.startswith("missing:") for detail in details.values())
    assert "candidate.elf" in details["identity"]


def test_route_a_cannot_pass_with_invalid_v4_and_v5_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    data, job, run, attempts = _setup(tmp_path)
    bundle = attempt_driver.routea_bundle_dir(data, job.id, run.id, attempts["route_a"].id)
    build_route_a_bundle(bundle, v4_verified_by=None, v5_independent_replay=False)
    build_route_b_bundle(
        attempt_driver.routeb_bundle_dir(data, job.id, run.id, attempts["route_b"].id)
    )
    _set_driver(monkeypatch, tmp_path)

    worker.run_once(data_dir=data)

    assert _obligations(data, attempts["route_a"].id) == {
        "identity": "passed",
        "structure": "passed",
        "interface": "passed",
        "behaviour": "passed",
        "symbolic": "not_run",
        "reproducibility": "not_run",
    }
    details = _details(data, attempts["route_a"].id)
    assert details["symbolic"].startswith(("invalid:", "V4 not_run:"))
    assert details["reproducibility"].startswith(("invalid:", "V5 not verified:", "V5 not_run:"))
    route_a = jobs.get_attempt(attempts["route_a"].id, data_dir=data)
    assert route_a is not None
    assert route_a.outcome == "inconclusive"
    assert route_a.reason == "required_check_not_run"
    assert route_a.failing_obligation == "symbolic"
