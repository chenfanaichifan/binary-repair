"""RepairSpec schema validation (fail closed before assembly)."""
from __future__ import annotations

from app.services.repair_spec import validate_spec


def _plan(**overrides):
    plan = {
        "schema_version": 1,
        "vulnerability_type": "CWE121",
        "root_cause": "unchecked copy",
        "affected_function": "multicall_bad",
        "affected_addresses": ["0x102cb60"],
        "affected_registers": ["rdi", "rsi"],
        "affected_memory": ["stack:16"],
        "original_behavior": "copies input",
        "required_invariant": "copy_len < 16",
        "repair_strategy": "guard_input_length",
        "failure_behavior": "reject oversized input",
        "permitted_calls": ["puts"],
        "expected_behavior": "valid input unchanged",
        "verification_conditions": ["overflow_blocked", "valid_preserved"],
        "confidence": "medium",
    }
    plan.update(overrides)
    return plan


def _case():
    return {"target": "multicall_bad"}


def _scope():
    return {"va": 0x102cb60, "end": 0x102cbb0}


def test_valid_repair_spec():
    spec, error = validate_spec(_plan(), case=_case(),
                                allowed_calls={"puts", "helper_copy"},
                                target_scope=_scope())
    assert error == ""
    assert spec is not None
    assert spec.required_invariant == "copy_len < 16"


def test_unknown_field_rejected():
    spec, error = validate_spec(_plan(extra=True), case=_case(),
                                allowed_calls={"puts"}, target_scope=_scope())
    assert spec is None and error.startswith("unexpected_fields")


def test_disallowed_symbol_rejected():
    spec, error = validate_spec(_plan(permitted_calls=["malloc"]), case=_case(),
                                allowed_calls={"puts"}, target_scope=_scope())
    assert spec is None and error.startswith("permitted_call_not_allowed")


def test_out_of_scope_address_rejected():
    spec, error = validate_spec(_plan(affected_addresses=["0xdeadbeef"]),
                                case=_case(), allowed_calls={"puts"},
                                target_scope=_scope())
    assert spec is None and error == "affected_address_out_of_scope"


def test_missing_invariant_and_verification_rejected():
    spec, error = validate_spec(_plan(required_invariant=""), case=_case(),
                                allowed_calls={"puts"}, target_scope=_scope())
    assert spec is None and error.startswith("missing_or_empty")
    spec, error = validate_spec(_plan(verification_conditions=[]), case=_case(),
                                allowed_calls={"puts"}, target_scope=_scope())
    assert spec is None and error == "missing_verification_conditions"


def test_target_mismatch_rejected():
    spec, error = validate_spec(_plan(affected_function="other"), case=_case(),
                                allowed_calls={"puts"}, target_scope=_scope())
    assert spec is None and error == "affected_function_mismatch"
