from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_phase8d_discovery_registry as registry  # noqa: E402


def test_registry_truthfully_separates_integrated_standalone_not_run():
    payload = registry.build_registry()
    summary = payload["summary"]
    assert payload["mechanism_count"] == 7
    assert summary["effective_run_count"] == 6
    assert summary["integrated_run_count"] == 3
    assert summary["standalone_run_count"] == 3
    assert summary["not_run_count"] == 1
    by_name = {r["mechanism"]: r for r in payload["records"]}
    assert by_name["sample_based"]["phase8d_status"] == "not_run"
    assert by_name["mutation"]["phase8d_status"] == "run_standalone"
    assert by_name["metamorphic"]["phase8d_status"] == "run_standalone"
    assert by_name["knowledge_source_scan"]["phase8d_status"] == "run_standalone"
    assert all(r["support_claimed"] is False for r in payload["records"])


def test_registry_check_and_evidence_digests():
    ok, problems = registry.check()
    assert ok is True, problems


def test_registry_does_not_rewrite_historical_gap_artifact():
    payload = registry.build_registry()
    assert payload["historical_registry"] == "artifacts/gap-registry-2026-11-16/gaps.json"
    path = ROOT / payload["historical_registry"]
    assert path.is_file()
