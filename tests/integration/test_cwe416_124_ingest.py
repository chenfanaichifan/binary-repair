"""Ingest the 124 CWE416 candidate through the controller's normal rules.

V2 is scored 5/5 from the binary pair; V4 stays not_run. The attempt must be
inconclusive, never success.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from app.services import jobs
from tools.route_bundle_ingest import ingest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput"
DELIVERY = ROOT / "delivery/cwe416-124-candidate-2026-11-05"
ORIGINAL_SHA = "c9c2632e792c5acd0311cc3a5e4eb3fde538eb05d0de9c6601711e84b7b123c9"
CANDIDATE_SHA = "46d16e997bdfbb87fbd9c1d6f09443a7907b11b2b37118f5c773087a0d91fcd0"
CONTRACT_SHA = "c1684f15bb1c67cb9b3d6752e4023ca670a432ceb92342f6d10d040ee17b4f7c"


def test_cwe416_124_ingest_keeps_v4_not_run_after_v2_score(tmp_path: Path) -> None:
    original = (FIXTURE / "original.elf").read_bytes()
    candidate = (DELIVERY / "candidate.elf").read_bytes()
    assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA
    assert hashlib.sha256(candidate).hexdigest() == CANDIDATE_SHA

    contract = json.loads((FIXTURE / "contract.json").read_text(encoding="utf-8"))
    data_dir = tmp_path / "var"
    record = jobs.create_job(
        original_bytes=original,
        filename="CWE416_124_candidate.elf",
        defect_description="use after free, no input",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        record.id,
        contract_revision=1,
        reviewer_label="m1-ingest-test",
        data_dir=data_dir,
        contract_body=contract,
        input_sha256=record.original_sha256,
    )
    assert approval.scope_sha256 == CONTRACT_SHA
    run = jobs.start_run(
        record.id,
        approval=approval,
        idempotency_key="cwe416-124",
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
                    "V2": {"status": "not_run", "artifacts": ["v2-interface.json"]},
                    "V3": {"status": "passed", "artifacts": ["manifest-repaired.json"]},
                    "V4": {"status": "not_run", "artifacts": ["v4-symbolic.json"]},
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
    assert "V2" in payload["evidence"]
    assert payload["details"]["V2"] == "5/5 static interface checks passed"
    assert payload["results"] == {
        "V0": "passed",
        "V1": "passed",
        "V2": "passed",
        "V3": "passed",
        "V4": "not_run",
        "V5": "passed",
    }
    final = jobs.get_attempt(attempt.id, data_dir=data_dir)
    assert final is not None
    assert final.outcome == "inconclusive"
    assert final.reason == "required_check_not_run"
    assert final.failing_obligation == "symbolic"
    assert final.detail == "V4 symbolic: not_run"

    by_kind = {
        row["kind"]: row["result"]
        for row in jobs.list_obligations(attempt.id, data_dir=data_dir)
    }
    assert by_kind == {
        "behaviour": "passed",
        "identity": "passed",
        "interface": "passed",
        "reproducibility": "passed",
        "structure": "passed",
        "symbolic": "not_run",
    }
    run_after = jobs.get_run(run.id, data_dir=data_dir)
    assert run_after is not None
    assert run_after.phase != "finished"
