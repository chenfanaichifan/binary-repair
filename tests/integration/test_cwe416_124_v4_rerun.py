"""124 rerun with M4's independent V4 marker.

The bundle now carries M4's marker (verified_by="m4"), so V4 is no longer
provisional. The attempt may finish with success_within_scope once all six
required obligations are present.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services import jobs
from tools.route_bundle_ingest import ingest

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "delivery/cwe416-124-v4-rerun-2026-11-06"
FIXTURE = ROOT / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput"


def test_cwe416_124_v4_evidence_is_provisional_without_m4_replay(tmp_path: Path) -> None:
    contract = json.loads((FIXTURE / "contract.json").read_text(encoding="utf-8"))
    data_dir = tmp_path / "var"
    job = jobs.create_job(
        original_bytes=(BUNDLE / "original.elf").read_bytes(),
        filename="CWE416_124_v4.elf",
        defect_description="124 V4 rerun",
        data_dir=data_dir,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="test",
        data_dir=data_dir,
        contract_body=contract,
        input_sha256=job.original_sha256,
    )
    run = jobs.start_run(
        job.id,
        approval=approval,
        idempotency_key="cwe416-124-v4",
        data_dir=data_dir,
    )
    attempt = next(
        item for item in jobs.list_attempts(run.id, data_dir=data_dir)
        if item.route == "route_b"
    )

    ingest(
        data_dir=data_dir,
        job_id=job.id,
        run_id=run.id,
        attempt_id=attempt.id,
        route="route_b",
        bundle=BUNDLE,
        trigger=True,
    )
    (BUNDLE / "_v2-interface-scored.json").unlink(missing_ok=True)
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
    assert payload["details"]["V2"] == "5/5 static interface checks passed"
    assert "V4" in payload["evidence"]

    final = jobs.get_attempt(attempt.id, data_dir=data_dir)
    assert final is not None
    assert final.outcome == "success_within_scope"
    assert final.reason is None
    assert final.failing_obligation is None
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
        "symbolic": "passed",
    }
    # Route A has no bundle, so the run itself is not finished/success yet.
    assert jobs.get_run(run.id, data_dir=data_dir).phase == "screening"
