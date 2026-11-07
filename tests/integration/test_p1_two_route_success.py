"""P1 two-route success from real guest Route A and Route B bundles."""

from __future__ import annotations

import json
from pathlib import Path

from app.services import jobs, worker
from tools.route_bundle_ingest import ingest

ROOT = Path(__file__).resolve().parents[2]
ROUTE_A = ROOT / "delivery/p1-routea-real-v4-2026-11-07/out"
ROUTE_B = ROOT / "delivery/p1-real-window-2026-11-07/bundle/a1.routeb"
CONTRACT = ROOT / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput/contract.json"


def test_p1_two_route_success(tmp_path: Path) -> None:
    data = tmp_path / "var"
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    job = jobs.create_job(
        original_bytes=(ROUTE_B / "original.elf").read_bytes(),
        filename="p1-two-route.elf",
        defect_description="P1 two-route success",
        data_dir=data,
    )
    approval = jobs.approve_contract(
        job.id,
        contract_revision=1,
        reviewer_label="p1",
        data_dir=data,
        contract_body=contract,
        input_sha256=job.original_sha256,
    )
    run = jobs.start_run(job.id, approval=approval, idempotency_key="p1-success", data_dir=data)
    attempts = {item.route: item for item in jobs.list_attempts(run.id, data_dir=data)}

    for route, bundle in (("route_a", ROUTE_A), ("route_b", ROUTE_B)):
        ingest(
            data_dir=data,
            job_id=job.id,
            run_id=run.id,
            attempt_id=attempts[route].id,
            route=route,
            bundle=bundle,
            trigger=False,
        )

    worker.run_once(data_dir=data)
    for route in ("route_a", "route_b"):
        final = jobs.get_attempt(attempts[route].id, data_dir=data)
        assert final is not None
        assert final.outcome == "success_within_scope", (route, final)
        assert final.failing_obligation is None
