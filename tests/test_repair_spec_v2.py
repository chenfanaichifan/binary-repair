"""RepairSpec v2 consistency/validation."""
from __future__ import annotations

from app.services.repair_spec import (
    failure_behavior_of, spec_from_plan, validate_spec,
)


def _v2(**overrides):
    plan = {
        "schema_version": 2,
        "vulnerability": {"type": "CWE121", "cwe": "CWE-121",
                          "root_cause": "unchecked copy length"},
        "program_context": {
            "function": "multicall_bad",
            "addresses": ["0x102cb60"],
            "registers": ["rdi", "rsi"],
            "memory": ["stack:16"],
            "capacity": 16,
            "allowed_calls": ["puts"],
        },
        "security_invariants": ["copy_len < 16"],
        "repair": {"strategy": "guard_input_length",
                   "failure_behavior": "reject oversized input",
                   "expected_behavior": "valid input unchanged"},
        "abi": {"architecture": "x86_64", "calling_convention": "sysv_amd64"},
        "verification": {
            "security_conditions": ["overflow_blocked"],
            "regression_conditions": ["short preserved"],
            "required_inputs": ["overflow", "short"],
        },
        "confidence": 0.9,
    }
    plan.update(overrides)
    return plan


CASE = {"target": "multicall_bad", "capacity": 16, "arch": "x86_64"}
SCOPE = {"va": 0x102cb60, "end": 0x102cbb0}


def test_valid_v2_and_factory():
    spec, error = validate_spec(_v2(), case=CASE, allowed_calls={"puts"},
                                target_scope=SCOPE)
    assert error == ""
    assert spec is not None
    assert spec.schema_version == 2
    again = spec_from_plan(spec.to_dict())
    assert again.to_dict() == spec.to_dict()


def test_v2_capacity_mismatch_rejected():
    plan = _v2()
    plan["program_context"]["capacity"] = 32
    spec, error = validate_spec(plan, case=CASE, allowed_calls={"puts"},
                                target_scope=SCOPE)
    assert spec is None and error == "capacity_mismatch"


def test_v2_missing_regression_conditions_rejected():
    plan = _v2()
    plan["verification"]["regression_conditions"] = []
    spec, error = validate_spec(plan, case=CASE, allowed_calls={"puts"},
                                target_scope=SCOPE)
    assert spec is None and error == "missing_regression_conditions"


def test_v2_unknown_strategy_and_bad_address_rejected():
    plan = _v2()
    plan["repair"]["strategy"] = "magic"
    spec, error = validate_spec(plan, case=CASE, allowed_calls={"puts"},
                                target_scope=SCOPE)
    assert spec is None and error == "unsupported_repair_strategy"
    plan = _v2()
    plan["program_context"]["addresses"] = ["0xdead"]
    spec, error = validate_spec(plan, case=CASE, allowed_calls={"puts"},
                                target_scope=SCOPE)
    assert spec is None and error == "affected_address_out_of_scope"


def test_v2_structured_failure_behavior_accepted_and_roundtrips():
    plan = _v2()
    plan["repair"]["failure_behavior"] = {
        "exit_code": 1, "stdout": None,
        "stderr": "ERROR: input exceeds destination capacity\n",
        "stdout_hex": None,
    }
    spec, error = validate_spec(plan, case=CASE, allowed_calls={"puts"},
                                target_scope=SCOPE)
    assert error == "" and spec is not None
    contract = failure_behavior_of(spec)
    assert contract is not None and contract.exit_code == 1
    assert contract.stderr == "ERROR: input exceeds destination capacity\n"
    assert spec.repair["failure_behavior"]["exit_code"] == 1
    again = spec_from_plan(spec.to_dict())
    assert again.to_dict() == spec.to_dict()
    assert failure_behavior_of(again) == contract


def test_v2_text_failure_behavior_stays_text_only():
    spec, error = validate_spec(_v2(), case=CASE, allowed_calls={"puts"},
                                target_scope=SCOPE)
    assert error == "" and spec is not None
    assert spec.repair["failure_behavior"] == "reject oversized input"
    assert failure_behavior_of(spec) is None


def test_v2_structured_failure_behavior_fails_closed():
    invalid = (
        ({"exit_code": -1}, "failure_behavior_exit_code_out_of_range"),
        ({"exit_code": "1"}, "failure_behavior_invalid_exit_code"),
        ({"exit_code": True}, "failure_behavior_invalid_exit_code"),
        ({"stderr": 5}, "failure_behavior_invalid_stderr"),
        ({"stdout": "x", "stdout_hex": "78"},
         "failure_behavior_conflicting_stdout"),
        ({"stdout_hex": "zz"}, "failure_behavior_invalid_stdout_hex"),
        ({"bogus": 1}, "failure_behavior_unexpected_fields"),
        ({}, "failure_behavior_empty"),
    )
    for contract, expected in invalid:
        plan = _v2()
        plan["repair"]["failure_behavior"] = contract
        spec, error = validate_spec(plan, case=CASE, allowed_calls={"puts"},
                                    target_scope=SCOPE)
        assert spec is None, contract
        assert error.startswith(expected), (contract, error)


def test_v1_still_accepted():
    plan = {
        "schema_version": 1,
        "vulnerability_type": "CWE121", "root_cause": "x",
        "affected_function": "multicall_bad",
        "affected_addresses": [], "affected_registers": [],
        "affected_memory": [], "original_behavior": "x",
        "required_invariant": "x", "repair_strategy": "guard_input_length",
        "failure_behavior": "reject", "permitted_calls": [],
        "expected_behavior": "x",
        "verification_conditions": ["security", "regression"],
        "confidence": "medium",
    }
    spec, error = validate_spec(plan, case=CASE, allowed_calls=set(),
                                target_scope=SCOPE)
    assert error == "" and spec.schema_version == 1
