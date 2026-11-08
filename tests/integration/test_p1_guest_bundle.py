"""P1 real guest bundle: host ingest must preserve measured gates."""

from __future__ import annotations

import json
from pathlib import Path

from app.services import jobs
from tools.route_bundle_ingest import ingest

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "delivery/p1-real-window-2026-11-07/bundle/a1.routeb"
PACKAGE = ROOT / "delivery/p1-real-window-2026-11-07/package"


def test_real_p1_bundle_ingests_measured_gates(tmp_path: Path) -> None:
    contract = json.loads((PACKAGE / "contract.json").read_text(encoding="utf-8"))
    data_dir = tmp_path / "var"
    job = jobs.create_job(
        original_bytes=(BUNDLE / "original.elf").read_bytes(),
        filename="p1-real-elf",
        defect_description="P1 real guest window",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="p1-test",
        data_dir=data_dir,
        contract_body=contract,
        input_sha256=job.original_sha256,
    )
    run = jobs.start_run(job.id, approval=approval, idempotency_key="p1-window", data_dir=data_dir)
    attempt = next(
        item for item in jobs.list_attempts(run.id, data_dir=data_dir) if item.route == "route_b"
    )

    result = ingest(
        data_dir=data_dir,
        job_id=job.id,
        run_id=run.id,
        attempt_id=attempt.id,
        route="route_b",
        bundle=BUNDLE,
        trigger=True,
    )
    assert result["imported"]["changed"] is True
    assert set(result["evidence"]) == {"V0", "V1", "V2", "V3", "V4", "V5"}

    final = jobs.get_attempt(attempt.id, data_dir=data_dir)
    assert final is not None
    assert final.phase == "finished"
    assert final.outcome == "success_within_scope"
    assert final.reason is None
    assert final.failing_obligation is None

    payload = json.loads(
        (data_dir / "jobs" / job.id / "runs" / run.id / "attempts" / f"{attempt.id}.json").read_text()
    )
    assert payload["results"] == {
        "V0": "passed",
        "V1": "passed",
        "V2": "passed",
        "V3": "passed",
        "V4": "passed",
        "V5": "passed",
    }
