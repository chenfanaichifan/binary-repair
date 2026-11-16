"""RepairSpec schema validation (fail closed before assembly)."""
from __future__ import annotations

from app.services.repair_spec import (
    diagnose_plan_error, spec_from_plan, validate_spec,
)


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


def test_structured_failure_behavior_contract_accepted_and_roundtrips():
    plan = _plan()
    plan["failure_behavior_contract"] = {
        "exit_code": 1, "stdout": None,
        "stderr": "ERROR: input exceeds destination capacity\n",
        "stdout_hex": None,
    }
    spec, error = validate_spec(plan, case=_case(),
                                allowed_calls={"puts"}, target_scope=_scope())
    assert error == "" and spec is not None
    contract = spec.failure_behavior_contract
    assert contract is not None and contract.exit_code == 1
    assert contract.stderr == "ERROR: input exceeds destination capacity\n"
    assert contract.stdout is None
    assert spec.to_dict()["failure_behavior_contract"]["exit_code"] == 1
    again = spec_from_plan(spec.to_dict())
    assert again.to_dict() == spec.to_dict()


def test_v1_plan_without_contract_has_no_structured_field():
    spec, error = validate_spec(_plan(), case=_case(),
                                allowed_calls={"puts"}, target_scope=_scope())
    assert error == "" and spec is not None
    assert spec.failure_behavior_contract is None
    assert "failure_behavior_contract" not in spec.to_dict()


def test_structured_failure_behavior_fails_closed():
    invalid = (
        ({"exit_code": 256}, "failure_behavior_exit_code_out_of_range"),
        ({"exit_code": True}, "failure_behavior_invalid_exit_code"),
        ({"exit_code": "1"}, "failure_behavior_invalid_exit_code"),
        ({"stdout": "x", "stdout_hex": "78"},
         "failure_behavior_conflicting_stdout"),
        ({"stdout_hex": "zz"}, "failure_behavior_invalid_stdout_hex"),
        ({"stderr": 5}, "failure_behavior_invalid_stderr"),
        ({"bogus": 1}, "failure_behavior_unexpected_fields"),
        ({}, "failure_behavior_empty"),
        ("not-an-object", "failure_behavior_not_object"),
    )
    for contract, expected in invalid:
        plan = _plan(failure_behavior_contract=contract)
        spec, error = validate_spec(plan, case=_case(),
                                    allowed_calls={"puts"},
                                    target_scope=_scope())
        assert spec is None, contract
        assert error.startswith(expected), (contract, error)


def test_diagnose_plan_error_is_field_level():
    scope = {"va": 0x4012b0, "end": 0x4016b0, "name": "multicall_bad"}
    case = {"target": "multicall_bad", "capacity": 16, "arch": "x86_64"}
    diag = diagnose_plan_error(
        "affected_address_out_of_scope", case=case, target_scope=scope)
    assert diag["schema_version"] == 1
    assert diag["reason_code"] == "affected_address_out_of_scope"
    assert diag["field"] == "program_context.addresses"
    assert "[0x4012b0, 0x4016b0)" in diag["expected"]
    assert "callee" in diag["detail"]

    diag = diagnose_plan_error(
        "permitted_call_not_allowed:malloc", case=case,
        allowed_calls={"puts", "helper_copy"})
    assert diag["field"] == "program_context.allowed_calls"
    assert "puts" in diag["expected"] and "helper_copy" in diag["expected"]
    assert "malloc" in diag["detail"]

    diag = diagnose_plan_error("unsupported_repair_strategy")
    assert diag["field"] == "repair.strategy"
    assert "format_string" in diag["expected"]

    diag = diagnose_plan_error("missing_or_empty:repair.failure_behavior")
    assert diag["field"] == "repair.failure_behavior"
    diag = diagnose_plan_error("failure_behavior_conflicting_stdout")
    assert diag["field"] == "repair.failure_behavior"

    diag = diagnose_plan_error("missing_security_conditions")
    assert diag["field"].startswith("verification.security_conditions")

    diag = diagnose_plan_error("capacity_mismatch", case=case)
    assert diag["field"] == "program_context.capacity"
    assert "16" in diag["expected"]

    diag = diagnose_plan_error("some_unmapped_error")
    assert diag["reason_code"] == "some_unmapped_error"
    assert diag["field"] is None and diag["expected"] is None
