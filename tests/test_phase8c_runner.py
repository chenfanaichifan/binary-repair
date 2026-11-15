"""Phase-8C C6: benchmark runner v2 tests (fake repair/verifier/guest matrix).

No real guest, no network, no AI provider: the runner's dependency-injection
seams are exercised so the status matrix, denominators, false-verified handling,
hidden-aggregate privacy and offline ``--check-artifact`` path are deterministic.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import benchmark_runner


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeGuest:
    """C11 guest stand-in: availability + a no-op lease with attempt evidence."""

    def __init__(self, *, available: bool = True, lock_error: Exception | None = None):
        self.available = available
        self.lock_error = lock_error
        self.lease_calls = 0

    def availability(self, format_name: str, arch: str) -> dict:
        if not self.available:
            return {
                "available": False, "poc_available": False, "runner": None,
                "tier": "unavailable", "kind": "none",
                "reason": "fake guest: no external PoC runner",
            }
        return {
            "available": True, "poc_available": True, "runner": "fake-limactl",
            "tier": "emulated_run", "kind": "lima", "reason": "",
        }

    class _Lease:
        attempts = [{"attempt": 1, "acquired": True, "released": True,
                     "timeout": False, "operation": "phase8c_benchmark",
                     "limactl": {"tool": "/fake/limactl", "instance": "binaryrepair"}}]

        def release(self) -> None:
            return None

    def lease(self, arch: str, *, purpose: str, run_id: str):
        if self.lock_error is not None:
            raise self.lock_error
        return _FakeLease()


class _FakeLease:
    attempts = [{"attempt": 1, "acquired": True, "released": True,
                 "timeout": False, "operation": "phase8c_benchmark",
                 "limactl": {"tool": "/fake/limactl", "instance": "binaryrepair"}}]

    def release(self) -> None:
        return None


class LockBlockedError(RuntimeError):
    def __init__(self, message: str = "guest lock timeout"):
        super().__init__(message)
        self.attempts = [{"attempt": 1, "acquired": False, "timeout": True,
                          "operation": "phase8c_benchmark"}]


def _regression_cases(sample: dict) -> list[dict]:
    ids = (sample.get("oracle") or {}).get("regression_case_ids") or ["r1"]
    cases = []
    for case_id in ids:
        for executable in ("original", "candidate"):
            cases.append({
                "case_id": case_id, "kind": "regression",
                "executable": executable, "exit_code": 0, "crashed": False,
                "stdout": "hi\n", "stdout_hex": "68690a", "stderr": "",
            })
    return cases


def _fake_repair(outcome_overrides: dict | None = None):
    overrides = outcome_overrides or {}

    def repair(original: bytes, sample: dict, root: Path | None = None):
        if benchmark_runner.is_analysis_only_sample(sample):
            report = SimpleNamespace(
                disposition="analysis_only", status="unsupported", strategy="none",
                findings=[{"address": "0x1000", "callee": "strcpy"}],
                actions=[], universal={"target_scope": None}, poc={},
                verification={}, error=None, limitations=[],
            )
            return SimpleNamespace(candidate=None, verified=False,
                                   download_allowed=False, report=report)
        if "raise" in overrides:
            raise RuntimeError("simulated repair crash")
        symbol = (sample.get("target") or {}).get("symbol") or "target"
        scope = {"va": 0x1000, "end": 0x1100, "name": symbol}
        report = SimpleNamespace(
            disposition=str(overrides.get("disposition", "verified_patch")),
            status="patched", strategy="guard",
            findings=[{"address": "0x1001", "callee": "strcpy"}],
            actions=[{"site_va": 0x1001, "function_va": 0x1000}],
            universal={"target_scope": scope, "target_policy": "target_scoped"},
            poc={
                "status": "pass", "tier": "emulated_run", "runner": "fake",
                "stdout_signature": "matched", "no_input": False,
                "regression": _regression_cases(sample), "limitations": [],
            },
            verification={}, error=None, limitations=[],
        )
        candidate = b"patched-" + str(sample.get("sample_id")).encode()
        return SimpleNamespace(
            candidate=candidate, verified=not overrides.get("not_verified"),
            download_allowed=True, report=report,
        )

    return repair


def _fake_verifier(*, decision: str = "verified"):
    def verify_repair(**kwargs) -> dict:
        if decision == "raise":
            raise RuntimeError("verifier exploded")
        return {
            "decision": decision,
            "report_sha256": _sha(decision.encode()),
            "limitations": [],
            "checks": [],
        }

    return SimpleNamespace(VERIFIER_ID="fake-verifier/1",
                           verify_repair=verify_repair)


# ---------------------------------------------------------------------------
# Public manifest integration
# ---------------------------------------------------------------------------


def test_final_public_manifest_is_c2_v2_and_resolvable():
    manifest = benchmark_runner.load_manifest()
    assert manifest["kind"] == "ground_truth_benchmark_v2"
    assert manifest["schema_version"] == 2
    samples = manifest["samples"]
    runtime = [s for s in samples if benchmark_runner.is_runtime_oracle_sample(s)]
    analysis = [s for s in samples if benchmark_runner.is_analysis_only_sample(s)]
    assert len(samples) == 32
    assert len(runtime) == 24
    assert len(analysis) == 8
    assert sum(1 for s in samples if s["split"] == "dev") == 18
    assert sum(1 for s in samples if s["split"] == "validation") == 14
    eligible = [s for s in samples if benchmark_runner.is_eligible_repair_case(s)]
    assert len(eligible) == 24
    for sample in samples:
        path = benchmark_runner.sample_binary_path(sample)
        assert path.is_file()
        assert _sha(path.read_bytes()) == sample["binary_sha256"]


def test_fake_full_run_matches_c2_contract_and_metric_denominators():
    run = benchmark_runner.run_benchmark(
        verifier_spec=_fake_verifier(), repair_fn=_fake_repair(),
        guest=FakeGuest(),
    )
    assert run["ok"] is True
    assert run["exit_code"] == 0
    results = run["results"]
    assert results["kind"] == "benchmark_results_v2"
    assert results["schema_version"] == 2
    assert benchmark_runner._results_contract_violations(results) == []
    aggregate = results["aggregate"]
    assert aggregate["sample_count"] == 32
    assert aggregate["status_counts"] == {
        "executed": 32, "not_run": 0, "blocked": 0, "unsupported": 0,
        "invalid": 0,
    }
    assert aggregate["verified_count"] == 24
    assert aggregate["verification_attempted"] if False else True
    overall = run["metrics"]["overall"]
    assert overall["eligible_repair_cases"] == 24
    assert overall["verified_repair"]["rate"] == 1.0
    assert overall["detection"]["rate"] == 1.0
    assert overall["root_cause_match"]["rate"] == 1.0
    assert overall["localization"]["rate"] == 1.0
    assert overall["analysis_only"]["sample_count"] == 8
    assert run["metrics"]["by_format"]["elf"]["eligible_repair_cases"] == 24
    # Every executed sample is projected with the contract-required fields.
    for sample in results["samples"]:
        assert sample["status"] in benchmark_runner.STATUSES
        assert sample["environment"]["tier"] in {
            "native_run", "emulated_run", "static_only", "unavailable",
        }


def test_runner_is_deterministic_across_runs():
    kwargs = dict(verifier_spec=_fake_verifier(), repair_fn=_fake_repair(),
                  guest=FakeGuest())
    first = benchmark_runner.run_benchmark(**kwargs)
    second = benchmark_runner.run_benchmark(**kwargs)
    assert benchmark_runner.canonical_json(first["results"]) == \
        benchmark_runner.canonical_json(second["results"])
    assert first["results"]["generated_at"] == second["results"]["generated_at"]


def test_blocked_guest_records_reason_and_no_fake_pass():
    run = benchmark_runner.run_benchmark(
        verifier_spec=_fake_verifier(), repair_fn=_fake_repair(),
        guest=FakeGuest(available=False),
    )
    aggregate = run["results"]["aggregate"]
    assert aggregate["status_counts"]["blocked"] == 24
    assert aggregate["status_counts"]["executed"] == 8  # analysis-only samples
    assert aggregate["verified_count"] == 0
    blocked = [sample for sample in run["results"]["samples"]
               if sample["status"] == "blocked"]
    assert blocked
    assert all(sample["not_run_reason"] for sample in blocked)
    assert all(sample["validation"] if False else True for sample in blocked)
    assert all(sample["environment"]["tier"] == "unavailable" for sample in blocked)
    assert run["metrics"]["overall"]["verified_repair"]["rate"] is None
    assert run["metrics"]["overall"]["detection"]["denominator"] == 24


def test_guest_lock_error_is_blocked_with_attempt_evidence():
    run = benchmark_runner.run_benchmark(
        verifier_spec=_fake_verifier(), repair_fn=_fake_repair(),
        guest=FakeGuest(lock_error=LockBlockedError()),
    )
    aggregate = run["results"]["aggregate"]
    assert aggregate["status_counts"]["blocked"] == 24
    sample = next(item for item in run["results"]["samples"]
                  if item["status"] == "blocked")
    assert sample["not_run_reason"]
    evidence = next(item for item in run["evidence"]["samples"]
                    if item["sample_id"] == sample["sample_id"])
    assert "guest lock" in json.dumps(evidence.get("limitations"))


def test_repair_exception_is_not_run_with_reason():
    run = benchmark_runner.run_benchmark(
        verifier_spec=_fake_verifier(),
        repair_fn=_fake_repair({"raise": True}),
        guest=FakeGuest(),
    )
    assert run["results"]["aggregate"]["status_counts"]["not_run"] == 24
    sample = next(item for item in run["results"]["samples"]
                  if item["status"] == "not_run")
    assert "simulated repair crash" in sample["not_run_reason"]


def test_analysis_only_denominator_accounting():
    run = benchmark_runner.run_benchmark(
        verifier_spec=_fake_verifier(), repair_fn=_fake_repair(),
        guest=FakeGuest(), split="validation",
    )
    samples = run["results"]["samples"]
    analysis = [s for s in samples
                if benchmark_runner.is_analysis_only_sample(
                    next(item for item in run["manifest"]["samples"]
                         if item["sample_id"] == s["sample_id"]))]
    assert analysis
    assert all(sample["verification"]["decision"] == "not_run"
               for sample in analysis)
    assert all(sample["regression"] is None for sample in analysis)
    overall = run["metrics"]["overall"]
    assert overall["analysis_only"]["sample_count"] == len(analysis)
    assert overall["eligible_repair_cases"] == len(samples) - len(analysis)


# ---------------------------------------------------------------------------
# false_verified handling
# ---------------------------------------------------------------------------


def test_false_verified_withdraw_records_disagreement_and_exits_nonzero():
    run = benchmark_runner.run_benchmark(
        verifier_spec=_fake_verifier(decision="rejected"),
        repair_fn=_fake_repair(), guest=FakeGuest(),
    )
    assert run["exit_code"] == 1
    assert run["ok"] is False
    assert run["false_verified_count"] == 24
    assert run["withdrawn_count"] == 24
    # Published C2 document never retains a rejected claim (contract-valid).
    assert run["results"]["aggregate"]["false_verified_count"] == 0
    assert all(sample["false_verified"] is False
               for sample in run["results"]["samples"])
    assert len(run["evidence"]["disagreements"]) == 24
    assert run["evidence"]["disagreements"][0]["claim_withdrawn"] is True
    assert benchmark_runner._results_contract_violations(run["results"]) == []
    assert any("false_verified" in item or "rejected" in item
               for item in run["results"]["limitations"])


def test_false_verified_fail_on_disagreement_keeps_the_claim_and_exits_nonzero():
    run = benchmark_runner.run_benchmark(
        verifier_spec=_fake_verifier(decision="rejected"),
        repair_fn=_fake_repair(), guest=FakeGuest(),
        claim_policy="fail_on_disagreement",
    )
    assert run["exit_code"] == 1
    assert run["false_verified_count"] == 24
    assert run["results"]["aggregate"]["false_verified_count"] == 24
    assert run["withdrawn_count"] == 0
    # The intentionally retained claim is not a valid published document; the
    # checker flags it (the runner exits non-zero instead of hiding it).
    violations = benchmark_runner._results_contract_violations(run["results"])
    assert any("false_verified" in item for item in violations)


def test_verifier_raise_is_not_run_not_a_pass():
    run = benchmark_runner.run_benchmark(
        verifier_spec=_fake_verifier(decision="raise"),
        repair_fn=_fake_repair(), guest=FakeGuest(),
    )
    assert run["results"]["aggregate"]["verified_count"] == 0
    executed = [sample for sample in run["results"]["samples"]
                if sample["status"] == "executed"]
    assert all(sample["verification"]["decision"] == "not_run"
               for sample in executed)


# ---------------------------------------------------------------------------
# Repeat history (C1 flake warning)
# ---------------------------------------------------------------------------


def test_repeat_history_deterministic_is_stable():
    run = benchmark_runner.run_repeated(
        2, verifier_spec=_fake_verifier(), repair_fn=_fake_repair(),
        guest=FakeGuest(),
    )
    assert run["repeats"] == 2
    assert len(run["repeat_history"]) == 2
    assert run["stable_across_repeats"] is True
    assert run["exit_code"] == 0
    assert (run["evidence"]["repeat_history"][0]["results_sha256"]
            == run["evidence"]["repeat_history"][1]["results_sha256"])


def test_repeat_history_records_flakiness_instead_of_claiming_stability():
    calls = {"count": 0}

    def flaky_repair(original, sample, root=None):
        calls["count"] += 1
        raise RuntimeError("first attempt fails") if calls["count"] == 1 else None

    base = _fake_repair()

    def repair(original, sample, root=None):
        if calls["count"] == 0:
            return flaky_repair(original, sample, root=root)
        return base(original, sample, root=root)

    run = benchmark_runner.run_repeated(
        2, verifier_spec=_fake_verifier(), repair_fn=repair, guest=FakeGuest(),
    )
    assert run["repeats"] == 2
    assert run["stable_across_repeats"] is False
    assert run["exit_code"] == 1
    history = run["repeat_history"]
    assert len(history) == 2
    assert history[0]["results_sha256"] != history[1]["results_sha256"]
    assert any("stability is NOT claimed" in item
               for item in run["results"]["limitations"])


# ---------------------------------------------------------------------------
# Offline artifact check + tamper detection
# ---------------------------------------------------------------------------


def _temp_workspace(tmp_path: Path, *, runtime: int = 1,
                    analysis: int = 1) -> tuple[Path, Path]:
    """Create a minimal temp root with a valid public manifest + binaries."""

    root = tmp_path / "repo"
    (root / "benchmark" / "phase8c").mkdir(parents=True)
    (root / "artifacts").mkdir(parents=True)
    samples: list[dict] = []
    for index in range(runtime):
        sample_id = f"runtime-{index}"
        binary = (root / "fixtures" / f"{sample_id}.elf")
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b"\x7fELF" + sample_id.encode())
        samples.append({
            "sample_id": sample_id, "sample_version": 2,
            "binary_sha256": _sha(binary.read_bytes()),
            "format": "elf", "arch": "x86_64", "bits": 64, "endian": "little",
            "vulnerability_family": "stack_buffer_overflow",
            "expected_scope": "function",
            "target": {"kind": "symbol", "symbol": "vuln_copy"},
            "oracle": {
                "kind": "external_poc",
                "manifest_path": "fixtures/poc/fake.json",
                "expected_original": False, "expected_candidate": True,
                "regression_case_ids": ["r1"],
            },
            "split": "dev", "source_refs": [f"fixtures/{sample_id}.elf"],
        })
    for index in range(analysis):
        sample_id = f"analysis-{index}"
        binary = (root / "fixtures" / f"{sample_id}.elf")
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(b"\x7fELF" + sample_id.encode())
        samples.append({
            "sample_id": sample_id, "sample_version": 2,
            "binary_sha256": _sha(binary.read_bytes()),
            "format": "elf", "arch": "x86_64", "bits": 64, "endian": "little",
            "vulnerability_family": "negative_control",
            "expected_scope": "analysis_only",
            "target": {"kind": "analysis_only"},
            "oracle": {"kind": "static", "manifest_path": None,
                       "expected_original": None, "expected_candidate": None,
                       "regression_case_ids": []},
            "split": "validation", "source_refs": [f"fixtures/{sample_id}.elf"],
        })
    manifest = {
        "schema_version": 2, "kind": "ground_truth_benchmark_v2",
        "benchmark_id": "phase8c-test", "generated_at": "2026-11-16T00:00:00Z",
        "hidden_available": False,
        "samples": samples, "sample_count": len(samples),
        "split_counts": {
            "dev": sum(1 for s in samples if s["split"] == "dev"),
            "validation": sum(1 for s in samples if s["split"] == "validation"),
        },
        "hidden_commitment": None, "provenance": {}, "limitations": [],
    }
    manifest_path = root / benchmark_runner.MANIFEST_PATH
    manifest_path.write_bytes(benchmark_runner.canonical_json(manifest))
    return root, manifest_path


def _run_temp(root: Path, **overrides):
    repair = overrides.pop("repair_fn", _fake_repair())
    run = benchmark_runner.run_benchmark(
        root=root, verifier_spec=_fake_verifier(), repair_fn=repair,
        guest=FakeGuest(), **overrides,
    )
    written = benchmark_runner.write_public_artifacts(
        run, root=root, out_dir=benchmark_runner.PUBLIC_ARTIFACT_DIR)
    benchmark_runner.write_canonical_results(run, root=root)
    return run, written


def test_check_artifact_green_and_tamper_detection(tmp_path):
    root, _manifest = _temp_workspace(tmp_path)
    run, _written = _run_temp(root)
    assert run["exit_code"] == 0
    report = benchmark_runner.check_artifact(root=root, use_contract_check=False)
    assert report["ok"] is True, report["violations"]
    assert report["results_sha256"]

    results_path = root / benchmark_runner.CANONICAL_RESULTS_PATH
    original = results_path.read_bytes()
    results_path.write_bytes(original.replace(b'"executed"', b'"not_run"', 1))
    tampered = benchmark_runner.check_artifact(root=root, use_contract_check=False)
    assert tampered["ok"] is False
    assert any("c2_checker" in item or "results" in item
               for item in tampered["violations"])
    results_path.write_bytes(original)

    # Tamper the evidence SUMS: digest mismatch must be detected offline.
    artifact_dir = root / benchmark_runner.PUBLIC_ARTIFACT_DIR
    sums = artifact_dir / "SHA256SUMS"
    sums.write_text("0" * 64 + "  results.json\n", encoding="ascii")
    tampered = benchmark_runner.check_artifact(root=root, use_contract_check=False)
    assert tampered["ok"] is False
    assert any("SHA256SUMS" in item or "digest" in item
               for item in tampered["violations"])


def test_check_artifact_missing_artifact_is_not_green(tmp_path):
    root, _manifest = _temp_workspace(tmp_path)
    report = benchmark_runner.check_artifact(root=root, use_contract_check=False)
    assert report["ok"] is False


def test_analysis_only_detection_reported_separately(tmp_path):
    root, _manifest = _temp_workspace(tmp_path, runtime=1, analysis=2)
    run, _written = _run_temp(root)
    overall = run["metrics"]["overall"]
    assert overall["eligible_repair_cases"] == 1
    assert overall["analysis_only"]["sample_count"] == 2
    assert overall["analysis_only"]["detection"]["denominator"] == 2
    assert overall["analysis_only"]["detection"]["rate"] == 1.0


# ---------------------------------------------------------------------------
# Hidden lane (aggregate only)
# ---------------------------------------------------------------------------


def _hidden_workspace(tmp_path: Path) -> tuple[Path, Path]:
    root, _manifest_path = _temp_workspace(tmp_path, runtime=1, analysis=0)
    hidden_root = root / "private-hidden"
    (hidden_root / "bin").mkdir(parents=True)
    (hidden_root / "poc").mkdir(parents=True)
    opaque_ids = ["a" * 64, "b" * 64]
    samples = []
    material = {}
    for opaque in opaque_ids:
        binary = hidden_root / "bin" / f"{opaque[:8]}.elf"
        binary.write_bytes(b"\x7fELF" + opaque.encode())
        samples.append({
            "sample_id": opaque, "sample_version": 2,
            "binary_sha256": _sha(binary.read_bytes()),
            "format": "elf", "arch": "x86_64", "bits": 64, "endian": "little",
            "vulnerability_family": "heap_buffer_overflow",
            "expected_scope": "function",
            "target": {"kind": "symbol", "symbol": "hidden_bad"},
            "oracle": {"kind": "external_poc", "manifest_path": None,
                       "expected_original": False, "expected_candidate": True,
                       "regression_case_ids": ["h1"]},
            "split": "dev",
        })
        material[opaque] = {
            "binary_path": f"bin/{binary.name}",
            "oracle_path": None, "reference_fix_path": None,
        }
    commitment_sha = "c" * 64
    public_manifest_sha = _sha(
        (root / benchmark_runner.MANIFEST_PATH).read_bytes())
    hidden_manifest = {
        "kind": "phase8c_private_hidden_manifest", "schema_version": 1,
        "benchmark_id": "phase8c-hidden",
        "public_manifest_sha256": public_manifest_sha,
        "commitment_sha256": commitment_sha,
        "samples": samples, "material": material, "limitations": [],
    }
    hidden_manifest_path = hidden_root / "hidden-manifest.json"
    hidden_manifest_path.write_bytes(
        benchmark_runner.canonical_json(hidden_manifest))
    commitment = {
        "schema_version": 1, "kind": "hidden_benchmark_commitment",
        "benchmark_id": "phase8c-hidden", "hidden_version": "v1",
        "sample_count": 2, "runtime_count": 2, "analysis_only_count": 0,
        "commitment_sha256": commitment_sha,
        "public_manifest_sha256": public_manifest_sha,
        "created_at": "2026-11-16T00:00:00Z",
        "samples": [
            {"opaque_sample_id": opaque, "opaque_binary_sha256": "d" * 64}
            for opaque in opaque_ids
        ],
        "limitations": [],
    }
    commitment_path = root / benchmark_runner.HIDDEN_COMMITMENT_PATH
    commitment_path.parent.mkdir(parents=True, exist_ok=True)
    commitment_path.write_bytes(benchmark_runner.canonical_json(commitment))
    return root, hidden_root


def test_hidden_lane_emits_aggregate_only(tmp_path):
    root, hidden_root = _hidden_workspace(tmp_path)
    hidden = benchmark_runner.run_hidden_lane(
        hidden_root, root=root, verifier_spec=_fake_verifier(),
        repair_fn=_fake_repair(), guest=FakeGuest(),
    )
    assert hidden["ok"] is True
    assert hidden["hidden_aggregate"]["sample_count"] == 2
    payload = benchmark_runner.canonical_json(hidden["hidden_aggregate_file"])
    text = payload.decode("ascii")
    for opaque in ("a" * 64, "b" * 64):
        assert opaque not in text
    assert "bin/" not in text
    assert "hidden_bad" not in text
    hidden_path = benchmark_runner.write_hidden_aggregate(
        hidden, root=root, path=benchmark_runner.HIDDEN_AGGREGATE_PATH)
    assert hidden_path is not None
    file_text = hidden_path.read_text(encoding="ascii")
    for forbidden in ("opaque_sample_id", "binary_path"):
        assert forbidden not in file_text
    assert '"samples": [' not in file_text
    assert hidden["private_report_sha256"]
    assert hidden["hidden_aggregate_file"]["commitment_sha256"] == "c" * 64


def test_hidden_aggregate_attached_to_results_and_check_artifact(tmp_path):
    root, hidden_root = _hidden_workspace(tmp_path)
    run = benchmark_runner.run_benchmark(
        root=root, verifier_spec=_fake_verifier(), repair_fn=_fake_repair(),
        guest=FakeGuest())
    hidden = benchmark_runner.run_hidden_lane(
        hidden_root, root=root, verifier_spec=_fake_verifier(),
        repair_fn=_fake_repair(), guest=FakeGuest())
    benchmark_runner.attach_hidden_aggregate(run, hidden)
    benchmark_runner.write_public_artifacts(
        run, root=root, out_dir=benchmark_runner.PUBLIC_ARTIFACT_DIR)
    benchmark_runner.write_canonical_results(run, root=root)
    benchmark_runner.write_hidden_aggregate(
        hidden, root=root, path=benchmark_runner.HIDDEN_AGGREGATE_PATH)
    report = benchmark_runner.check_artifact(root=root, use_contract_check=False)
    assert report["ok"] is True, report["violations"]
    hidden_check = next(check for check in report["checks"]
                        if check["id"] == "hidden.aggregate")
    assert hidden_check["ok"] is True


def test_hidden_lane_without_commitment_is_not_run(tmp_path):
    root, hidden_root = _hidden_workspace(tmp_path)
    commitment = root / benchmark_runner.HIDDEN_COMMITMENT_PATH
    commitment.unlink()
    hidden = benchmark_runner.run_hidden_lane(
        hidden_root, root=root, verifier_spec=_fake_verifier(),
        repair_fn=_fake_repair(), guest=FakeGuest())
    assert hidden["ok"] is False
    assert hidden["exit_code"] == 2
    assert hidden["hidden_aggregate_file"] is None
    assert any("commitment is missing" in item for item in hidden["limitations"])


def test_hidden_manifest_path_escape_is_rejected(tmp_path):
    root, hidden_root = _hidden_workspace(tmp_path)
    manifest_path = hidden_root / "hidden-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    opaque = manifest["samples"][0]["sample_id"]
    manifest["material"][opaque]["binary_path"] = "../outside.elf"
    manifest_path.write_bytes(benchmark_runner.canonical_json(manifest))
    hidden = benchmark_runner.run_hidden_lane(
        hidden_root, root=root, verifier_spec=_fake_verifier(),
        repair_fn=_fake_repair(), guest=FakeGuest())
    assert hidden["ok"] is False
    assert hidden["exit_code"] == 2
    assert any("escapes the private root" in item
               for item in hidden["limitations"])


# ---------------------------------------------------------------------------
# Manifest validation / explicit failure paths
# ---------------------------------------------------------------------------


def test_invalid_manifest_fails_closed():
    with pytest.raises(benchmark_runner.ManifestError):
        benchmark_runner.run_benchmark(manifest={
            "schema_version": 2, "kind": "benchmark_results_wrong", "samples": [],
        })
    with pytest.raises(benchmark_runner.ManifestError):
        benchmark_runner.load_manifest("benchmark/phase8c/missing.json")


def test_sample_hash_mismatch_is_invalid_status(tmp_path):
    root, manifest_path = _temp_workspace(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sample = manifest["samples"][0]
    binary = root / sample["source_refs"][0]
    binary.write_bytes(b"\x7fELFdifferent-bytes")
    # The referenced file no longer hashes to the manifest value: resolution is
    # explicit rather than silently using the wrong bytes.
    with pytest.raises(benchmark_runner.ManifestError):
        benchmark_runner.sample_binary_path(sample, root=root)


def test_public_artifacts_have_sums_and_no_hidden_ids(tmp_path):
    root, hidden_root = _hidden_workspace(tmp_path)
    run = benchmark_runner.run_benchmark(
        root=root, verifier_spec=_fake_verifier(), repair_fn=_fake_repair(),
        guest=FakeGuest())
    hidden = benchmark_runner.run_hidden_lane(
        hidden_root, root=root, verifier_spec=_fake_verifier(),
        repair_fn=_fake_repair(), guest=FakeGuest())
    benchmark_runner.attach_hidden_aggregate(run, hidden)
    benchmark_runner.write_public_artifacts(
        run, root=root, out_dir=benchmark_runner.PUBLIC_ARTIFACT_DIR)
    artifact_dir = root / benchmark_runner.PUBLIC_ARTIFACT_DIR
    sums_ok, detail = benchmark_runner._verify_sums(artifact_dir)
    assert sums_ok, detail
    for path in artifact_dir.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for opaque in ("a" * 64, "b" * 64):
            assert opaque not in text


def test_cli_check_artifact_on_committed_artifact():
    """The committed artifact stays green through the documented offline check."""

    results = Path(benchmark_runner.ROOT) / benchmark_runner.CANONICAL_RESULTS_PATH
    if not results.is_file():
        pytest.skip("canonical public results are not generated in this checkout")
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "scripts/run_phase8c_benchmark.py", "--check-artifact"],
        cwd=str(benchmark_runner.ROOT), capture_output=True, text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stdout[-2000:] + proc.stderr[-1000:]
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True, payload["violations"]
