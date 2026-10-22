"""Overall-result honesty tests (P1 acceptance: no misread as success)."""

from __future__ import annotations

from app.status import overall_result


def _snapshot(phase: str = "finished", cancelled: bool = False, a=None, b=None):
    return {
        "phase": phase,
        "cancelled": cancelled,
        "routes": {"A": {"outcome": a}, "B": {"outcome": b}},
    }


def test_unfinished_job_has_no_verdict():
    assert overall_result(_snapshot(phase="validating", a=None, b=None))["key"] == "none"


def test_success_requires_both_routes_within_scope():
    result = overall_result(_snapshot(a="success_within_scope", b="success_within_scope"))
    assert result["key"] == "success_within_scope"
    assert "成功" in result["label_zh"]


def test_one_success_and_one_missing_is_not_success():
    result = overall_result(_snapshot(a="success_within_scope", b=None))
    assert result["key"] == "rejected"
    assert "未达成" in result["label_zh"]


def test_rejected_and_inconclusive_are_not_success():
    for outcome in ("rejected", "inconclusive", "unsupported"):
        result = overall_result(_snapshot(a=outcome, b="success_within_scope"))
        assert result["key"] == "rejected"
        assert "未达成" in result["label_zh"]


def test_cancelled_is_shown_as_cancelled_not_failure_or_success():
    result = overall_result(_snapshot(phase="validating", cancelled=True, a="cancelled", b=None))
    assert result["key"] == "cancelled"
    assert result["label_zh"] == "已取消"


def test_error_is_shown_as_failure():
    result = overall_result(_snapshot(a="error", b="success_within_scope"))
    assert result["key"] == "error"
    assert "失败" in result["label_zh"]
