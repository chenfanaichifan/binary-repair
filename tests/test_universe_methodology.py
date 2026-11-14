"""Tests for the capability-universe methodology checker."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import check_universe_methodology as checker  # noqa: E402
from app.services import coverage_audit  # noqa: E402


@pytest.fixture(scope="module")
def universe() -> dict:
    audit = coverage_audit.build_audit(include_probes=False)
    return audit["universe"]


@pytest.fixture(scope="module")
def registry() -> dict:
    return checker.build_registry()


def _report(universe: dict, registry: dict) -> dict:
    return checker.evaluate_methodology(universe=universe, registry=registry)


def _tampered_cell(universe: dict, **overrides: object) -> dict:
    mutated = copy.deepcopy(universe)
    cells = copy.deepcopy(mutated["cells"])
    target = None
    for cell in cells:
        if cell.get("status") == "supported":
            target = cell
            break
    assert target is not None
    target.update(overrides)
    mutated["cells"] = cells
    return mutated


def test_registry_snapshot_is_canonical_and_deterministic(registry: dict) -> None:
    second = checker.build_registry()
    assert checker._sha256_json(registry) == checker._sha256_json(second)
    assert len(checker._sha256_json(registry)) == 64
    repair = registry["repair_matrix"]
    assert len(repair["cells"]) == 8
    assert set(repair["sink_classes"]) == {
        "unbounded_copy", "memcpy_length", "syscall_length", "checked_copy",
        "capacity_check_mismatch"}
    assert set(repair["strategy_profiles"]) == {
        "strict-template", "immediate", "guard", "capacity"}
    assert set(repair["evidence_profiles"]) == {
        "strict_template", "emulated_instruction", "native_poc",
        "native_poc_rewrite"}
    taxonomy = registry["universe_taxonomy"]
    assert taxonomy["dimensions"] == list(checker.DIMENSIONS)
    assert len(checker.DIMENSIONS) == 11


def test_methodology_passes_on_live_universe(universe: dict,
                                            registry: dict) -> None:
    report = _report(universe, registry)
    assert report["ok"] is True, (
        report["unexplained_cells"][:3], report["missing_registry_entries"][:3])
    assert report["cell_count"] == len(universe["cells"]) == 240
    assert report["unknown"] == 0
    assert report["missing_registry_entries"] == []
    assert report["unexplained_cells"] == []
    assert report["unexplained_cell_count"] == 0
    assert len(report["registry_sha256"]) == 64
    assert len(report["unknown_rules"]) >= 4
    assert set(report["dimensions"]) == set(checker.DIMENSIONS)


def test_every_dimension_value_is_registered_and_observed(
        universe: dict, registry: dict) -> None:
    report = _report(universe, registry)
    for dimension, detail in report["dimensions"].items():
        assert set(detail["values"]) <= set(detail["allowed"]), dimension
        assert detail["values"], dimension
    # reverse coverage: every registry entry appears at least once
    required = checker._registry_required_entries(registry)
    for value in required["strategy"]:
        assert value in report["dimensions"]["strategy"]["values"]
    for value in required["sink_class"]:
        assert value in report["dimensions"]["sink_class"]["values"]
    for value in required["runtime_tier"]:
        assert value in report["dimensions"]["runtime_tier"]["values"]
    for value in required["evidence_profile"]:
        assert value in report["dimensions"]["evidence_profile"]["values"]


def test_unregistered_sink_is_reported(universe: dict, registry: dict) -> None:
    mutated = _tampered_cell(universe, sink_class="audit_unregistered_sink")
    report = _report(mutated, registry)
    assert report["ok"] is False
    assert any("unregistered sink_class" in item
               for item in report["unexplained_cells"])


def test_unregistered_strategy_is_reported(universe: dict,
                                           registry: dict) -> None:
    mutated = _tampered_cell(universe, strategy="audit_unregistered_strategy")
    report = _report(mutated, registry)
    assert report["ok"] is False
    assert any("unregistered strategy" in item
               for item in report["unexplained_cells"])


def test_unregistered_platform_is_reported(universe: dict,
                                           registry: dict) -> None:
    for field, value in (("container", "plan9"), ("arch", "riscv")):
        mutated = _tampered_cell(universe, **{field: value})
        report = _report(mutated, registry)
        assert report["ok"] is False
        assert any(f"unregistered {field}" in item
                   for item in report["unexplained_cells"])


def test_unknown_cell_fails_the_methodology(universe: dict,
                                            registry: dict) -> None:
    mutated = copy.deepcopy(universe)
    cells = copy.deepcopy(mutated["cells"])
    cells[0]["status"] = "unknown"
    mutated["cells"] = cells
    report = _report(mutated, registry)
    assert report["ok"] is False
    assert report["unknown"] == 1


def test_missing_registry_entry_is_reported(universe: dict,
                                            registry: dict) -> None:
    mutated = copy.deepcopy(universe)
    mutated["cells"] = [
        cell for cell in mutated["cells"]
        if cell.get("sink_class") != "syscall_length"]
    report = _report(mutated, registry)
    assert report["ok"] is False
    assert "sink_class:syscall_length" in report["missing_registry_entries"]


def test_summary_disagreement_fails_closed(universe: dict,
                                           registry: dict) -> None:
    mutated = copy.deepcopy(universe)
    mutated["unknown"] = 5
    report = _report(mutated, registry)
    assert report["ok"] is False
    assert any("summary.unknown" in item
               for item in report["missing_registry_entries"])


def test_write_artifact_is_deterministic(tmp_path: Path, universe: dict,
                                         registry: dict) -> None:
    report = _report(universe, registry)
    first = checker.write_artifact(report, tmp_path / "artifact")
    methodology = Path(first["methodology_path"])
    assert methodology.is_file()
    sums = Path(first["sums_path"])
    assert sums.is_file()
    assert sums.read_text(encoding="utf-8") == (
        f"{first['methodology_sha256']}  methodology.json\n")
    assert hashlib.sha256(methodology.read_bytes()).hexdigest() == (
        first["methodology_sha256"])
    document = json.loads(methodology.read_text(encoding="utf-8"))
    assert document["registry_sha256"] == report["registry_sha256"]
    assert document["check"]["ok"] is True
    assert document["check"]["cell_count"] == report["cell_count"]


def test_cli_check_and_json_contract() -> None:
    check = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_universe_methodology.py"),
         "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert "universe-methodology: ok=True" in check.stdout
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_universe_methodology.py"),
         "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["cell_count"] == 240
    assert payload["unknown"] == 0
    for field in ("dimensions", "registry_sha256", "cell_count", "unknown",
                  "missing_registry_entries", "unexplained_cells",
                  "unknown_rules"):
        assert field in payload


def test_cli_write_artifact(tmp_path: Path) -> None:
    target = tmp_path / "universe-artifact"
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "check_universe_methodology.py"),
         "--check", "--write-artifact", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "methodology.json").is_file()
    assert (target / "SHA256SUMS").is_file()
