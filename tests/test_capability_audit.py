"""Tests for the capability-gap self-discovery audit (fast, deterministic)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.services import coverage_audit

ROOT = Path(__file__).resolve().parents[1]
STATIC_AUDIT = coverage_audit.build_audit(include_probes=False)


def test_static_audit_returns_structured_document() -> None:
    audit = STATIC_AUDIT
    assert audit["schema_version"] == coverage_audit.SCHEMA_VERSION
    assert audit["audit_date"] == coverage_audit.AUDIT_DATE
    assert audit["mode"] == "static"
    for key in ("environment", "bounds", "census", "coverage_rows", "probes", "gaps",
                "summary"):
        assert key in audit
    census = audit["census"]
    for key in ("matrix", "gates", "runtime_sources", "fixtures", "cases",
                "poc_manifests", "claims", "docs", "benchmarks", "modules",
                "capability"):
        assert key in census
    assert census["matrix"]["status"] in {"ok", "module_not_ready"}
    assert isinstance(census["gates"]["unified"]["status"], str)
    assert isinstance(census["gates"]["legacy"]["status"], str)
    assert isinstance(census["fixtures"], list)
    assert isinstance(audit["gaps"], list)
    assert audit["gaps"], "the audit must always report gap rows"


def test_gap_rows_use_the_declared_taxonomy() -> None:
    for gap in STATIC_AUDIT["gaps"]:
        assert gap["category"] in coverage_audit.GAP_CATEGORIES
        assert gap["status"] in coverage_audit.GAP_STATUSES
        assert gap["severity"] in coverage_audit.GAP_SEVERITIES
        assert isinstance(gap["gap_id"], str) and gap["gap_id"]
        assert isinstance(gap["symptom"], str) and gap["symptom"]
        assert isinstance(gap["evidence"], list) and gap["evidence"]
        assert isinstance(gap["next_step"], str) and gap["next_step"]
        assert isinstance(gap["detector"], str) and gap["detector"]


def test_gap_ids_are_unique_and_stably_ordered() -> None:
    gaps = STATIC_AUDIT["gaps"]
    ids = [gap["gap_id"] for gap in gaps]
    assert len(ids) == len(set(ids))
    ordered = sorted(
        gaps,
        key=lambda gap: (coverage_audit.CATEGORY_RANK[gap["category"]],
                         coverage_audit.SEVERITY_RANK[gap["severity"]],
                         gap["gap_id"]),
    )
    assert ids == [gap["gap_id"] for gap in ordered]


def test_known_concrete_gaps_are_reported() -> None:
    gaps = {gap["gap_id"]: gap for gap in STATIC_AUDIT["gaps"]}
    known = [gap_id for gap_id in coverage_audit.known_gap_ids() if gap_id in gaps]
    assert known, "at least one known concrete gap id must be reported"
    assert "EG-capacity-strategy" in gaps
    capacity = gaps["EG-capacity-strategy"]
    assert capacity["category"] in {"engine_gap", "matrix_claim_mismatch"}
    assert capacity["status"] in coverage_audit.GAP_STATUSES
    # Status is measured, not fixed: it must be open OR already closed by a
    # later integration, never silently absent.
    assert capacity["evidence"]


def test_static_audit_is_deterministic() -> None:
    again = coverage_audit.build_audit(include_probes=False)
    first = json.dumps(STATIC_AUDIT, indent=2, sort_keys=True)
    second = json.dumps(again, indent=2, sort_keys=True)
    assert first == second


def test_summary_matches_gap_rows() -> None:
    summary = STATIC_AUDIT["summary"]
    gaps = STATIC_AUDIT["gaps"]
    assert summary["gap_count"] == len(gaps)
    statuses = [gap["status"] for gap in gaps]
    for status in coverage_audit.GAP_STATUSES:
        assert summary["by_status"][status] == statuses.count(status)
    assert summary["open_gap_ids"] == sorted(
        gap["gap_id"] for gap in gaps if gap["status"] == "open"
    )


def test_render_gap_report_contains_required_sections() -> None:
    report = coverage_audit.render_gap_report(STATIC_AUDIT)
    assert report.startswith("# Capability-gap audit")
    assert "## Summary" in report
    assert "## Open gaps (actionable)" in report
    assert "## Self-reflection: what the audit found that prose missed" in report
    assert "## Method and bounds" in report
    assert "coverage-matrix.json" in report
    assert any(gap_id in report for gap_id in coverage_audit.known_gap_ids())


def test_write_artifacts_and_checksums(tmp_path: Path) -> None:
    written = coverage_audit.write_artifacts(STATIC_AUDIT, tmp_path)
    directory = tmp_path
    assert (directory / "coverage-matrix.json").is_file()
    assert (directory / "gap-report.md").is_file()
    assert (directory / "SHA256SUMS").is_file()
    matrix = json.loads((directory / "coverage-matrix.json").read_text(encoding="utf-8"))
    assert matrix == STATIC_AUDIT
    sums = (directory / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(sums) == 2
    entries = {}
    for line in sums:
        digest, name = line.split("  ", 1)
        entries[name] = digest
    for name in ("coverage-matrix.json", "gap-report.md"):
        payload = (directory / name).read_bytes()
        assert entries[name] == hashlib.sha256(payload).hexdigest()
    # Deterministic second write.
    written_again = coverage_audit.write_artifacts(STATIC_AUDIT, tmp_path)
    assert written["sha256"] == written_again["sha256"]


def test_module_records_mid_flight_import_failure() -> None:
    module, error = coverage_audit._load_module(
        "app.services.__audit_missing_module__"
    )
    assert module is None
    assert isinstance(error, str) and error


def test_probe_subset_returns_probe_rows() -> None:
    if len(sys.argv) > 0 and "pytest" not in sys.argv[0]:
        pytest.skip("only meaningful under pytest")
    audit = coverage_audit.build_audit(
        include_probes=True,
        max_fixture_probes=1,
        budget_seconds=120.0,
    )
    assert audit["mode"] == "full"
    fixture_probes = audit["probes"]["fixtures"]
    assert fixture_probes, "the full audit must probe at least one fixture"
    row = fixture_probes[0]
    assert row["status"] in {"ok", "module_not_ready", "probe_error",
                             "skipped_budget"}
    if row["status"] == "ok":
        assert "disposition" in row
        assert "checks" in row
    assert audit["bounds"]["fixtures_probed"] >= 1


def test_cli_static_run_writes_artifacts(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "audit_capability_coverage.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--static-only",
         "--output-dir", str(tmp_path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "coverage-matrix.json").is_file()
    assert (tmp_path / "gap-report.md").is_file()
    assert (tmp_path / "SHA256SUMS").is_file()
    assert "audit: gaps=" in proc.stdout
