"""Host route-B writer gate derivation for 124 and P1 bundles."""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.services import attempt_writer, jobs

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_124 = ROOT / "delivery/cwe416-124-v4-rerun-2026-11-06"
BUNDLE_P1 = ROOT / "delivery/p1-real-window-2026-11-07/bundle/a1.routeb"
CONTRACT = ROOT / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/contract.json"


def _run(tmp_path: Path, bundle: Path) -> dict:
    data = tmp_path / "var"
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    job = jobs.create_job(
        original_bytes=(bundle / "original.elf").read_bytes(),
        filename=bundle.parent.name + ".elf",
        defect_description="gate derivation",
        data_dir=data,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="test",
        data_dir=data,
        contract_body=contract,
        input_sha256=job.original_sha256,
    )
    run = jobs.start_run(job.id, approval=approval, idempotency_key=bundle.name, data_dir=data)
    attempt = next(a for a in jobs.list_attempts(run.id, data_dir=data) if a.route == "route_b")
    out = data / "result.json"
    os.environ.update(
        BINARYREPAIR_DATA_DIR=str(data),
        BINARYREPAIR_JOB_ID=job.id,
        BINARYREPAIR_RUN_ID=run.id,
        BINARYREPAIR_ATTEMPT_ID=attempt.id,
        BINARYREPAIR_ROUTE="route_b",
        BINARYREPAIR_RESULT_PATH=str(out),
    )
    rc = attempt_writer.main(["--routeb-bundle", str(bundle)])
    assert rc == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_124_bundle_derives_all_six_gates(tmp_path: Path) -> None:
    payload = _run(tmp_path, BUNDLE_124)
    assert payload["results"] == {
        "V0": "passed",
        "V1": "passed",
        "V2": "passed",
        "V3": "passed",
        "V4": "passed",
        "V5": "passed",
    }
    assert {"V1", "V2", "V3", "V4", "V5"} <= set(payload["evidence"])


def test_p1_bundle_keeps_v2_v4_v5_not_run(tmp_path: Path) -> None:
    payload = _run(tmp_path, BUNDLE_P1)
    assert payload["results"] == {
        "V0": "passed",
        "V1": "passed",
        "V2": "not_run",
        "V3": "passed",
        "V4": "not_run",
        "V5": "not_run",
    }
    assert set(payload["evidence"]) == {"V1", "V3"}
