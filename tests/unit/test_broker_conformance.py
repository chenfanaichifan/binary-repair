"""Tests for the conformance matrix and its fail-closed verdict (VMer task-15).

The point of these tests is honesty: a missing case must never read as a pass,
an isolation gap must never read as a pass, and an absent attestation must be
``inconclusive`` rather than inferred.
"""

from __future__ import annotations

import pytest

from workers.broker.conformance import (
    CONFORMANCE_MATRIX,
    Attestation,
    CaseRecord,
    Evidence,
    WindowMeta,
    case_ids,
    evaluate,
)

SHA = "a" * 64

GOOD_ATT = {
    "uid": 1003,
    "gid": 1003,
    "cap_eff": "0",
    "no_new_privs": 1,
    "netns": "net:[4026532222]",
    "default_route": "",
    "rlimit_cpu": 600,
}


def _window(**over):
    base = dict(
        snapshot_uid=11,
        snapshot_name="gate4-harness",
        started_at="2026-11-05T00:00:00Z",
        finished_at="2026-11-05T00:05:00Z",
        executor_sha256=SHA,
        available_modes=("probe", "routea"),
    )
    base.update(over)
    return base


def _passing_cases():
    """Build a record set that should evaluate to pass."""
    out = []
    for case in CONFORMANCE_MATRIX:
        if case.kind == "positive":
            out.append({
                "id": case.id, "rc": case.expected_rc, "stderr": "",
                "attestation": GOOD_ATT,
            })
        else:
            out.append({
                "id": case.id, "rc": case.expected_rc,
                "stderr": f"jobwrap-gate5: {case.expected_stderr_contains}",
                "attestation": None,
            })
    return out


def _payload(cases):
    return {"schema_version": 1, "window": _window(), "cases": cases}


# ---- happy path -----------------------------------------------------------


def test_full_matching_matrix_passes():
    verdict = evaluate(_payload(_passing_cases()))
    assert verdict.state == "pass", verdict.reason
    assert verdict.missing == ()
    assert all(c.result == "pass" for c in verdict.cases)


def test_matrix_ids_are_unique():
    ids = case_ids()
    assert len(ids) == len(set(ids))


def test_matrix_has_both_kinds():
    kinds = {c.kind for c in CONFORMANCE_MATRIX}
    assert kinds == {"positive", "negative"}


# ---- fail-closed: missing evidence ---------------------------------------


def test_missing_case_is_not_run_not_pass():
    cases = _passing_cases()
    dropped = cases.pop()  # remove one required case
    verdict = evaluate(_payload(cases))
    assert verdict.state == "not_run"
    assert dropped["id"] in verdict.missing


def test_empty_cases_is_not_run():
    verdict = evaluate(_payload([]))
    assert verdict.state == "not_run"
    assert len(verdict.missing) == len(CONFORMANCE_MATRIX)


def test_malformed_payload_is_fail_not_pass():
    verdict = evaluate({"not": "evidence"})
    assert verdict.state == "fail"
    assert "schema validation" in verdict.reason


# ---- fail-closed: wrong behaviour -----------------------------------------


def test_wrong_exit_code_fails():
    cases = _passing_cases()
    cases[0]["rc"] = 99
    verdict = evaluate(_payload(cases))
    assert verdict.state == "fail"


def test_wrong_stderr_fails():
    cases = _passing_cases()
    negative = next(c for c in cases if c["rc"] == 2)
    negative["stderr"] = "Segmentation fault"
    verdict = evaluate(_payload(cases))
    assert verdict.state == "fail"


def test_missing_exit_code_fails():
    cases = _passing_cases()
    cases[0]["rc"] = None
    verdict = evaluate(_payload(cases))
    assert verdict.state == "fail"


# ---- fail-closed: isolation ----------------------------------------------


@pytest.mark.parametrize(
    "field,bad_value,why",
    [
        ("uid", 0, "ran as root"),
        ("gid", 0, "wrong group"),
        ("cap_eff", "00000000a80425fb", "capabilities retained"),
        ("no_new_privs", 0, "nnp not set"),
        ("default_route", "default via 192.168.30.1", "egress reachable"),
        ("netns", "", "netns unknown"),
    ],
)
def test_isolation_gap_fails(field, bad_value, why):
    cases = _passing_cases()
    att = dict(GOOD_ATT)
    att[field] = bad_value
    cases[0]["attestation"] = att
    verdict = evaluate(_payload(cases))
    assert verdict.state == "fail", f"{why} should fail, got {verdict.state}"


def test_absent_attestation_is_inconclusive_not_pass():
    cases = _passing_cases()
    cases[0]["attestation"] = None
    verdict = evaluate(_payload(cases))
    assert verdict.state == "inconclusive"


# ---- missing mode is inconclusive, not fail -------------------------------


def test_missing_routea_mode_is_inconclusive():
    payload = _payload(_passing_cases())
    payload["window"]["available_modes"] = ["probe"]
    verdict = evaluate(payload)
    assert verdict.state == "inconclusive"
    routea_cases = [
        c for c in verdict.cases
        if c.id in {m.id for m in CONFORMANCE_MATRIX if m.requires_mode == "routea"}
    ]
    assert all(c.result == "inconclusive" for c in routea_cases)


def test_skipped_case_is_inconclusive():
    cases = _passing_cases()
    cases[0] = {"id": cases[0]["id"], "rc": None, "stderr": "",
                "attestation": None,
                "skipped_reason": "timed out after 300s"}
    verdict = evaluate(_payload(cases))
    assert verdict.state == "inconclusive"


# ---- schema strictness ----------------------------------------------------


def test_evidence_rejects_extra_fields():
    payload = _payload(_passing_cases())
    payload["cases"][0]["claimed_pass"] = True
    verdict = evaluate(payload)
    assert verdict.state == "fail"


def test_attestation_rejects_extra_fields():
    with pytest.raises(Exception):
        Attestation.model_validate({**GOOD_ATT, "trust_me": True})


def test_window_requires_64_hex_executor_hash():
    with pytest.raises(Exception):
        WindowMeta(
            snapshot_uid=11, snapshot_name="s",
            started_at="a", finished_at="b", executor_sha256="short",
        )
