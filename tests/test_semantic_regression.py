"""Phase-8C C10: semantic regression evidence tests (fake oracle only)."""
from __future__ import annotations

import hashlib
import json

import pytest

from app.services import semantic_regression


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _valid_manifest(original: bytes) -> dict:
    """Minimal PoC manifest accepted by poc_runner.load_manifest."""

    return {
        "schema_version": 1,
        "fixture_sha256": _sha(original),
        "format": "elf",
        "arch": "x86_64",
        "target": "main",
        "poc": [{"id": "p1", "argv": []}],
        "regression": [{"id": "r1", "argv": []}],
    }


def _case(case_id: str, executable: str, *, exit_code: int = 0,
          crashed: bool = False, stdout: str = "", stderr: str = "",
          timed_out: bool = False, errno_value: int | None = None) -> dict:
    return {
        "case_id": case_id,
        "kind": "regression",
        "executable": executable,
        "exit_code": exit_code,
        "crashed": crashed,
        "stdout": stdout,
        "stderr": stderr,
        "stdout_hex": stdout.encode("utf-8").hex(),
        "timed_out": timed_out,
        "errno_value": errno_value,
        "syscall_errors": [],
    }


def _evidence(*, status: str = "pass", regression: list[dict] | None = None,
              poc: list[dict] | None = None, no_input: bool = False,
              limitations: list[str] | None = None) -> dict:
    return {
        "status": status,
        "runner": "limactl",
        "tier": "emulated_run",
        "stdout_signature": "matched",
        "no_input": no_input,
        "poc": list(poc or []),
        "regression": list(regression or []),
        "limitations": list(limitations or []),
    }


def test_pass_evidence_is_accepted_and_bounded():
    evidence = _evidence(regression=[
        _case("r1", "original", stdout="hi\n"),
        _case("r1", "candidate", stdout="hi\n"),
    ])
    result = semantic_regression.evaluate_evidence(evidence, expected_regression_ids=["r1"])
    assert result.status == "pass"
    assert result.decision == "accepted"
    assert result.regression is True
    assert result.cases[0]["matched"] is True
    assert semantic_regression.BOUNDED_LIMITATION in result.limitations
    summary = result.public_summary()
    assert summary["case_ids"] == ["r1"]
    # Never a full semantic-equivalence claim.
    assert "full semantic-equivalence" in " ".join(result.limitations)


def test_candidate_stdout_regression_is_rejected():
    evidence = _evidence(regression=[
        _case("r1", "original", stdout="hi\n"),
        _case("r1", "candidate", stdout="HI\n"),
    ])
    result = semantic_regression.evaluate_evidence(evidence)
    assert result.status == "fail"
    assert result.decision == "rejected"
    assert result.regression is False
    assert any("stdout changed" in item for item in result.cases[0]["mismatches"])


def test_candidate_crash_and_exit_regression_are_rejected():
    evidence = _evidence(regression=[
        _case("r1", "original", exit_code=0),
        _case("r1", "candidate", exit_code=-6, crashed=True),
        _case("r2", "original", exit_code=0),
        _case("r2", "candidate", exit_code=1),
    ])
    result = semantic_regression.evaluate_evidence(evidence)
    assert result.decision == "rejected"
    mismatches = [item for case in result.cases for item in case["mismatches"]]
    assert any("candidate crashed" in item for item in mismatches)
    assert any("exit_code" in item for item in mismatches)


def test_failed_poc_differential_is_rejected():
    evidence = _evidence(
        status="fail", poc=[_case("p1", "original", exit_code=0)],
        limitations=["candidate still crashes on the PoC case"],
    )
    result = semantic_regression.evaluate_evidence(evidence)
    assert result.status == "fail"
    assert result.decision == "rejected"
    assert "did not pass" in " ".join(result.limitations)


def test_unavailable_oracle_is_not_run_never_pass():
    evidence = _evidence(status="unavailable", limitations=[
        "Lima guest lock unavailable: blocked",
    ])
    result = semantic_regression.evaluate_evidence(evidence)
    assert result.status == "not_run"
    assert result.decision == "not_run"
    assert result.regression is None
    assert "oracle unavailable" in " ".join(result.limitations)


def test_missing_or_non_executable_evidence_is_not_run():
    for evidence in (None, {}, {"status": "not_run"}, {"status": "weird"}):
        result = semantic_regression.evaluate_evidence(evidence)
        assert result.decision == "not_run"
        assert result.regression is None
    result = semantic_regression.evaluate_evidence(
        _evidence(regression=[]), require_cases=True)
    assert result.decision == "not_run"
    assert "no declared regression cases" in " ".join(result.limitations)


def test_no_input_model_passes_without_regression_cases():
    result = semantic_regression.evaluate_evidence(
        _evidence(regression=[], no_input=True), require_cases=True)
    assert result.decision == "accepted"
    assert result.regression is None
    assert any("no-input" in item for item in result.limitations)


def test_unpaired_case_is_explicit_not_silently_dropped():
    evidence = _evidence(regression=[
        _case("r1", "original", stdout="hi\n"),
        _case("r2", "candidate", stdout="hi\n"),
    ])
    result = semantic_regression.evaluate_evidence(evidence)
    assert result.decision == "rejected"
    assert {case["case_id"] for case in result.cases} == {"r1", "r2"}
    assert any("missing candidate evidence" in " ".join(case["mismatches"])
               for case in result.cases)


def test_expected_case_ids_are_the_comparison_contract():
    evidence = _evidence(regression=[
        _case("r1", "original", stdout="a\n"),
        _case("r1", "candidate", stdout="a\n"),
        _case("r2", "original", stdout="x\n"),
        _case("r2", "candidate", stdout="x\n"),
    ])
    result = semantic_regression.evaluate_evidence(
        evidence, expected_regression_ids=["r1"])
    assert result.decision == "accepted"
    assert [case["case_id"] for case in result.cases] == ["r1"]


def test_hidden_public_summary_leaks_no_case_ids():
    evidence = _evidence(regression=[
        _case("private-case-id", "original", stdout="hi\n"),
        _case("private-case-id", "candidate", stdout="hi\n"),
    ])
    result = semantic_regression.evaluate_evidence(evidence, hidden=True)
    summary = result.public_summary(hidden=True)
    text = json.dumps(summary)
    assert "private-case-id" not in text
    assert "case_ids" not in summary
    assert summary["case_count"] == 1


def test_live_runner_pass_fail_and_unavailable(monkeypatch):
    manifest = _valid_manifest(b"orig")
    candidate = b"cand"

    class _Evidence:
        def __init__(self, payload: dict) -> None:
            self.payload = payload

        def to_dict(self) -> dict:
            return dict(self.payload)

    def runner_pass(_original, _candidate, _manifest):
        return _Evidence(_evidence(regression=[
            _case("r1", "original", stdout="hi\n"),
            _case("r1", "candidate", stdout="hi\n"),
        ]))

    result = semantic_regression.run_live(
        b"orig", candidate, manifest, run_poc=runner_pass)
    assert result.decision == "accepted"

    def runner_fail(_original, _candidate, _manifest):
        return _Evidence(_evidence(regression=[
            _case("r1", "original", stdout="hi\n"),
            _case("r1", "candidate", crashed=True),
        ]))

    assert semantic_regression.run_live(
        b"orig", candidate, manifest, run_poc=runner_fail).decision == "rejected"

    def runner_unavailable(_original, _candidate, _manifest):
        return _Evidence(_evidence(status="unavailable"))

    result = semantic_regression.run_live(
        b"orig", candidate, manifest, run_poc=runner_unavailable)
    assert result.decision == "not_run"

    # No candidate: never a pass.
    assert semantic_regression.run_live(
        b"orig", None, manifest, run_poc=runner_pass).decision == "not_run"


def test_live_runner_invalid_manifest_and_raising_runner():
    result = semantic_regression.run_live(
        b"orig", b"cand", {"not": "a poc manifest"})
    assert result.status == "invalid"
    assert result.decision == "not_run"

    def runner_boom(*_args, **_kwargs):
        raise RuntimeError("guest exploded")

    result = semantic_regression.run_live(
        b"orig", b"cand",
        _valid_manifest(b"orig"),
        run_poc=runner_boom,
    )
    assert result.decision == "not_run"
    assert "guest exploded" in " ".join(result.limitations)


def test_compare_case_is_field_exact():
    original = _case("r", "original", exit_code=0, stdout="x\n", stderr="e")
    candidate = _case("r", "candidate", exit_code=0, stdout="x\n", stderr="e")
    assert semantic_regression.compare_case(original, candidate) == []
    candidate["errno_value"] = 13
    assert any("errno" in item for item in
               semantic_regression.compare_case(original, candidate))
