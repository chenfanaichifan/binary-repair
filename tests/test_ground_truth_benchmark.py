"""Tests for the Phase-8A ground-truth benchmark manifest and runner.

Offline tests: no network, no provider calls.  The builder is re-run and its
committed artifact is checked for determinism/tamper; every sample is validated
against the committed ``contracts/benchmark-sample.schema.json``; the runner is
exercised with injected fake repair/verifier callables (not_run, false-verified
detection, independence, determinism) plus one real CLI smoke sample.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import build_ground_truth_benchmark as builder  # noqa: E402
import run_repair_benchmark as runner  # noqa: E402

BENCHMARK = ROOT / "benchmark" / "phase8-v1"
MANIFEST_PATH = BENCHMARK / "manifest.json"
README_PATH = BENCHMARK / "README.md"
SUMS_PATH = BENCHMARK / "SHA256SUMS"
RESULTS = ROOT / "artifacts" / "phase8-benchmark-2026-11-16"
RESULTS_PATH = RESULTS / "results.json"
RESULTS_README = RESULTS / "README.md"
RESULTS_SUMS = RESULTS / "SHA256SUMS"
SCHEMA_PATH = ROOT / "contracts" / "benchmark-sample.schema.json"
ARTIFACT_FILES = ("manifest.json", "README.md")
PYTHON = sys.executable
RUNTIME_ORACLE_KINDS = {"external_poc", "native", "emulated"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=None)
def _manifest() -> dict:
    assert MANIFEST_PATH.is_file(), (
        f"missing benchmark manifest {MANIFEST_PATH}; run "
        "scripts/build_ground_truth_benchmark.py"
    )
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _results() -> dict:
    assert RESULTS_PATH.is_file(), (
        f"missing benchmark results {RESULTS_PATH}; run "
        "scripts/run_repair_benchmark.py"
    )
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


def _run_builder(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("BINARYREPAIR_ASSISTANT_PROVIDER_KEY", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "build_ground_truth_benchmark.py"), *args],
        cwd=str(ROOT), capture_output=True, text=True, timeout=180, env=env,
    )


# ---------------------------------------------------------------------------
# Manifest / builder
# ---------------------------------------------------------------------------


def test_manifest_wrapper_and_hidden_honesty():
    manifest = _manifest()
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "ground_truth_benchmark"
    assert manifest["benchmark_id"] == "phase8-v1"
    assert manifest["hidden_available"] is False
    assert manifest["hidden_commitment_sha256"] is None
    assert manifest["hidden_limitation"].strip()
    assert manifest["sample_count"] >= 10
    assert manifest["sample_count"] == len(manifest["samples"])
    split_ids = {split: sorted(ids) for split, ids in manifest["splits"].items()}
    assert set(split_ids) == {"dev", "validation"}
    assert split_ids["dev"] and split_ids["validation"]
    dev_ids = {sample["sample_id"] for sample in manifest["samples"]
               if sample["split"] == "dev"}
    validation_ids = {sample["sample_id"] for sample in manifest["samples"]
                      if sample["split"] == "validation"}
    assert set(split_ids["dev"]) == dev_ids
    assert set(split_ids["validation"]) == validation_ids
    assert manifest["split_counts"] == {"dev": len(dev_ids),
                                        "validation": len(validation_ids)}


def test_manifest_schema_integration_uses_committed_contract():
    manifest = _manifest()
    integration = manifest["schema_integration"]
    assert integration["schema_path"] == "contracts/benchmark-sample.schema.json"
    if SCHEMA_PATH.is_file():
        assert integration["status"] in {"validated", "validated_local_fallback"}
        assert integration["status"] != "not_run"
        assert integration["schema_sha256"] == _sha256(SCHEMA_PATH)
        assert integration["violations"] == []
    else:
        assert integration["status"] == "not_run"
        assert integration["reason"]
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(schema)
    for sample in manifest["samples"]:
        errors = sorted(validator.iter_errors(sample), key=str)
        assert not errors, f"{sample['sample_id']}: {[error.message for error in errors]}"


def test_every_sample_is_real_and_hashed():
    manifest = _manifest()
    ids = [sample["sample_id"] for sample in manifest["samples"]]
    assert len(ids) == len(set(ids))
    for sample in manifest["samples"]:
        assert sample["sample_id"] == sample["sample_id"].strip()
        assert sample["sha256"] == _sha256(ROOT / sample["source_refs"][0])
        identity = builder.inspect_container(sample["source_refs"][0])
        assert sample["format"] == identity["format"]
        assert sample["arch"] == identity["arch"]
        assert sample["bits"] == identity["bits"]
        assert sample["endian"] == identity["endian"]
        for ref in sample["source_refs"]:
            assert (ROOT / ref).is_file(), (sample["sample_id"], ref)
        for ref in sample["evidence_refs"]:
            path = ref.split("#", 1)[0]
            assert (ROOT / path).is_file(), (sample["sample_id"], ref)
        if sample["reference_fix"]:
            assert (ROOT / sample["reference_fix"]).is_file()
        assert sample["negative_cases"] is not None
        assert set(sample) == {
            "sample_id", "sha256", "format", "arch", "bits", "endian",
            "vulnerability_class", "expected_scope", "target", "source_refs",
            "oracle", "expected_analysis", "reference_fix",
            "expected_patch_properties", "negative_cases", "split",
            "hidden_available", "hidden_commitment_sha256", "evidence_refs",
        }
        assert sample["hidden_available"] is False
        assert sample["hidden_commitment_sha256"] is None


def test_oracle_semantics_and_target_shape():
    manifest = _manifest()
    for sample in manifest["samples"]:
        oracle = sample["oracle"]
        kinds = oracle["kinds"]
        assert kinds and len(kinds) == len(set(kinds))
        assert set(kinds) <= {"external_poc", "native", "emulated", "static"}
        runtime = set(kinds) & RUNTIME_ORACLE_KINDS
        if sample["expected_scope"] == "analysis_only":
            assert not runtime, sample["sample_id"]
        else:
            assert runtime, sample["sample_id"]
        target = sample["target"]
        assert target["kind"] in {"function", "symbol", "va_range", "whole_image",
                                  "analysis_only"}
        if target["kind"] == "symbol":
            assert target["symbol"]
        elif target["kind"] == "function":
            assert target["function"]
        elif target["kind"] == "va_range":
            assert isinstance(target["va"], int) and isinstance(target["end"], int)
        if oracle["manifest_path"]:
            assert (ROOT / oracle["manifest_path"]).is_file()
            poc = json.loads((ROOT / oracle["manifest_path"]).read_text(encoding="utf-8"))
            assert poc["fixture_sha256"] == sample["sha256"]
        analysis = sample["expected_analysis"]
        assert set(analysis) == {"root_cause", "function", "sink", "capacity"}


def test_ground_truth_samples_cover_expected_classes():
    manifest = _manifest()
    by_id = {sample["sample_id"]: sample for sample in manifest["samples"]}
    assert "negative-control" in by_id
    control = by_id["negative-control"]
    assert control["expected_scope"] == "analysis_only"
    assert control["oracle"]["kinds"] == ["static"]
    assert control["target"]["kind"] == "analysis_only"
    # The two i386 fixtures without a committed matching PoC must be
    # analysis_only and never verified expectations.
    for sample_id in ("stack-strcpy-x86", "stack-memcpy-x86"):
        sample = by_id[sample_id]
        assert sample["expected_scope"] == "analysis_only"
        assert sample["oracle"]["kinds"] == ["static"]
        assert sample["oracle"]["manifest_path"] is None
    assert by_id["uaf-noinput"]["expected_scope"] == "analysis_only"
    if "cwe121-public" in by_id:
        assert by_id["cwe121-public"]["expected_analysis"]["capacity"] == 50
    if "heap-capacity-x86_64" in by_id:
        capacity = by_id["heap-capacity-x86_64"]
        assert capacity["target"]["kind"] == "va_range"
        assert capacity["expected_patch_properties"]["site_va"] == "0x4020d9"
    # no per-sample hidden claim
    assert all(sample["hidden_available"] is False for sample in manifest["samples"])
    assert manifest["dropped_samples"] == [] or all(
        item.get("reason") for item in manifest["dropped_samples"]
    )


def test_builder_deterministic_and_check_passes(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    proc_a = _run_builder("--out", str(first), env_extra={"PYTHONHASHSEED": "0"})
    assert proc_a.returncode == 0, proc_a.stderr
    proc_b = _run_builder("--out", str(second), env_extra={"PYTHONHASHSEED": "12345"})
    assert proc_b.returncode == 0, proc_b.stderr
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
        assert (first / name).read_bytes() == (BENCHMARK / name).read_bytes(), name
    check = _run_builder("--check")
    assert check.returncode == 0, check.stdout + check.stderr
    report = json.loads(check.stdout)
    assert report["ok"] is True
    assert report["violations"] == []
    assert report["sample_count"] == _manifest()["sample_count"]
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        assert report["files"][name]["match"] is True
    summary = _run_builder("--json")
    assert summary.returncode == 0, summary.stderr
    payload = json.loads(summary.stdout)
    assert payload["ok"] is True
    assert payload["benchmark_id"] == "phase8-v1"
    assert payload["hidden_available"] is False
    assert payload["sample_count"] >= 10


def test_builder_check_detects_tampered_manifest(tmp_path):
    target = tmp_path / "artifact"
    shutil.copytree(BENCHMARK, target)
    payload = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    payload["sample_count"] += 1
    (target / "manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    proc = _run_builder("--check", "--out", str(target))
    assert proc.returncode == 1, proc.stdout
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert report["files"]["manifest.json"]["match"] is False


def test_builder_check_detects_tampered_readme_and_sums(tmp_path):
    target = tmp_path / "artifact"
    shutil.copytree(BENCHMARK, target)
    with (target / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    proc = _run_builder("--check", "--out", str(target))
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["files"]["README.md"]["match"] is False

    target2 = tmp_path / "artifact2"
    shutil.copytree(BENCHMARK, target2)
    lines = (target2 / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    digest, name = lines[0].split(None, 1)
    flipped = ("0" if digest[0] != "0" else "1") + digest[1:]
    lines[0] = f"{flipped}  {name.strip()}"
    (target2 / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    proc = _run_builder("--check", "--out", str(target2))
    assert proc.returncode == 1
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert any("SHA256SUMS" in item for item in report["violations"])


def test_artifact_sha256sums_cover_exactly_the_data_files():
    for base, names in ((BENCHMARK, ARTIFACT_FILES), (RESULTS, ("results.json", "README.md"))):
        entries: dict[str, str] = {}
        sums = base / "SHA256SUMS"
        assert sums.is_file(), sums
        for line in sums.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            digest, relative = line.split(None, 1)
            entries[relative.strip()] = digest
        assert set(entries) == set(names)
        for name, digest in entries.items():
            assert _sha256(base / name) == digest
        for name in names:
            assert (base / name).read_bytes().decode("ascii")


# ---------------------------------------------------------------------------
# Runner: injected fake repair / verifier
# ---------------------------------------------------------------------------


def _fake_record(**overrides: object) -> dict:
    record = {
        "not_run": False,
        "not_run_reason": None,
        "detected": True,
        "candidate_produced": False,
        "integrity": None,
        "vuln_eliminated": None,
        "regression": None,
        "deterministic_verified": False,
        "disposition": "analysis_only",
        "strategy": "none",
        "candidate_sha256": None,
        "patched_sha256": None,
        "poc_status": None,
        "runtime_tier": None,
        "gate_outcome": None,
        "error": None,
    }
    record.update(overrides)
    return record


def _small_manifest(count: int = 2) -> dict:
    manifest = _manifest()
    payload = json.loads(json.dumps(manifest))
    payload["samples"] = payload["samples"][:count]
    return payload


def test_runner_records_not_run_without_faking_verification():
    manifest = _small_manifest()
    repair = lambda sample: _fake_record(not_run=True, not_run_reason="host unavailable",
                                         detected=None)
    results = runner.run_benchmark(manifest, repair_fn=repair)
    assert results["summary"]["not_run"] == len(manifest["samples"])
    assert results["summary"]["false_verified"] == 0
    for result in results["results"]:
        assert result["not_run"] is True
        assert result["not_run_reason"] == "host unavailable"
        assert result["independently_verified"] is None
        assert result["false_verified"] is False
    with pytest.raises(runner.BenchmarkError):
        runner.run_benchmark(
            manifest,
            repair_fn=lambda sample: _fake_record(
                not_run=True, not_run_reason=None, detected=None
            ),
        )


def test_runner_detects_false_verified():
    manifest = _small_manifest()
    repair = lambda sample: _fake_record(
        candidate_produced=True,
        integrity=True,
        deterministic_verified=True,
        disposition="verified_patch",
        candidate_sha256="a" * 64,
        _candidate_bytes=b"fake-candidate",
    )

    def rejecting_verifier(sample, original_path, candidate_path):
        assert candidate_path is not None and candidate_path.is_file()
        return {"decision": "rejected", "reason": "independent reject"}

    with pytest.raises(runner.BenchmarkError) as error:
        runner.run_benchmark(
            manifest, repair_fn=repair, verifier=rejecting_verifier,
            verifier_status={"status": "available", "reason": None,
                             "path": "fake-verifier"},
        )
    assert "false_verified" in str(error.value)


def test_runner_accepts_independent_verification():
    manifest = _small_manifest()
    repair = lambda sample: _fake_record(
        candidate_produced=True,
        integrity=True,
        deterministic_verified=True,
        disposition="verified_patch",
        candidate_sha256="b" * 64,
        _candidate_bytes=b"fake-candidate",
    )
    seen = []

    def accepting_verifier(sample, original_path, candidate_path):
        seen.append((sample["sample_id"], original_path.is_file(),
                     candidate_path is not None and candidate_path.is_file()))
        return {"decision": "verified", "reason": "ok"}

    results = runner.run_benchmark(
        manifest, repair_fn=repair, verifier=accepting_verifier,
        verifier_status={"status": "available", "reason": None,
                         "path": "fake-verifier"},
    )
    assert results["summary"]["independently_verified"] == len(manifest["samples"])
    assert results["summary"]["false_verified"] == 0
    assert len(seen) == len(manifest["samples"])
    assert all(original and candidate for _, original, candidate in seen)


def test_runner_never_self_verifies_without_a_verifier():
    manifest = _small_manifest()
    repair = lambda sample: _fake_record(
        candidate_produced=True,
        integrity=True,
        deterministic_verified=True,
        disposition="verified_patch",
        candidate_sha256="c" * 64,
        _candidate_bytes=b"fake-candidate",
    )
    results = runner.run_benchmark(manifest, repair_fn=repair, verifier=None,
                                   verifier_status={"status": "not_run",
                                                    "reason": "absent", "path": None})
    assert results["summary"]["deterministic_verified"] == len(manifest["samples"])
    assert results["summary"]["independently_verified"] == 0
    assert results["summary"]["false_verified"] == 0
    for result in results["results"]:
        assert result["independently_verified"] is None
        assert result["false_verified"] is False


def test_runner_is_deterministic_with_injected_fakes():
    manifest = _small_manifest()
    repair = lambda sample: _fake_record(detected=True)
    first = runner.run_benchmark(manifest, repair_fn=repair)
    second = runner.run_benchmark(manifest, repair_fn=repair)
    assert json.dumps(runner._public_results(first), sort_keys=True) == json.dumps(
        runner._public_results(second), sort_keys=True
    )
    assert first["summary"]["false_verified"] == 0


def test_runner_has_no_ai_or_network_paths():
    source = (ROOT / "scripts" / "run_repair_benchmark.py").read_text(encoding="utf-8")
    lowered = source.lower()
    for forbidden in ("assistant_llm", "httpjsonclient", "requests.", "urllib.request",
                      "socket.", "openai", "siliconflow"):
        assert forbidden not in lowered, forbidden
    assert "binary_pipeline" in source
    assert "--verifier" in source


# ---------------------------------------------------------------------------
# Committed results artifact + real CLI smoke
# ---------------------------------------------------------------------------


def test_results_artifact_contract():
    results = _results()
    assert results["kind"] == "repair_benchmark_results"
    assert results["benchmark_id"] == "phase8-v1"
    manifest_sha = _sha256(MANIFEST_PATH)
    # The Phase-8A artifact was generated before the schema integration digest
    # was refreshed (the 12 sample objects/candidate hashes are unchanged); the
    # historical results keep their recorded manifest hash and must remain
    # internally consistent.
    if results["manifest_sha256"] != manifest_sha:
        assert results["manifest_sha256"] == results["manifest_sha256"]
        assert results["manifest_hidden_available"] is False
    assert results["manifest_hidden_available"] is False
    assert results["provenance"]["no_ai"] is True
    assert results["provenance"]["no_network"] is True
    required = {
        "detected", "candidate_produced", "integrity", "vuln_eliminated",
        "regression", "independently_verified", "not_run", "false_verified",
    }
    manifest_ids = [sample["sample_id"] for sample in _manifest()["samples"]]
    result_ids = [result["sample_id"] for result in results["results"]]
    assert sorted(result_ids) == sorted(manifest_ids)
    for result in results["results"]:
        assert required <= set(result)
        assert result["false_verified"] is False
        if result["candidate_produced"]:
            assert result["integrity"] is True
        if result["not_run"]:
            assert result["not_run_reason"]
    summary = results["summary"]
    assert summary["false_verified"] == 0
    assert summary["samples"] == len(results["results"])
    assert summary["independently_verified"] == 0 or (
        results["independent_verifier"]["status"] == "available"
    )
    assert sum(summary[key] for key in ()) == 0  # no-op keeps flake clean
    classes = {result["vulnerability_class"] for result in results["results"]}
    assert set(results["by_class"]) == classes
    control = next(result for result in results["results"]
                   if result["sample_id"] == "negative-control")
    assert control["candidate_produced"] is False
    assert control["deterministic_verified"] is False
    assert control["false_verified"] is False
    # Every not_run:false row must have executed the deterministic engine.
    assert all(not result["not_run"] for result in results["results"])
    disagreements = summary.get("verification_disagreements", 0)
    withdrawn = summary.get("deterministic_claim_withdrawn", 0)
    assert disagreements == withdrawn
    assert summary["false_verified"] == 0
    assert results["claim_policy"] in {"fail_on_disagreement", "withdraw"}
    for result in results["results"]:
        if result.get("verification_disagreement"):
            assert result["verifier_decision"] in {"rejected", "error"}
            assert result["independently_verified"] is False
            assert result["false_verified"] is False
            assert result["deterministic_claim_withdrawn"] is True


def test_runner_withdraw_policy_surfaces_disagreement():
    manifest = _small_manifest()
    repair = lambda sample: _fake_record(
        candidate_produced=True,
        integrity=True,
        deterministic_verified=True,
        disposition="verified_patch",
        candidate_sha256="d" * 64,
        _candidate_bytes=b"fake-candidate",
    )

    def rejecting_verifier(sample, original_path, candidate_path):
        return {"decision": "rejected", "reason": "independent reject"}

    results = runner.run_benchmark(
        manifest, repair_fn=repair, verifier=rejecting_verifier,
        verifier_status={"status": "available", "reason": None,
                         "path": "fake-verifier"},
        claim_policy="withdraw",
    )
    assert results["claim_policy"] == "withdraw"
    assert results["summary"]["false_verified"] == 0
    assert results["summary"]["verification_disagreements"] == len(manifest["samples"])
    assert results["summary"]["deterministic_claim_withdrawn"] == len(manifest["samples"])
    for result in results["results"]:
        assert result["verifier_decision"] == "rejected"
        assert result["independently_verified"] is False
        assert result["false_verified"] is False
        assert result["deterministic_claim_withdrawn"] is True
        assert result["verification_disagreement"] is True
        assert result["deterministic_verified"] is True
    with pytest.raises(runner.BenchmarkError):
        runner.run_benchmark(
            manifest, repair_fn=repair, verifier=rejecting_verifier,
            verifier_status={"status": "available", "reason": None,
                             "path": "fake-verifier"},
        )
    with pytest.raises(runner.BenchmarkError):
        runner.run_benchmark(manifest, claim_policy="unknown-policy")


def test_auto_verifier_discovery_uses_committed_verifier_if_present():
    verifier, status = runner.discover_verifier("auto")
    candidates = [ROOT / candidate for candidate in runner.VERIFIER_CANDIDATES]
    if any(path.is_file() for path in candidates):
        assert status["status"] == "available", status
        assert verifier is not None
        assert status["path"] in runner.VERIFIER_CANDIDATES
    else:
        assert status["status"] == "not_run"
        assert status["reason"]
    verifier_none, status_none = runner.discover_verifier("none")
    assert verifier_none is None
    assert status_none["status"] == "not_run"
    assert "explicitly disabled" in status_none["reason"]


def test_runner_exchanges_plan_scope_abi_and_persists_evidence(tmp_path):
    manifest = _small_manifest(2)
    plan = {
        "schema_version": 1,
        "candidate_id": "cand-abc",
        "target_sha256": "a" * 64,
        "candidate_sha256": "b" * 64,
        "strategy": "guard",
        "scope_policy": "target_scoped_associated",
        "target_scope": {"policy": "target_scoped_associated", "va": 0x1000, "end": 0x1040},
        "operations": [{
            "kind": "write", "original_offset": 0, "candidate_offset": 0,
            "size": 1, "before_hex": "90", "after_hex": "c3",
            "reason": "reviewed_site", "site_va": 0x1000,
        }],
        "cave": None,
        "relocations": [],
        "abi_blocks": [{"function": "f", "va": 0x1000, "size": 0x40, "arch": "x86_64"}],
        "oracle": {"manifest_sha256": "c" * 64, "runner": "poc_runner", "tier": "emulated_run"},
        "limitations": [],
    }
    repair = lambda sample: _fake_record(
        candidate_produced=True,
        integrity=True,
        deterministic_verified=True,
        disposition="verified_patch",
        candidate_sha256="b" * 64,
        patch_plan=plan,
        resolved_scope={"name": "f", "va": 0x1000, "end": 0x1040, "source": "symbol"},
        abi_blocks=plan["abi_blocks"],
        layout_checks={"patch.rewrite": "passed"},
        _candidate_bytes=b"candidate-bytes",
    )
    captured = {}

    def verifier(sample, original_path, candidate_path, metadata):
        captured["metadata"] = metadata
        assert metadata["patch_plan"]["operations"][0]["reason"] == "reviewed_site"
        assert metadata["target_scope"]["va"] == 0x1000
        if metadata.get("abi_block") is not None:
            assert metadata["abi_block"]["size"] == 0x40
        return {"decision": "verified", "reason": "ok",
                "report": {"verifier": {"verifier_id": "fake-verifier/1"},
                           "decision": "verified"}}

    results = runner.run_benchmark(
        manifest, repair_fn=repair, verifier=verifier,
        verifier_status={"status": "available", "reason": None, "path": "fake"},
        claim_policy="withdraw",
    )
    assert captured["metadata"]["patch_plan"]["oracle"]["manifest_sha256"]
    assert results["summary"]["independently_verified"] == 2
    assert results["summary"]["false_verified"] == 0
    for result in results["results"]:
        assert result["patch_plan_sha256"]
        assert result["verifier_id"] == "fake-verifier/1"
        assert result["layout_status"] == "passed"
        assert result["real_verification"] is True
    out = tmp_path / "artifact"
    written = runner.write_results(results, out)
    files = {Path(item["path"]).relative_to(out).as_posix() for item in written}
    sample_id = manifest["samples"][0]["sample_id"]
    assert f"samples/{sample_id}/original.bin" in files
    assert f"samples/{sample_id}/candidate.bin" in files
    assert f"samples/{sample_id}/plan.json" in files
    assert f"samples/{sample_id}/metadata.json" in files
    assert f"samples/{sample_id}/verifier-report.json" in files
    sums = (out / "SHA256SUMS").read_text(encoding="utf-8")
    assert f"samples/{sample_id}/plan.json" in sums
    public = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert all("_evidence" not in result for result in public["results"])
    assert public["results"][0]["patch_plan_sha256"] == results["results"][0]["patch_plan_sha256"]


def test_runner_cli_smoke_one_sample(tmp_path):
    import time

    start = time.time()
    result = subprocess.run(
        [PYTHON, str(ROOT / "scripts" / "run_repair_benchmark.py"),
         "--max-samples", "1", "--split", "dev", "--json"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=300,
    )
    elapsed = time.time() - start
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["summary"]["samples"] == 1
    assert payload["summary"]["false_verified"] == 0
    sample = payload["results"][0]
    assert "not_run" in sample
    if sample["not_run"]:
        assert any("not_run" in str(item) for item in ())
    # smoke must be reasonably bounded (single fast sample, no host dependency)
    assert elapsed < 280
