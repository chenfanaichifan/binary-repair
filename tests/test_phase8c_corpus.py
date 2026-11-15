"""Phase-8C C3/C9: public ground-truth corpus v2 manifest and builder tests."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "benchmark" / "phase8c"
MANIFEST_PATH = PUBLIC / "manifest.json"
README_PATH = PUBLIC / "README.md"
PROVENANCE_PATH = PUBLIC / "PROVENANCE.json"
SUMS_PATH = PUBLIC / "SHA256SUMS"
V1_MANIFEST = ROOT / "benchmark" / "phase8-v1" / "manifest.json"
SCHEMA_MANIFEST = ROOT / "contracts" / "benchmark-manifest-v2.schema.json"
SCHEMA_SAMPLE = ROOT / "contracts" / "ground-truth-sample-v2.schema.json"
PYTHON = sys.executable
RUNTIME_KINDS = {"external_poc", "native", "emulated"}
HARD_IDS = {
    "hard-loop8", "hard-loop16", "hard-loop32", "hard-loop64",
    "hard-reverse", "heap-malloc",
}
REPAIR_IDS = {
    "repair-cwe122", "repair-cwe125", "repair-cwe134",
    "repair-cwe190", "repair-cwe476", "repair-cwe787",
}
XARCH_IDS = {
    "xarch-macho-arm64", "xarch-macho-x86_64",
    "xarch-pe-arm64", "xarch-pe-x64",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=None)
def _builder():
    return _load_module("_phase8c_builder", "scripts/build_phase8c_corpus.py")


@lru_cache(maxsize=None)
def _manifest() -> dict:
    assert MANIFEST_PATH.is_file(), (
        "missing benchmark/phase8c/manifest.json; run "
        "scripts/build_phase8c_corpus.py --write")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _provenance() -> dict:
    return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))


def _run_builder(*args: str) -> subprocess.CompletedProcess:
    env = dict(**{})
    env.update({
        "PATH": str(Path(sys.executable).parent) + ":" + env.get("PATH", ""),
    })
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "build_phase8c_corpus.py"), *args],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600,
    )


# ---------------------------------------------------------------------------
# Manifest shape / schema / counts
# ---------------------------------------------------------------------------


def test_manifest_wrapper_and_counts():
    manifest = _manifest()
    assert manifest["schema_version"] == 2
    assert manifest["kind"] == "ground_truth_benchmark_v2"
    assert manifest["benchmark_id"] == "phase8c-public-v2"
    assert manifest["generated_at"] == "2026-11-16T00:00:00Z"
    assert manifest["hidden_available"] is False
    assert manifest["hidden_commitment"] is None
    samples = manifest["samples"]
    assert manifest["sample_count"] == len(samples) == 32
    assert manifest["split_counts"] == {"dev": 18, "validation": 14}
    ids = [sample["sample_id"] for sample in samples]
    assert len(ids) == len(set(ids))
    core = [sample for sample in samples if sample["sample_id"] not in {
        "variant-cwe122-O2", "variant-cwe122-O2-stripped",
        "variant-cwe125-O3-static", "variant-cwe125-Os-static-stripped",
    }]
    assert len(core) == 28
    variants = [sample for sample in samples if sample["sample_id"].startswith("variant-")]
    assert len(variants) == 4
    assert {sample["split"] for sample in variants} == {"dev", "validation"}


def test_manifest_and_samples_validate_against_c2_schemas():
    jsonschema = pytest.importorskip("jsonschema")
    manifest = _manifest()
    manifest_validator = jsonschema.Draft202012Validator(
        json.loads(SCHEMA_MANIFEST.read_text(encoding="utf-8")))
    sample_validator = jsonschema.Draft202012Validator(
        json.loads(SCHEMA_SAMPLE.read_text(encoding="utf-8")))
    assert not list(manifest_validator.iter_errors(manifest))
    for sample in manifest["samples"]:
        errors = list(sample_validator.iter_errors(sample))
        assert not errors, (sample["sample_id"], [error.message for error in errors])
    builder = _builder()
    assert builder._semantic_violations(manifest) == []
    assert builder._schema_violations(manifest) == []


def test_core_group_composition_and_split_assignment():
    samples = {sample["sample_id"]: sample for sample in _manifest()["samples"]}
    v1_ids = {sample["sample_id"] for sample in
              json.loads(V1_MANIFEST.read_text(encoding="utf-8"))["samples"]}
    assert set(samples) >= v1_ids
    assert len(v1_ids) == 12
    assert HARD_IDS <= set(samples) and len(HARD_IDS) == 6
    assert REPAIR_IDS <= set(samples) and len(REPAIR_IDS) == 6
    assert XARCH_IDS <= set(samples) and len(XARCH_IDS) == 4
    expected = {
        "hard-loop8": "dev", "hard-loop16": "dev", "hard-loop32": "dev",
        "hard-loop64": "validation", "hard-reverse": "validation",
        "heap-malloc": "validation",
        "repair-cwe122": "dev", "repair-cwe125": "dev", "repair-cwe134": "dev",
        "repair-cwe190": "validation", "repair-cwe476": "validation",
        "repair-cwe787": "validation",
        "xarch-macho-arm64": "dev", "xarch-macho-x86_64": "dev",
        "xarch-pe-arm64": "validation", "xarch-pe-x64": "validation",
    }
    for sample_id, split in expected.items():
        assert samples[sample_id]["split"] == split, sample_id
    runtime = sum(
        1 for sample in samples.values()
        if set((sample["oracle"] or {}).get("kinds") or []) & RUNTIME_KINDS)
    analysis = sum(1 for sample in samples.values()
                   if sample["expected_scope"] == "analysis_only")
    assert runtime == 24 and analysis == 8
    core_runtime = sum(
        1 for sample_id, sample in samples.items()
        if sample_id not in {
            "variant-cwe122-O2", "variant-cwe122-O2-stripped",
            "variant-cwe125-O3-static", "variant-cwe125-Os-static-stripped",
        } and set((sample["oracle"] or {}).get("kinds") or []) & RUNTIME_KINDS)
    core_analysis = sum(
        1 for sample_id, sample in samples.items()
        if sample_id not in {
            "variant-cwe122-O2", "variant-cwe122-O2-stripped",
            "variant-cwe125-O3-static", "variant-cwe125-Os-static-stripped",
        } and sample["expected_scope"] == "analysis_only")
    assert core_runtime == 20 and core_analysis == 8


# ---------------------------------------------------------------------------
# v1 lossless migration + every source/oracle/reference/provenance binding
# ---------------------------------------------------------------------------


def test_v1_samples_migrate_losslessly():
    migration = _load_module(
        "_phase8c_migration_check", "scripts/migrate_ground_truth_v2.py")
    v1 = json.loads(V1_MANIFEST.read_text(encoding="utf-8"))
    v2 = {sample["sample_id"]: sample for sample in _manifest()["samples"]}
    assert len(v1["samples"]) == 12
    for source in v1["samples"]:
        target = v2[source["sample_id"]]
        assert migration._lossless_for_sample(source, target), source["sample_id"]
        assert target["binary_sha256"] == source["sha256"]
        assert target["split"] == source["split"]
        assert target["target"] == source["target"]
        assert target["oracle"]["manifest_path"] == source["oracle"].get("manifest_path")
        assert target["oracle"]["kinds"] == source["oracle"].get("kinds")
        assert target["source_refs"] == source["source_refs"]
        assert target["evidence_refs"] == source["evidence_refs"]


def test_every_sample_binary_poc_and_reference_binding():
    manifest = _manifest()
    for sample in manifest["samples"]:
        binary = ROOT / sample["source_refs"][0]
        assert binary.is_file(), (sample["sample_id"], binary)
        assert _sha256_file(binary) == sample["binary_sha256"], sample["sample_id"]
        for ref in sample["source_refs"]:
            path = ref.split("#", 1)[0]
            if path.startswith("benchmark/phase8c/"):
                assert (ROOT / path).is_file(), (sample["sample_id"], path)
        for ref in sample["evidence_refs"]:
            path = ref.split("#", 1)[0]
            assert (ROOT / path).is_file(), (sample["sample_id"], ref)
        reference = sample["reference_fix"]
        if reference is not None:
            target = ROOT / reference["path"]
            assert target.is_file()
            assert reference["sha256"] == _sha256_file(target)
        oracle = sample["oracle"]
        if oracle.get("manifest_path"):
            poc_path = ROOT / oracle["manifest_path"]
            assert poc_path.is_file(), sample["sample_id"]
            poc = json.loads(poc_path.read_text(encoding="utf-8"))
            assert poc["fixture_sha256"] == sample["binary_sha256"], sample["sample_id"]
        scope = sample["expected_scope"]
        kinds = set(oracle.get("kinds") or []) | {oracle.get("kind")}
        if scope in {"function", "whole_program"}:
            assert kinds & RUNTIME_KINDS, sample["sample_id"]
        else:
            assert not (kinds & RUNTIME_KINDS), sample["sample_id"]


def test_cross_arch_samples_are_analysis_only():
    manifest = _manifest()
    by_id = {sample["sample_id"]: sample for sample in manifest["samples"]}
    formats = set()
    for sample_id in XARCH_IDS:
        sample = by_id[sample_id]
        formats.add(sample["format"])
        assert sample["expected_scope"] == "analysis_only"
        assert sample["target"] == {"kind": "analysis_only"}
        assert sample["oracle"]["kind"] == "static"
        assert sample["oracle"]["kinds"] == ["static"]
        assert sample["oracle"]["manifest_path"] is None
        assert sample["oracle"]["expected_original"] is None
        assert sample["oracle"]["expected_candidate"] is None
        assert sample["semantic_regression"] is None
        assert sample["reference_fix"] is None
        assert sample["limitations"]
    assert formats == {"macho", "pe"}


# ---------------------------------------------------------------------------
# Builder determinism / tamper / variant records
# ---------------------------------------------------------------------------


def test_builder_is_deterministic_and_check_passes():
    first = _run_builder("--json")
    second = _run_builder("--json")
    assert first.returncode == 0, first.stderr + first.stdout
    assert second.returncode == 0, second.stderr + second.stdout
    payload_a = json.loads(first.stdout)
    payload_b = json.loads(second.stdout)
    assert payload_a == payload_b
    assert payload_a["sample_count"] == 32
    assert payload_a["core_sample_count"] == 28
    assert payload_a["variant_count"] == 4
    assert payload_a["lossless_v1_migration"] is True
    assert payload_a["hidden_available"] is False
    check = _run_builder("--check")
    assert check.returncode == 0, check.stdout + check.stderr
    assert json.loads(check.stdout)["ok"] is True


def test_builder_check_detects_tamper(tmp_path):
    target = tmp_path / "artifact"
    shutil.copytree(PUBLIC, target)
    payload = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    payload["sample_count"] += 1
    (target / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    result = _run_builder("--check", "--out", str(target))
    assert result.returncode == 1
    assert json.loads(result.stdout)["ok"] is False


def test_builder_check_detects_binary_tamper(tmp_path):
    target = tmp_path / "artifact"
    shutil.copytree(PUBLIC, target)
    variant = target / "bin" / "variant-cwe122-O2.elf"
    assert variant.is_file()
    variant.write_bytes(variant.read_bytes() + b"tamper")
    result = _run_builder("--check", "--out", str(target))
    assert result.returncode == 1
    problems = json.loads(result.stdout)["problems"]
    assert any("variant-cwe122-O2.elf" in item or "SHA256SUMS" in item
               for item in problems)


def test_artifact_sums_cover_every_payload():
    files = {}
    for line in SUMS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split(None, 1)
        files[relative.strip()] = digest
    on_disk = {
        path.relative_to(PUBLIC).as_posix()
        for path in PUBLIC.rglob("*") if path.is_file()
    }
    on_disk.discard("SHA256SUMS")
    assert set(files) == on_disk
    for relative, digest in files.items():
        assert _sha256_file(PUBLIC / relative) == digest
    for relative in files:
        if not relative.endswith((".elf", ".exe")):
            (PUBLIC / relative).read_bytes().decode("ascii")


def test_provenance_records_variants_attempts_and_toolchain():
    provenance = _provenance()
    manifest = _manifest()
    assert provenance["kind"] == "phase8c_public_corpus_provenance"
    assert provenance["migration"]["sample_count"] == 12
    assert provenance["migration"]["lossless"] is True
    assert provenance["source_manifest"]["sha256"] == _sha256_file(V1_MANIFEST)
    variants = provenance["variants"]
    assert len(variants) == 4
    for record in variants:
        assert record["status"] == "validated"
        assert record["compiler"] == "zig"
        assert record["compiler_version"] == "0.17.1"
        assert record["oracle_validation"]["executed"] is True
        assert record["oracle_validation"]["original_vulnerable_observed"] is True
        assert record["binary_sha256"] == _sha256_file(ROOT / record["binary"])
        assert record["build_record"] and record["poc"]
    attempts = provenance["variant_attempts"]
    assert len(attempts) == 3
    for record in attempts:
        assert record["status"] == "dropped"
        assert record["reason"]
        assert record["attempt_id"] not in {
            sample["sample_id"] for sample in manifest["samples"]}
    assert provenance["toolchain"]["zig"]["version"] == "0.17.1"
    assert any("requires dynamic linking" in (record.get("reason") or "")
               for record in attempts), (
        "the gnu-static probe must record Zig's dynamic-linking limitation")


def test_builder_has_no_ai_or_network_paths():
    source = (ROOT / "scripts" / "build_phase8c_corpus.py").read_text(
        encoding="utf-8").lower()
    for forbidden in ("requests.", "urllib.request", "httpjsonclient",
                      "assistant_llm", "openai", "siliconflow", "socket."):
        assert forbidden not in source, forbidden
    assert "no ai" in source or "no network" in source
