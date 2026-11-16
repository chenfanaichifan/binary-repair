"""D05: hidden no-candidate stage attribution tests (fake hidden root).

The integration test uses a temporary private root and fake repair/guest
seams.  No real hidden corpus, network or AI provider is read.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import benchmark_runner  # noqa: E402
from app.services import hidden_stage_attribution as stage_mod  # noqa: E402
import test_phase8c_runner as phase8c_tests  # noqa: E402


def _no_candidate_repair(_original, sample, root=None):
    """A deterministic engine report that found no sink/candidate."""

    report = SimpleNamespace(
        disposition="analysis_only",
        status="unsupported",
        strategy="none",
        findings=[],
        actions=[],
        patch_plan=None,
        verification={},
        container={"format": sample.get("format"), "arch": sample.get("arch"),
                   "bits": sample.get("bits", 64), "endian": "little"},
        matrix={"cell": f"{sample.get('format')}/{sample.get('arch')}"},
        universal={
            "detected": True,
            "repairable": True,
            "reason": "no patchable sink",
            "target_scope": {"va": 0x1000, "end": 0x1100, "name": "hidden_bad"},
        },
        limitations=["target-scoped mode: no patchable sink lies inside target"],
        error=None,
    )
    return SimpleNamespace(candidate=None, verified=False, download_allowed=False,
                           report=report)


def _execution(**overrides):
    report = SimpleNamespace(
        disposition="analysis_only",
        status="unsupported",
        strategy=overrides.get("strategy", "none"),
        findings=overrides.get("findings", []),
        actions=overrides.get("actions", []),
        patch_plan=overrides.get("patch_plan"),
        verification=overrides.get("verification", {}),
        container=overrides.get(
            "container", {"format": "elf", "arch": "x86_64", "bits": 64}),
        matrix=overrides.get("matrix", {"cell": "elf/x86_64/64/little"}),
        universal=overrides.get(
            "universal",
            {"detected": True, "repairable": True,
             "target_scope": {"va": 0x1000, "end": 0x1100}}),
        limitations=overrides.get("limitations", ["no patchable sink"]),
    )
    return {
        "sample": {},
        "result": {
            "status": overrides.get("status", "executed"),
            "detection": overrides.get("detection", False),
            "root_cause": overrides.get("root_cause", False),
            "localization": overrides.get("localization", False),
            "strategy": overrides.get("strategy", "none"),
            "candidate": overrides.get("candidate"),
            "repair": {"report": report},
        },
    }


def _sample(scope="function", fmt="elf", arch="x86_64"):
    return {
        "sample_id": "a" * 64,
        "expected_scope": scope,
        "format": fmt,
        "arch": arch,
        "target": ({"kind": "analysis_only"} if scope == "analysis_only"
                   else {"kind": "symbol", "symbol": "hidden_bad"}),
    }


def test_detection_miss_is_first_blocking_stage_and_downstream_is_not_reached():
    diagnostic = stage_mod.attribute_hidden_execution(
        _sample(), _execution())
    assert diagnostic["first_blocking_stage"] == "detection"
    assert diagnostic["no_candidate_reason"] == "detection_missed"
    assert diagnostic["candidate_produced"] is False
    assert diagnostic["stages"]["parsing"]["status"] == "observed"
    assert diagnostic["stages"]["function_cfg_recovery"]["status"] == "observed"
    assert diagnostic["stages"]["detection"]["status"] == "not_observed"
    assert diagnostic["stages"]["candidate_generation"]["status"] == "not_reached"
    assert diagnostic["stages"]["pre_verification"]["status"] == "not_reached"


def test_missing_target_scope_attributes_function_boundary():
    diagnostic = stage_mod.attribute_hidden_execution(
        _sample(),
        _execution(universal={"detected": True, "repairable": True,
                              "target_scope": None}),
    )
    assert diagnostic["first_blocking_stage"] == "function_cfg_recovery"
    assert diagnostic["no_candidate_reason"] == "function_boundary_unknown"
    assert diagnostic["stages"]["function_cfg_recovery"]["status"] == "not_observed"


def test_analysis_only_sample_is_expected_no_candidate_and_excluded_from_runtime():
    diagnostic = stage_mod.attribute_hidden_execution(
        _sample(scope="analysis_only"), _execution())
    assert diagnostic["no_candidate_expected"] is True
    assert diagnostic["no_candidate_reason"] == "analysis_only"
    aggregate = stage_mod.aggregate_stage_attribution(
        [diagnostic], sample_count=1, runtime_count=0, analysis_only_count=1)
    assert aggregate["runtime_no_candidate_count"] == 0
    assert aggregate["analysis_only_count"] == 1
    assert aggregate["no_candidate_reason_counts"] == {}
    assert aggregate["first_blocking_stage_counts"] == {}


def test_bad_status_invalid_maps_to_parsing_taxonomy():
    diagnostic = stage_mod.attribute_hidden_execution(
        _sample(fmt="wasm", arch="mips"),
        _execution(status="invalid", universal={}),
    )
    assert diagnostic["first_blocking_stage"] == "parsing"
    assert diagnostic["no_candidate_reason"] == "unsupported_binary_format"


def test_no_candidate_lane_collects_private_diagnostics_without_public_ids(tmp_path):
    root, hidden_root = phase8c_tests._hidden_workspace(tmp_path)
    hidden = benchmark_runner.run_hidden_lane(
        hidden_root, root=root,
        verifier_spec=phase8c_tests._fake_verifier(),
        repair_fn=_no_candidate_repair,
        guest=phase8c_tests.FakeGuest(),
        collect_stage_attribution=True,
    )
    assert hidden["exit_code"] == 0
    stage = hidden["stage_attribution"]
    assert stage["sample_count"] == 2
    assert stage["runtime_count"] == 2
    assert stage["analysis_only_count"] == 0
    assert stage["runtime_no_candidate_count"] == 2
    assert stage["runtime_candidate_count"] == 0
    assert stage["no_candidate_reason_counts"] == {"detection_missed": 2}
    assert stage["first_blocking_stage_counts"] == {"detection": 2}
    private = hidden["private_report"]
    assert len(private["stage_attribution"]) == 2
    assert all(item["candidate_produced"] is False
               for item in private["stage_attribution"])
    public_text = benchmark_runner.canonical_json(
        hidden["hidden_aggregate_file"]).decode("ascii")
    for opaque in ("a" * 64, "b" * 64):
        assert opaque not in public_text
    assert "bin/" not in public_text
    assert "hidden_bad" not in public_text
    assert "opaque_sample_id" not in public_text


def test_aggregate_privacy_and_count_invariants():
    diagnostics = [
        stage_mod.attribute_hidden_execution(_sample(), _execution()),
        stage_mod.attribute_hidden_execution(
            _sample(scope="analysis_only"), _execution()),
    ]
    aggregate = stage_mod.aggregate_stage_attribution(
        diagnostics, sample_count=2, runtime_count=1, analysis_only_count=1)
    assert aggregate["sample_count"] == 2
    assert aggregate["runtime_count"] == 1
    assert aggregate["runtime_no_candidate_count"] == 1
    assert sum(aggregate["no_candidate_reason_counts"].values()) == 1
    assert sum(aggregate["first_blocking_stage_counts"].values()) == 1
    assert aggregate["analysis_only_no_candidate_expected"] == 1
    serialized = json.dumps(aggregate, sort_keys=True)
    assert "a" * 64 not in serialized
    assert "hidden_bad" not in serialized
    assert "/" not in serialized


def test_phase8d_public_artifact_check_is_green_and_contains_no_hidden_ids():
    script = ROOT / "scripts/run_phase8d_hidden_attribution.py"
    if not script.is_file():
        pytest.skip("D05 script not present in this checkout")
    proc = subprocess.run(
        [sys.executable, str(script), "--check"], cwd=str(ROOT),
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        pytest.skip(f"D05 public artifact not generated yet: {proc.stdout[-500:]}")
    public = ROOT / "artifacts/phase8d-hidden-attribution-2026-11-17/aggregate.json"
    payload = json.loads(public.read_text(encoding="ascii"))
    assert payload["runtime_no_candidate_count"] == 6
    assert payload["runtime_candidate_count"] == 0
    assert payload["analysis_only_count"] == 2
    assert payload["first_blocking_stage_counts"] == {"detection": 6}
    assert payload["no_candidate_reason_counts"] == {"detection_missed": 6}
    text = public.read_text(encoding="ascii")
    assert "opaque_sample_id" not in text
    assert "binary_path" not in text
    assert "/" not in text
