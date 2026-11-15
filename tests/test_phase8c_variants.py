"""Phase-8C C8: compiler/flag variant validation and drop behavior tests."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "benchmark" / "phase8c"
MANIFEST_PATH = PUBLIC / "manifest.json"
PROVENANCE_PATH = PUBLIC / "PROVENANCE.json"
VARIANT_IDS = {
    "variant-cwe122-O2", "variant-cwe122-O2-stripped",
    "variant-cwe125-O3-static", "variant-cwe125-Os-static-stripped",
}
ALLOWED_SOURCES = {"repair-cwe122", "repair-cwe125"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


@lru_cache(maxsize=None)
def _builder():
    spec = importlib.util.spec_from_file_location(
        "_phase8c_builder_variants", ROOT / "scripts/build_phase8c_corpus.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=None)
def _manifest() -> dict:
    assert MANIFEST_PATH.is_file()
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _provenance() -> dict:
    return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))


def _variants() -> dict[str, dict]:
    return {sample["sample_id"]: sample for sample in _manifest()["samples"]
            if sample["sample_id"] in VARIANT_IDS}


def test_variants_are_validated_and_from_two_sources():
    variants = _variants()
    assert set(variants) == VARIANT_IDS
    provenance = _provenance()
    records = {record["sample_id"]: record for record in provenance["variants"]}
    assert set(records) == VARIANT_IDS
    sources = {record["source_sample"] for record in records.values()}
    assert sources == ALLOWED_SOURCES
    combos = set()
    for sample_id, sample in variants.items():
        record = records[sample_id]
        assert record["status"] == "validated"
        assert record["oracle_validation"]["executed"] is True
        assert record["oracle_validation"]["original_vulnerable_observed"] is True
        assert record["oracle_validation"]["status"] == "fail"
        assert record["oracle_validation"]["runner"]
        assert sample["binary_sha256"] == _sha256_file(ROOT / record["binary"])
        assert sample["split"] == ("dev" if sample_id in {
            "variant-cwe122-O2", "variant-cwe125-O3-static"} else "validation")
        assert sample["expected_scope"] == "function"
        assert sample["oracle"]["kind"] == "external_poc"
        assert sample["oracle"]["manifest_path"] == record["poc"]
        poc = json.loads((ROOT / record["poc"]).read_text(encoding="utf-8"))
        assert poc["fixture_sha256"] == sample["binary_sha256"]
        assert sample["oracle"]["manifest_path"] in sample["evidence_refs"]
        combos.add((sample["optimization_level"], sample["stripping_status"],
                    sample["linking_mode"]))
    # Distinct optimization/strip/link configurations, never duplicates.
    assert len(combos) == 4
    assert {combo[0] for combo in combos} == {"-O2", "-O3", "-Os"}
    assert {combo[1] for combo in combos} == {"stripped", "not_stripped"}
    assert {combo[2] for combo in combos} == {"static", "dynamic"}


def test_variant_build_records_are_complete():
    provenance = _provenance()
    for record in provenance["variants"]:
        build = json.loads((ROOT / record["build_record"]).read_text(
            encoding="utf-8"))
        assert build["compiler"] == "zig"
        assert build["compiler_version"] == "0.17.1"
        assert build["target"] in {"x86_64-linux-gnu", "x86_64-linux-musl"}
        assert build["output_sha256"] == record["binary_sha256"]
        assert build["optimization"] in {"-O2", "-O3", "-Os"}
        assert isinstance(build["flags"], list) and build["flags"]
        assert build["source"].startswith("fixtures/repair-benchmark/")
        assert build["oracle_validation"]["expected_original_fail_observed"] is True
        assert build["network"] is False
        assert build["command"][0].endswith("zig")
        assert "-target" in build["command"]


def test_negative_attempts_are_recorded_not_admitted():
    manifest_ids = {sample["sample_id"] for sample in _manifest()["samples"]}
    attempts = _provenance()["variant_attempts"]
    assert len(attempts) == 3
    assert {record["attempt_id"] for record in attempts} == {
        "attempt-cwe122-musl-O2-static",
        "attempt-cwe787-musl-O3-static",
        "attempt-cwe122-gnu-static",
    }
    for record in attempts:
        assert record["status"] == "dropped"
        assert record["reason"]
        assert record["attempt_id"] not in manifest_ids
        assert record["compiler"] == "zig"
        assert record["compiler_version"] == "0.17.1"
    gnu = next(record for record in attempts
               if record["attempt_id"] == "attempt-cwe122-gnu-static")
    assert "requires dynamic linking" in gnu["reason"]
    musl = next(record for record in attempts
                if record["attempt_id"] == "attempt-cwe122-musl-O2-static")
    assert "did not crash" in musl["reason"]
    assert musl["oracle_validation"]["original_vulnerable_observed"] is False


def test_poc_manifest_identity_is_enforced_for_variants():
    builder = _builder()
    record = _provenance()["variants"][0]
    poc = json.loads((ROOT / record["poc"]).read_text(encoding="utf-8"))
    with pytest.raises(ValueError):
        builder._poc_facts(record["poc"], "0" * 64)
    assert poc["fixture_sha256"] == record["binary_sha256"]


def test_validation_rejects_unavailable_or_non_vulnerable_oracle(monkeypatch):
    builder = _builder()

    class _Evidence:
        def __init__(self, payload):
            self._payload = payload

        def to_dict(self):
            return self._payload

    binary = ROOT / _provenance()["variants"][0]["binary"]
    variant_poc = ROOT / _provenance()["variants"][0]["poc"]

    monkeypatch.setattr(
        "app.services.poc_runner.run_poc",
        lambda *args, **kwargs: _Evidence(
            {"status": "unavailable", "runner": "", "tier": "", "poc": []}),
    )
    result = builder._validate_variant_oracle(binary, variant_poc)
    assert result["executed"] is False
    assert result["reason"]

    monkeypatch.setattr(
        "app.services.poc_runner.run_poc",
        lambda *args, **kwargs: _Evidence({
            "status": "fail",
            "runner": "limactl",
            "tier": "emulated_run",
            "poc": [{"executable": "original", "kind": "poc",
                     "case_id": "x", "crashed": False}],
        }),
    )
    result = builder._validate_variant_oracle(binary, variant_poc)
    assert result["executed"] is True
    assert result["original_vulnerable_observed"] is False
    assert result["reason"] and "did not crash" in result["reason"]

    monkeypatch.setattr(
        "app.services.poc_runner.run_poc",
        lambda *args, **kwargs: _Evidence({
            "status": "fail",
            "runner": "limactl",
            "tier": "emulated_run",
            "poc": [{"executable": "original", "kind": "poc",
                     "case_id": "x", "crashed": True}],
        }),
    )
    result = builder._validate_variant_oracle(binary, variant_poc)
    assert result["reason"] is None
    assert result["original_vulnerable_observed"] is True


def test_semantic_validation_rejects_runtime_oracle_on_analysis_only():
    builder = _builder()
    manifest = json.loads(json.dumps(_manifest()))
    sample = next(item for item in manifest["samples"]
                  if item["expected_scope"] == "analysis_only")
    sample["oracle"]["kinds"] = ["external_poc"]
    violations = builder._semantic_violations(manifest)
    assert any("analysis_only must not claim a runtime oracle" in item
               for item in violations)
