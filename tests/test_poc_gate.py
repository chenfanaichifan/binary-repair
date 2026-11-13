"""PoC-style differential predicate is a required part of the deterministic gate."""
from __future__ import annotations

import hashlib
from pathlib import Path

from app.services.binary_pipeline import repair_any
from app.services.runtime.evidence import RuntimeCase, RuntimeEvidence
from app.services.unified_verification import build

ROOT = Path(__file__).resolve().parents[1]
PE = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"


def _runtime(verdict: str = "pass") -> RuntimeEvidence:
    return RuntimeEvidence(
        tier="emulated_run", engine="unicorn-test", verdict=verdict,
        cases=[RuntimeCase(input_len=64, canary_intact=(verdict == "pass"))],
    )


def _poc(original_verdict: str = "fail", candidate_verdict: str = "pass") -> dict:
    return {
        "kind": "capacity_overflow_differential",
        "inputs": [16, 64],
        "original_verdict": original_verdict,
        "candidate_verdict": candidate_verdict,
        "original_cases": [{"input_len": 64, "canary_intact": False}],
        "candidate_cases": [{"input_len": 64, "canary_intact": True}],
    }


def _build(*, runtime=None, poc=None):
    original = b"orig"
    candidate = b"cand"
    return build(
        format_name="pe", arch="x86_64", original=original, candidate=candidate,
        actions=[{"kind": "guard"}], runtime=runtime if runtime is not None else _runtime(),
        reparse_ok=True,
        original_sha256=hashlib.sha256(original).hexdigest(),
        patched_sha256=hashlib.sha256(candidate).hexdigest(),
        poc=poc,
    )


def test_poc_differential_is_required_when_provided():
    verification = _build(poc=_poc())
    assert verification.gate.success is True
    ids = {check["id"] for check in verification.packet["checks"]}
    assert "poc.original_fails" in ids
    assert "poc.candidate_passes" in ids
    assert verification.packet["poc"]["original_verdict"] == "fail"


def test_poc_fails_when_original_does_not_fail():
    verification = _build(poc=_poc(original_verdict="pass"))
    assert verification.gate.success is False
    assert verification.gate.outcome == "rejected"
    assert verification.gate.reason.startswith("original_verdict=pass")


def test_poc_fails_when_candidate_does_not_pass():
    verification = _build(poc=_poc(candidate_verdict="fail"))
    assert verification.gate.success is False


def test_repair_report_contains_poc_differential():
    data = PE.read_bytes()
    outcome = repair_any(data)
    assert outcome.verified is True
    packet = outcome.report.verification["packet"]
    assert packet["poc"]["original_verdict"] == "fail"
    assert packet["poc"]["candidate_verdict"] == "pass"
    ids = {check["id"] for check in packet["checks"]}
    assert {"poc.original_fails", "poc.candidate_passes"} <= ids
