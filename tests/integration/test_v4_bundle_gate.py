"""A V4 'passed' claim without typed evidence is NOT VERIFIED."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from app.services import jobs
from tools.route_bundle_ingest import ingest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput"
DELIVERY = ROOT / "artifacts/cwe416-124-candidate-2026-11-05"
CANDIDATE_SHA = "46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0"


def test_v4_passed_without_typed_evidence_becomes_not_run(tmp_path: Path) -> None:
    contract = json.loads((FIXTURE / "contract.json").read_text(encoding="utf-8"))
    data_dir = tmp_path / "var"
    record = jobs.create_job(
        original_bytes=(FIXTURE / "original.elf").read_bytes(),
        filename="CWE416_v4_gate.elf",
        defect_description="V4 typed evidence gate",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        record.id,
        contract_revision=1,
        reviewer_label="test",
        data_dir=data_dir,
        contract_body=contract,
        input_sha256=record.original_sha256,
    )
    run = jobs.start_run(
        record.id,
        approval=approval,
        idempotency_key="cwe416-v4-gate",
        data_dir=data_dir,
    )
    attempt = next(
        item for item in jobs.list_attempts(run.id, data_dir=data_dir)
        if item.route == "route_b"
    )

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in (
        "original.elf",
        "candidate.elf",
        "audit.json",
        "manifest-repaired.json",
        "reproducibility.json",
        "v2-interface.json",
        "v4-symbolic.json",
    ):
        shutil.copyfile(DELIVERY / name, bundle / name)
    (bundle / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "route": "route_b",
                "candidate_sha256": CANDIDATE_SHA,
                "gates": {
                    "V0": {"status": "passed", "artifacts": ["original.elf", "candidate.elf"]},
                    "V1": {"status": "passed", "artifacts": ["audit.json"]},
                    "V2": {"status": "passed", "artifacts": ["v2-interface.json"]},
                    "V3": {"status": "passed", "artifacts": ["manifest-repaired.json"]},
                    "V4": {"status": "passed", "artifacts": ["v4-symbolic.json"]},
                    "V5": {"status": "passed", "artifacts": ["reproducibility.json"]},
                },
            }
        ),
        encoding="utf-8",
    )

    ingest(
        data_dir=data_dir,
        job_id=record.id,
        run_id=run.id,
        attempt_id=attempt.id,
        route="route_b",
        bundle=bundle,
        trigger=True,
    )

    payload = json.loads(
        (data_dir / "jobs" / record.id / "runs" / run.id / "attempts" / f"{attempt.id}.json").read_text()
    )
    assert payload["results"]["V4"] == "not_run"
    assert "V4" not in payload.get("evidence", {})
    assert "not_run" in payload["details"]["V4"]

    final = jobs.get_attempt(attempt.id, data_dir=data_dir)
    assert final is not None
    assert final.outcome == "inconclusive"
    assert final.reason == "required_check_not_run"
    by_kind = {
        row["kind"]: row["result"]
        for row in jobs.list_obligations(attempt.id, data_dir=data_dir)
    }
    assert by_kind["symbolic"] == "not_run"


def test_persist_v4_passed_with_invalid_artifact_is_not_run(tmp_path: Path) -> None:
    import uuid

    from app.db.connection import connect
    from app.services import obligations

    data_dir = tmp_path / "var"
    job = jobs.create_job(
        original_bytes=b"\x7fELF persist-v4",
        filename="persist-v4.elf",
        defect_description="persist V4 gate",
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
        idempotency_key="persist-v4",
        data_dir=data_dir,
    )
    attempt = next(
        item for item in jobs.list_attempts(run.id, data_dir=data_dir)
        if item.route == "route_b"
    )

    relative = f"jobs/{job.id}/evidence/{attempt.id}/v4.json"
    path = data_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"gate": "V4", "state": "not_run"}), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    artifact_id = uuid.uuid4().hex
    connection = connect(data_dir)
    try:
        with connection:
            connection.execute(
                "INSERT INTO artifacts "
                "(id, job_id, attempt_id, relative_path, sha256, size_bytes, media_type, role, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'application/json', 'v4_evidence', ?)",
                (artifact_id, job.id, attempt.id, relative, digest, path.stat().st_size,
                 "2026-11-06T00:00:00+00:00"),
            )
    finally:
        connection.close()

    obligations.persist_obligations(
        data_dir=data_dir,
        job_id=job.id,
        attempt_id=attempt.id,
        results={"V4": "passed"},
        evidence={"V4": artifact_id},
        candidate_sha256=job.original_sha256,
    )
    rows = jobs.list_obligations(attempt.id, data_dir=data_dir)
    by_kind = {row["kind"]: row for row in rows}
    assert by_kind["symbolic"]["result"] == "not_run"
    assert "not_run" in by_kind["symbolic"]["detail"]


def _typed_v4(candidate_sha256: str, original_sha256: str) -> dict:
    return {
        "schema_version": 1,
        "gate": "V4",
        "kind": "symbolic",
        "scope": "model",
        "state": "passed",
        "ran": True,
        "candidate_sha256": candidate_sha256,
        "original_sha256": original_sha256,
        "tool_versions": {"angr": "10.0.4.post1", "z3": "5.1.0"},
        "preconditions": ["bound 64", "no-input path"],
        "property_kind": "pointer-flow",
        "memory_predicates": ["freed block is not read"],
        "forbidden_ranges": [{"start": 0, "end": 64, "reason": "freed object"}],
        "hooks": ["after free", "before read"],
        "exploration_accounting": {
            "initial": 8, "deadended": 7, "errored": 0, "unconstrained": 0,
            "deferred": 0, "active": 0, "pruned": 1,
            "complete": True, "unexplored": [],
        },
        "solver_accounting": {
            "engine": "z3", "version": "5.1.0", "queries": 8,
            "sat": 1, "unsat": 7, "unknown": 0, "eval": 0,
            "timeouts": 0, "steps": 120, "max_steps": 256, "complete": True,
        },
        "calibration": {
            "suite": "original-negative-control", "cases": 2,
            "passed": 1, "failed": 1, "known_good": True, "known_bad": True,
            "known_bad_rejected": True, "complete": True,
        },
        "replay": {
            "command": "v4 replay", "runs": 2, "identical": True,
            "evidence_sha256": "d" * 64,
            "verified_by": "m4",
        },
        "claimed_scope": "model",
        "not_claimed": ["binary-level proof"],
    }


def test_typed_v4_symbolic_json_lands_in_bundle_and_persist(tmp_path: Path) -> None:
    contract = json.loads((FIXTURE / "contract.json").read_text(encoding="utf-8"))
    data_dir = tmp_path / "var"
    record = jobs.create_job(
        original_bytes=(FIXTURE / "original.elf").read_bytes(),
        filename="CWE416_v4_typed.elf",
        defect_description="typed V4 bundle path",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        record.id,
        contract_revision=1,
        reviewer_label="test",
        data_dir=data_dir,
        contract_body=contract,
        input_sha256=record.original_sha256,
    )
    run = jobs.start_run(
        record.id,
        approval=approval,
        idempotency_key="cwe416-v4-typed",
        data_dir=data_dir,
    )
    attempt = next(
        item for item in jobs.list_attempts(run.id, data_dir=data_dir)
        if item.route == "route_b"
    )

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    for name in ("original.elf", "candidate.elf", "audit.json"):
        shutil.copyfile(DELIVERY / name, bundle / name)
    candidate_sha = hashlib.sha256((DELIVERY / "candidate.elf").read_bytes()).hexdigest()
    original_sha = hashlib.sha256((FIXTURE / "original.elf").read_bytes()).hexdigest()
    (bundle / "v4-symbolic.json").write_text(
        json.dumps(_typed_v4(candidate_sha, original_sha)), encoding="utf-8"
    )
    (bundle / "bundle.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "route": "route_b",
                "candidate_sha256": candidate_sha,
                "gates": {
                    "V0": {"status": "passed", "artifacts": ["original.elf", "candidate.elf"]},
                    "V1": {"status": "passed", "artifacts": ["audit.json"]},
                    "V2": {"status": "not_run", "artifacts": []},
                    "V3": {"status": "not_run", "artifacts": []},
                    "V4": {"status": "passed", "artifacts": ["v4-symbolic.json"]},
                    "V5": {"status": "not_run", "artifacts": []},
                },
            }
        ),
        encoding="utf-8",
    )

    ingest(
        data_dir=data_dir,
        job_id=record.id,
        run_id=run.id,
        attempt_id=attempt.id,
        route="route_b",
        bundle=bundle,
        trigger=True,
    )
    payload = json.loads(
        (data_dir / "jobs" / record.id / "runs" / run.id / "attempts" / f"{attempt.id}.json").read_text()
    )
    assert payload["results"]["V4"] == "passed"
    assert "V4" in payload["evidence"]
    by_kind = {
        row["kind"]: row["result"]
        for row in jobs.list_obligations(attempt.id, data_dir=data_dir)
    }
    assert by_kind["symbolic"] == "passed"
    final = jobs.get_attempt(attempt.id, data_dir=data_dir)
    assert final is not None
    assert final.outcome == "inconclusive"
    assert final.failing_obligation == "behaviour"
