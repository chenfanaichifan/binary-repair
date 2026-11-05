"""Tests for the screening-test comparison (T7.3).

The properties worth pinning are the honesty ones: a route with no observations
is never shown as equivalent, "changed" is decided by observed exit code rather
than by a result label, and no ranking is ever produced.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from workers.broker.comparison import compare

REPO = Path(__file__).resolve().parents[2]
TESTS = REPO / "fixtures/public/CWE121_src_char_declare_cpy_51b/tests"
MANIFESTS = [str(TESTS / "valid.json"), str(TESTS / "invalid.json")]

ERR = b"ERROR: input exceeds destination capacity\n"


def _case(cid, rc, out=b"", err=b""):
    return {"case_id": cid, "return_code": rc,
            "stdout_hex": out.hex(), "stderr_hex": err.hex()}


def payload(sha, cases):
    return {"schema_version": 1, "binary_sha256": sha, "cases": cases}


# The four valid cases and the two invalid ones, as the manifests define them.
VALID = [("valid-empty", b"\n"), ("valid-smallest", b"A\n"),
         ("valid-typical", b"A" * 10 + b"\n"), ("valid-maximum", b"A" * 49 + b"\n")]
INVALID = ["invalid-first", "invalid-longer"]


def vulnerable(sha="a" * 64):
    """Original-like: valid fine, 50-byte exits 0, 100-byte SIGSEGV(139)."""
    cases = [_case(cid, 0, out) for cid, out in VALID]
    cases.append(_case("invalid-first", 0, b"A" * 50 + b"\n"))
    cases.append(_case("invalid-longer", 139))
    return payload(sha, cases)


def repaired(sha="b" * 64):
    cases = [_case(cid, 0, out) for cid, out in VALID]
    cases += [_case(cid, 1, b"", ERR) for cid in INVALID]
    return payload(sha, cases)


def roundtrip_unchanged(sha="c" * 64):
    return vulnerable(sha)


# ---- the core discrimination -------------------------------------------------


def test_repaired_route_vs_unchanged_roundtrip():
    rec = compare(manifests=MANIFESTS, original=vulnerable(),
                  routes={"A": repaired(), "B_roundtrip": roundtrip_unchanged()})
    a = rec.routes["A"]
    b = rec.routes["B_roundtrip"]

    assert a.v3_result == "passed" and a.passed == 6
    assert a.repaired_invalid_cases == ("invalid-first", "invalid-longer")
    assert a.still_failing_invalid_cases == ()

    # The round trip preserves behaviour exactly — and that is NOT a repair.
    assert b.v3_result == "failed" and b.passed == 4
    assert b.repaired_invalid_cases == ()
    assert b.still_failing_invalid_cases == ("invalid-first", "invalid-longer")
    assert b.valid_behaviour_preserved is True


def test_roundtrip_is_flagged_as_still_vulnerable():
    rec = compare(manifests=MANIFESTS, original=vulnerable(),
                  routes={"B_roundtrip": roundtrip_unchanged()})
    joined = " ".join(rec.limitations)
    assert "not repaired" in joined
    assert "B_roundtrip" in joined


# ---- changed_by is decided by observed behaviour ----------------------------


def test_changed_by_lists_only_routes_that_moved():
    rec = compare(manifests=MANIFESTS, original=vulnerable(),
                  routes={"A": repaired(), "B_roundtrip": roundtrip_unchanged()})
    by_id = {c.case_id: c for c in rec.cases}

    assert by_id["invalid-first"].changed_by == ("A",)
    assert by_id["invalid-longer"].changed_by == ("A",)
    for cid, _ in VALID:
        assert by_id[cid].changed_by == (), "valid cases must not be reported as changed"


def test_a_failed_on_both_sides_is_not_reported_as_changed():
    """A route that fails the same way as the original moved nothing."""
    rec = compare(manifests=MANIFESTS, original=vulnerable(),
                  routes={"B_roundtrip": roundtrip_unchanged()})
    for case in rec.cases:
        assert case.changed_by == ()


# ---- fail-closed on missing evidence ---------------------------------------


def test_route_without_observations_is_not_run_not_equivalent():
    rec = compare(manifests=MANIFESTS, original=vulnerable(), routes={"B": {}})
    b = rec.routes["B"]
    assert b.v3_result == "not_run"
    assert b.repaired_invalid_cases == ()
    # It must never be presented as "behaves like the original".
    assert b.still_failing_invalid_cases == ("invalid-first", "invalid-longer")


def test_route_omitted_entirely_does_not_appear():
    rec = compare(manifests=MANIFESTS, original=vulnerable(), routes={"A": repaired()})
    assert set(rec.routes) == {"A"}


def test_case_error_in_payload_counts_as_absent():
    broken = repaired()
    broken["cases"] = [c for c in broken["cases"] if c["case_id"] != "invalid-first"]
    broken["cases"].append({"case_id": "invalid-first", "error": "timed out"})
    rec = compare(manifests=MANIFESTS, original=vulnerable(), routes={"A": broken})
    assert rec.routes["A"].not_run >= 1
    assert "invalid-first" not in rec.routes["A"].repaired_invalid_cases


# ---- no ranking, ever ------------------------------------------------------


def test_no_ranking_is_produced():
    rec = compare(manifests=MANIFESTS, original=vulnerable(),
                  routes={"A": repaired(), "B": roundtrip_unchanged()})
    assert rec.ranking is None
    assert "No ranking" in rec.note
    assert "safer" in rec.note


# ---- the comparison is only meaningful if the original is vulnerable --------


def test_original_not_failing_is_stated_as_a_limitation():
    """If the original already passes, a 'repair' proves nothing."""
    rec = compare(manifests=MANIFESTS, original=repaired(sha="d" * 64),
                  routes={"A": repaired()})
    joined = " ".join(rec.limitations)
    assert "not demonstrated" in joined


def test_original_sha_is_carried_through():
    rec = compare(manifests=MANIFESTS, original=vulnerable(sha="e" * 64),
                  routes={"A": repaired()})
    assert rec.original_sha256 == "e" * 64
    assert rec.routes["A"].candidate_sha256 == "b" * 64


# ---- shape ------------------------------------------------------------------


def test_every_case_appears_once_with_its_contract_exit_code():
    rec = compare(manifests=MANIFESTS, original=vulnerable(), routes={"A": repaired()})
    ids = [c.case_id for c in rec.cases]
    assert len(ids) == 6 and len(set(ids)) == 6
    for case in rec.cases:
        expected = 0 if case.kind == "valid" else 1
        assert case.expected_return_code == expected


def test_record_serialises_cleanly():
    rec = compare(manifests=MANIFESTS, original=vulnerable(),
                  routes={"A": repaired()}, fixture="CWE121")
    doc = json.loads(rec.model_dump_json())
    assert doc["schema_version"] == 1
    assert doc["gate"] == "V3"
    assert doc["ranking"] is None
    assert len(doc["cases"]) == 6
