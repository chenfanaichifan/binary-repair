"""Tests for app/services/repair_states.py (the canonical state machine)."""

from __future__ import annotations

from app.services import acceptance_invariants
from app.services import repair_states as states


def test_state_machine_self_check_is_clean() -> None:
    assert states.SCHEMA_VERSION == 1
    assert states.validate_state_machine() == []
    assert not set(states.REPAIR_STATES) & set(states.FAILURE_STATES)
    assert len(set(states.ALL_REPAIR_STATES)) == len(states.ALL_REPAIR_STATES)
    assert set(states.TERMINAL_STATES) <= set(states.ALL_REPAIR_STATES)


def test_forward_chain_is_the_only_happy_path() -> None:
    chain = (None, "candidate", "analysis_only", "patch_candidate", "verified")
    for source, target in zip(chain, chain[1:]):
        ok, reason = states.validate_transition(source, target)
        assert ok is True, (source, target, reason)
        assert reason == ""
    ok, reason = states.validate_transition(
        "verified", "release_eligible",
        evidence_ok=True, independence_ok=True,
    )
    assert ok is True, reason
    assert reason == ""


def test_release_eligible_requires_both_gates() -> None:
    ok, reason = states.validate_transition("verified", "release_eligible")
    assert ok is False
    assert "evidence_ok=True" in reason
    assert "independence_ok=True" in reason

    ok, reason = states.validate_transition(
        "verified", "release_eligible", evidence_ok=True)
    assert ok is False
    assert "evidence_ok" not in reason
    assert "independence_ok=True" in reason

    ok, reason = states.validate_transition(
        "verified", "release_eligible", independence_ok=True)
    assert ok is False
    assert "evidence_ok=True" in reason
    assert "independence_ok" not in reason


def test_evidence_gate_does_not_unlock_illegal_edges() -> None:
    ok, reason = states.validate_transition(
        "candidate", "release_eligible",
        evidence_ok=True, independence_ok=True,
    )
    assert ok is False
    assert "illegal transition" in reason
    assert "release_eligible" in reason


def test_unknown_states_are_rejected_with_reason() -> None:
    ok, reason = states.validate_transition("verified", "blessed")
    assert ok is False
    assert "unknown target state" in reason

    ok, reason = states.validate_transition("blessed", "verified")
    assert ok is False
    assert "unknown source state" in reason


def test_self_transition_is_not_a_state_change() -> None:
    for state in ("candidate", "analysis_only", "verified", "rejected"):
        ok, reason = states.validate_transition(state, state)
        assert ok is False
        assert "self-transition" in reason


def test_terminal_states_have_no_outgoing_transitions() -> None:
    for state in states.TERMINAL_STATES:
        assert states.allowed_transitions(state) == ()
        for target in states.ALL_REPAIR_STATES:
            ok, _reason = states.validate_transition(state, target)
            assert ok is False
        assert states.is_terminal_state(state) is True


def test_retry_edges_from_recoverable_failures() -> None:
    for source in ("not_run", "inconclusive", "unavailable"):
        assert "candidate" in states.allowed_transitions(source)


def test_failure_states_are_explicit() -> None:
    assert "not_verified" not in states.FAILURE_STATES
    for failure in states.FAILURE_STATES:
        assert states.is_failure_state(failure) is True
    assert states.is_failure_state("verified") is False


def test_canonical_status_aliases() -> None:
    expected = {
        "verified_patch": "verified",
        "verified": "verified",
        "patched": "verified",
        "success_within_scope": "verified",
        "analysis_only": "analysis_only",
        "not_verified": "analysis_only",
        "static_only_patch": "patch_candidate",
        "invalid": "unsupported",
        "candidate": "candidate",
        "rejected": "rejected",
        "inconclusive": "inconclusive",
    }
    for raw, canonical in expected.items():
        assert states.canonical_status(raw) == canonical, raw
    assert states.canonical_status("blessed") == states.UNKNOWN_STATE
    assert states.canonical_status(None) == states.UNKNOWN_STATE


def test_state_of_mapping_and_object_views() -> None:
    assert states.state_of({"disposition": "verified_patch"}) == "verified"
    assert states.state_of({"status": "analysis_only"}) == "analysis_only"
    assert states.state_of({"verified": True}) == "verified"
    assert states.state_of({"success": False}) == "analysis_only"
    assert states.state_of({"verification": {"gate": {
        "outcome": "success_within_scope"}}}) == "verified"
    assert states.state_of({"decision": {"outcome": "rejected"}}) == "rejected"
    assert states.state_of(None) == states.UNKNOWN_STATE
    assert states.state_of("patched") == "verified"


def test_state_of_uses_to_dict_when_available() -> None:
    class Record:
        def to_dict(self) -> dict:
            return {"status": "not_run"}

    assert states.state_of(Record()) == "not_run"


def test_capability_state_mapping() -> None:
    assert states.capability_state_of("covered") == "covered"
    assert states.capability_state_of("supported") == "covered"
    assert states.capability_state_of("partial") == "partial"
    assert states.capability_state_of("non_goal") == "non_goal"
    assert states.capability_state_of("unavailable") == "unavailable"
    assert states.capability_state_of("not_started") == "not_started"
    assert states.capability_state_of("verified") == states.UNKNOWN_STATE


def test_acceptance_invariants_mapping_covers_every_existing_value() -> None:
    mapping = states.acceptance_invariants_state
    for value in acceptance_invariants.VERIFIED_DISPOSITIONS:
        assert mapping(value) == "verified", value
    for value in acceptance_invariants.NON_DOWNLOAD_DISPOSITIONS:
        mapped = mapping(value)
        assert mapped in states.ALL_REPAIR_STATES, (value, mapped)
        assert mapped not in {"verified", "release_eligible"}, value
    for value in acceptance_invariants.TARGET_POLICIES:
        assert mapping(value) in state_set(), value
    for outcome in ("success_within_scope", "rejected", "inconclusive",
                    "unsupported"):
        assert mapping(outcome) in {*states.REPAIR_STATES, *states.FAILURE_STATES}


def state_set() -> set[str]:
    return set(states.ALL_REPAIR_STATES)


def test_acceptance_invariants_fallback_matches_live_module() -> None:
    vocabulary = states._acceptance_vocabulary()
    assert vocabulary["verified_dispositions"] == tuple(
        acceptance_invariants.VERIFIED_DISPOSITIONS)
    assert vocabulary["non_download_dispositions"] == tuple(
        acceptance_invariants.NON_DOWNLOAD_DISPOSITIONS)
    assert vocabulary["target_policies"] == tuple(
        acceptance_invariants.TARGET_POLICIES)


def test_allowed_transitions_are_declared_and_validated() -> None:
    assert states.allowed_transitions(None) == states.ALLOWED_TRANSITIONS[
        states.START_STATE]
    assert states.allowed_transitions("candidate") == (
        states.ALLOWED_TRANSITIONS["candidate"])
    assert states.allowed_transitions("unknown") == ()
    transition = states.validate_transition(
        states.START_STATE, "candidate")
    assert transition == (True, "")


def test_validate_transition_reports_are_plain_strings() -> None:
    for source in (None, "candidate", "patch_candidate", "verified",
                   "release_eligible", "rejected"):
        ok, reason = states.validate_transition(source, "verified")
        assert isinstance(ok, bool)
        assert isinstance(reason, str)
        if not ok:
            assert reason
