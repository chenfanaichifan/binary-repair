"""Tests for the Phase-8C ground-truth v2 contracts and v1 migration."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import check_contract_schemas as checker  # noqa: E402
import migrate_ground_truth_v2 as migrate  # noqa: E402

CONTRACTS = ROOT / "contracts"
FIXTURES = ROOT / "artifacts" / "contract-fixtures-2026-11-16"
SUMS = FIXTURES / "SHA256SUMS"
V1_MANIFEST = ROOT / "benchmark" / "phase8-v1" / "manifest.json"
V2_SCHEMAS = (
    "ground-truth-sample-v2",
    "benchmark-manifest-v2",
    "hidden-benchmark-commitment",
    "benchmark-results-v2",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture(name: str) -> dict:
    return _load(FIXTURES / f"{name}.valid.json")


def _validate(schema_name: str, payload: dict) -> list[str]:
    schema = _load(CONTRACTS / f"{schema_name}.schema.json")
    errors, _validator = checker._validate_instance(
        schema_name, schema, payload, use_jsonschema=True)
    return errors


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "migrate_ground_truth_v2.py"), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )


# ---------------------------------------------------------------------------
# Contracts and fixtures
# ---------------------------------------------------------------------------


def test_v2_schemas_exist_and_are_structurally_valid() -> None:
    for name in V2_SCHEMAS:
        path = CONTRACTS / f"{name}.schema.json"
        assert path.is_file(), name
        schema = _load(path)
        assert checker.check_schema_document(name, schema) == [], name
        raw = path.read_text(encoding="utf-8")
        assert all(ord(char) < 128 for char in raw), name


def test_v2_fixtures_exist_and_checker_registers_at_least_seventeen() -> None:
    # Phase-8C introduced exactly 17 contracts. Later phases may add contracts
    # (Phase-8D adds three); the historical 17 must remain registered and green.
    assert len(checker.SCHEMA_NAMES) >= 17
    for name in V2_SCHEMAS:
        assert (FIXTURES / f"{name}.valid.json").is_file(), name
        assert (FIXTURES / f"{name}.invalid.json").is_file(), name
    report = checker.run_check(ROOT, check_sums=True)
    assert report["ok"] is True, report["violations"]
    assert report["schema_count"] == len(checker.SCHEMA_NAMES)
    assert report["fixtures"]["valid_passed"] == len(checker.SCHEMA_NAMES)
    assert report["fixtures"]["invalid_rejected"] == len(checker.SCHEMA_NAMES)
    lines = [line for line in SUMS.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    assert len(lines) == len(checker.SCHEMA_NAMES) * 3


def test_old_contract_fixtures_and_artifacts_stay_green() -> None:
    report = checker.run_check(ROOT, check_sums=True)
    assert report["ok"] is True
    statuses = {item["id"]: item["status"] for item in report["integrations"]}
    for old_id in ("capability-universe", "gap-registry",
                   "autonomous-reflection", "benchmark-manifest",
                   "verification-report"):
        assert statuses[old_id] == "validated", old_id
    for new_id in ("phase8c-public-manifest", "phase8c-hidden-commitment",
                   "phase8c-results"):
        assert statuses[new_id] in {"not_run", "validated"}, new_id
    for name in ("capability", "acceptance", "patch-plan", "verification",
                 "benchmark-sample"):
        assert _validate(name, _fixture(name)) == [], name


# ---------------------------------------------------------------------------
# Cross-field semantics / fail-closed behavior
# ---------------------------------------------------------------------------


def test_ground_truth_sample_semantics_fail_closed() -> None:
    payload = _fixture("ground-truth-sample-v2")
    assert _validate("ground-truth-sample-v2", payload) == []
    assert checker.CONTRACT_SEMANTICS["ground-truth-sample-v2"](payload) == []

    hidden_split = json.loads(json.dumps(payload))
    hidden_split["split"] = "hidden"
    assert _validate("ground-truth-sample-v2", hidden_split)

    runtime_scope = json.loads(json.dumps(payload))
    runtime_scope["expected_scope"] = "whole_program"
    runtime_scope["oracle"]["kind"] = "static"
    runtime_scope["oracle"]["kinds"] = ["static"]
    violations = checker.CONTRACT_SEMANTICS["ground-truth-sample-v2"](
        runtime_scope)
    assert any("runtime oracle" in item for item in violations)

    no_limitations = json.loads(json.dumps(payload))
    no_limitations["abi"] = None
    no_limitations["limitations"] = []
    violations = checker.CONTRACT_SEMANTICS["ground-truth-sample-v2"](
        no_limitations)
    assert any("limitations" in item for item in violations)


def test_manifest_v2_semantics_fail_closed() -> None:
    payload = _fixture("benchmark-manifest-v2")
    assert _validate("benchmark-manifest-v2", payload) == []
    assert checker.CONTRACT_SEMANTICS["benchmark-manifest-v2"](payload) == []

    hidden_available = json.loads(json.dumps(payload))
    hidden_available["hidden_available"] = True
    assert _validate("benchmark-manifest-v2", hidden_available)

    count_mismatch = json.loads(json.dumps(payload))
    count_mismatch["sample_count"] = 2
    violations = checker.CONTRACT_SEMANTICS["benchmark-manifest-v2"](
        count_mismatch)
    assert any("sample_count" in item for item in violations)

    commitment_mismatch = json.loads(json.dumps(payload))
    commitment_mismatch["hidden_commitment"]["counts"] = {
        "sample_count": 2, "runtime_count": 0, "analysis_only_count": 0}
    violations = checker.CONTRACT_SEMANTICS["benchmark-manifest-v2"](
        commitment_mismatch)
    assert any("counts" in item for item in violations)


def test_hidden_commitment_semantics_fail_closed() -> None:
    payload = _fixture("hidden-benchmark-commitment")
    assert _validate("hidden-benchmark-commitment", payload) == []
    assert checker.CONTRACT_SEMANTICS["hidden-benchmark-commitment"](
        payload) == []

    count_mismatch = json.loads(json.dumps(payload))
    count_mismatch["sample_count"] = 1
    violations = checker.CONTRACT_SEMANTICS["hidden-benchmark-commitment"](
        count_mismatch)
    assert any("sample_count" in item for item in violations)

    path_leak = json.loads(json.dumps(payload))
    path_leak["limitations"] = ["hidden root is /home/user/.binaryrepair"]
    violations = checker.CONTRACT_SEMANTICS["hidden-benchmark-commitment"](
        path_leak)
    assert any("paths" in item for item in violations)

    duplicate_ids = json.loads(json.dumps(payload))
    duplicate_ids["samples"][1]["opaque_sample_id"] = duplicate_ids["samples"][
        0]["opaque_sample_id"]
    violations = checker.CONTRACT_SEMANTICS["hidden-benchmark-commitment"](
        duplicate_ids)
    assert any("unique" in item for item in violations)


def test_results_v2_semantics_fail_closed() -> None:
    payload = _fixture("benchmark-results-v2")
    assert _validate("benchmark-results-v2", payload) == []
    assert checker.CONTRACT_SEMANTICS["benchmark-results-v2"](payload) == []

    bad_status = json.loads(json.dumps(payload))
    bad_status["samples"][0]["status"] = "passed"
    assert _validate("benchmark-results-v2", bad_status)

    count_mismatch = json.loads(json.dumps(payload))
    count_mismatch["aggregate"]["status_counts"]["executed"] = 2
    violations = checker.CONTRACT_SEMANTICS["benchmark-results-v2"](
        count_mismatch)
    assert any("status_counts.executed" in item for item in violations)

    missing_reason = json.loads(json.dumps(payload))
    missing_reason["samples"][0]["status"] = "not_run"
    missing_reason["samples"][0]["not_run_reason"] = None
    missing_reason["aggregate"]["status_counts"] = {
        "executed": 0, "not_run": 1, "blocked": 0, "unsupported": 0,
        "invalid": 0}
    missing_reason["aggregate"]["denominator"] = {
        "samples": 1, "executed": 0, "verification_attempted": 0}
    violations = checker.CONTRACT_SEMANTICS["benchmark-results-v2"](
        missing_reason)
    assert any("not_run_reason" in item for item in violations)

    fake_verified = json.loads(json.dumps(payload))
    fake_verified["samples"][0]["false_verified"] = True
    fake_verified["samples"][0]["verification"]["decision"] = "rejected"
    fake_verified["aggregate"]["false_verified_count"] = 1
    fake_verified["aggregate"]["verified_count"] = 0
    fake_verified["aggregate"]["rejected_count"] = 1
    violations = checker.CONTRACT_SEMANTICS["benchmark-results-v2"](
        fake_verified)
    assert any("false_verified" in item for item in violations)


# ---------------------------------------------------------------------------
# v1 -> v2 migration
# ---------------------------------------------------------------------------


def test_migration_builds_all_twelve_samples_losslessly() -> None:
    v1 = _load(V1_MANIFEST)
    migration = migrate.build_migration(V1_MANIFEST)
    manifest = migration["manifest"]
    report = migration["report"]
    assert report["sample_count"] == 12
    assert report["migrated_count"] == 12
    assert report["lossless"] is True
    assert report["lossless_count"] == 12
    assert manifest["sample_count"] == len(manifest["samples"]) == 12
    assert manifest["split_counts"] == v1["split_counts"]
    assert _validate("benchmark-manifest-v2", manifest) == []
    assert checker.CONTRACT_SEMANTICS["benchmark-manifest-v2"](manifest) == []
    for sample in manifest["samples"]:
        assert _validate("ground-truth-sample-v2", sample) == []
        assert checker.CONTRACT_SEMANTICS["ground-truth-sample-v2"](sample) == []
    v1_by_id = {item["sample_id"]: item for item in v1["samples"]}
    for sample in manifest["samples"]:
        original = v1_by_id[sample["sample_id"]]
        assert sample["binary_sha256"] == original["sha256"]
        assert sample["split"] == original["split"]
        assert sample["target"] == original["target"]
        assert sample["oracle"]["kinds"] == original["oracle"]["kinds"]
        assert sample["oracle"]["manifest_path"] == original["oracle"][
            "manifest_path"]
        assert sample["source_refs"] == original["source_refs"]
        assert sample["evidence_refs"] == original["evidence_refs"]
        if original.get("reference_fix"):
            assert sample["reference_fix"]["path"] == original["reference_fix"]
        assert sample["limitations"], sample["sample_id"]


def test_migration_is_deterministic_and_schema_clean() -> None:
    first = migrate.build_migration(V1_MANIFEST)
    second = migrate.build_migration(V1_MANIFEST)
    assert first["manifest_text"] == second["manifest_text"]
    assert first["report"] == second["report"]
    assert first["manifest_sha256"] == second["manifest_sha256"]


def test_migration_cli_write_check_and_tamper(tmp_path: Path) -> None:
    out = tmp_path / "v2"
    write = _run_cli("--write", "--out", str(out), "--json")
    assert write.returncode == 0, write.stdout + write.stderr
    payload = json.loads(write.stdout)
    assert payload["ok"] is True
    for name in ("manifest.json", "migration-report.json", "SHA256SUMS"):
        assert (out / name).is_file(), name
    check = _run_cli("--check", "--out", str(out), "--json")
    assert check.returncode == 0, check.stdout + check.stderr
    assert json.loads(check.stdout)["ok"] is True

    manifest_path = out / "manifest.json"
    tampered = _load(manifest_path)
    tampered["benchmark_id"] = "tampered"
    manifest_path.write_text(json.dumps(tampered, indent=2) + "\n",
                            encoding="utf-8")
    tamper_check = _run_cli("--check", "--out", str(out))
    assert tamper_check.returncode == 1
    assert "MIGRATION-VIOLATION" in tamper_check.stdout


def test_migration_rejects_missing_v1(tmp_path: Path) -> None:
    result = _run_cli("--v1", str(tmp_path / "missing.json"), "--check")
    assert result.returncode == 2


def test_migration_script_is_offline_and_clock_free() -> None:
    source = (SCRIPTS / "migrate_ground_truth_v2.py").read_text(encoding="utf-8")
    for forbidden in ("import requests", "import socket", "import urllib",
                      "import http", "import openai", "assistant_llm",
                      "datetime.now", "time.time", "time.clock"):
        assert forbidden not in source, forbidden


def test_migration_does_not_write_committed_c3_path() -> None:
    phase8c = ROOT / "benchmark" / "phase8c"
    before = phase8c.exists()
    migration = migrate.build_migration(V1_MANIFEST)
    assert migration["manifest"]["benchmark_id"] == "phase8-v1-migrated-v2"
    assert phase8c.exists() == before
