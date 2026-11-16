"""Hard-case benchmark harness: baseline must fail, reference fix must gate."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINUX_X64 = sys.platform.startswith("linux") and __import__("platform").machine() in {"x86_64", "amd64"}


def test_hard_cases_are_well_formed_and_baseline_fails():
    cases = json.loads((ROOT / "fixtures" / "hard-cases" / "cases.json").read_text())
    assert len(cases["cases"]) >= 2
    for case in cases["cases"]:
        assert (ROOT / case["binary"]).is_file()
        assert (ROOT / case["poc"]).is_file()
        assert (ROOT / case["reference_fix"]).is_file()
        if case.get("reference_fix_asm"):
            assert (ROOT / case["reference_fix_asm"]).is_file()
        assert case["baseline_expected"] in {"analysis_only", "rejected", "unsupported"}
        # Target-strict baseline bookkeeping (contract T1): the field records the
        # deterministic repair_any(target=...) expectation and never rewrites
        # the historical whole-image baseline_expected.
        strict_expected = case.get("baseline_expected_target_strict")
        if strict_expected is not None:
            assert strict_expected in {"analysis_only", "rejected", "unsupported"}
            assert strict_expected != case["baseline_expected"]




def test_cwe121_declares_failure_contract_and_reference_assembly():
    from scripts.run_hard_benchmark import (
        _poc_failure_contract, _poc_spec,
    )
    cases = json.loads((ROOT / "fixtures" / "hard-cases" / "cases.json").read_text())
    case = next(item for item in cases["cases"]
                if item["id"] == "cwe121-unchecked-strcpy")
    assert case["reference_fix_asm"].endswith(".S")
    contract = _poc_failure_contract(_poc_spec(case))
    assert contract == {
        "exit_code": 1,
        "stdout": "",
        "stderr": "ERROR: input exceeds destination capacity\n",
    }


@pytest.mark.skipif(not LINUX_X64, reason="native PoC gate requires Linux x86-64")
def test_reference_assembly_case_passes_native_poc_gate(tmp_path: Path):
    out = tmp_path / "bench"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_hard_benchmark.py"),
         "--out", str(out), "--client", "reference", "--case", "inline-byte-loop"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads((out / "summary.json").read_text())
    assert summary["baseline_verified"] == 0
    assert summary["ai_verified"] == 1
    assert summary["ai_increment"] == 1
    # Target-strict deterministic baseline is recorded next to the whole-image
    # baseline: the target resolves, no action is produced outside it.
    case = next(
        item for item in json.loads(
            (ROOT / "fixtures" / "hard-cases" / "cases.json").read_text()
        )["cases"]
        if item["id"] == "inline-byte-loop"
    )
    record = summary["cases"][0]
    strict = record["baseline_target_strict"]
    assert strict["attempted"] is True
    assert strict["target_scope"]["name"] == case["target"]
    assert strict["disposition"] == case["baseline_expected_target_strict"]
    assert strict["actions"] == []
    assert strict["target_in_scope"] is False
