"""Native feedback classification; observed only, no invented trace fields."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.native_feedback import analyze_native_failure


def _case(executable="candidate", kind="poc", crashed=True, expected_ok=False,
          exit_code=255, stdout="", stderr="qemu: uncaught target signal 11"):
    return SimpleNamespace(case_id="c1", kind=kind, executable=executable,
                           exit_code=exit_code, crashed=crashed, timed_out=False,
                           stdout=stdout, stderr=stderr, expected_ok=expected_ok)


def test_candidate_crash_is_retryable_with_signal():
    ev = SimpleNamespace(status="fail", cases=[_case()], regression=[])
    feedback = analyze_native_failure(ev, case_id="hard-multicall")
    assert feedback is not None
    assert feedback.failure_class == "candidate_crash"
    assert feedback.retryable is True
    assert feedback.signal == 11
    payload = feedback.to_dict()
    assert "registers" not in payload
    assert "register_diff" not in payload


def test_timeout_not_retryable():
    case = _case(crashed=False, exit_code=None)
    case.timed_out = True
    feedback = analyze_native_failure(
        SimpleNamespace(status="fail", cases=[case], regression=[]), case_id="x")
    assert feedback is not None
    assert feedback.failure_class == "timeout"
    assert feedback.retryable is False


def test_regression_mismatch_is_retryable():
    reg = _case(kind="regression", crashed=False, expected_ok=False,
                exit_code=0, stdout="wrong")
    feedback = analyze_native_failure(
        SimpleNamespace(status="fail", cases=[], regression=[reg]), case_id="x")
    assert feedback is not None
    assert feedback.failure_class == "regression_mismatch"
    assert feedback.retryable is True


def test_pass_or_non_failure_returns_none():
    assert analyze_native_failure(SimpleNamespace(status="pass", cases=[], regression=[])) is None
    assert analyze_native_failure(
        SimpleNamespace(status="fail", cases=[], regression=[])) is None
