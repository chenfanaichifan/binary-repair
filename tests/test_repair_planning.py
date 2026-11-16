"""Planner-stage tests: structured plan before assembly, no injection."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.services.repair_spec import (
    failure_behavior_of, spec_from_plan, validate_spec,
)
from scripts.run_hard_benchmark import (
    _ai_plan_attempt, _ai_prompt_attempt,
)

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "fixtures" / "hard-cases" / "vuln-hardcases-c-x86_64.elf"
CASE = {"id": "hard-multicall", "target": "multicall_bad",
        "capacity": 16, "contract": "guard the 16-byte copy"}

CWE121 = (ROOT / "fixtures" / "public"
          / "CWE121_src_char_declare_cpy_51b" / "original.elf")
CWE121_TARGET = (
    "CWE121_Stack_Based_Buffer_Overflow__src_char_declare_cpy_51b_badSink")
CWE121_STDERR = "ERROR: input exceeds destination capacity\n"
CASE121 = {
    "id": "cwe121-unchecked-strcpy", "target": CWE121_TARGET,
    "capacity": 50, "arch": "x86_64",
    "contract": "reject oversized input with exit 1 and exact stderr",
    "poc": "fixtures/poc/cwe121.json",
}


class _AssemblyClient:
    model = "fake-asm-model"

    def __init__(self, assembly):
        self.assembly = assembly
        self.calls = 0

    def chat_json(self, messages, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            content=json.dumps({"schema_version": 1,
                               "assembly": self.assembly}),
            model=self.model, usage={"prompt_tokens": 1,
                                      "completion_tokens": 1},
            request_id="asm-1")


def _cwe121_plan(**overrides):
    plan = {
        "schema_version": 2,
        "vulnerability": {"type": "CWE121", "cwe": "CWE-121",
                          "root_cause": "unchecked strcpy into char[50]"},
        "program_context": {
            "function": CWE121_TARGET, "addresses": [],
            "registers": ["rdi"], "memory": ["stack:50"],
            "capacity": 50, "allowed_calls": [],
        },
        "security_invariants": ["len+1 <= 50"],
        "repair": {
            "strategy": "guard_input_length",
            "failure_behavior": {
                "exit_code": 1, "stdout": None,
                "stderr": CWE121_STDERR, "stdout_hex": None,
            },
            "expected_behavior": "valid input printed unchanged",
        },
        "abi": {"architecture": "x86_64",
                "calling_convention": "sysv_amd64"},
        "verification": {
            "security_conditions": ["oversized rejected"],
            "regression_conditions": ["valid preserved"],
        },
        "confidence": 0.9,
        "evidence_refs": ["static.target"],
    }
    plan.update(overrides)
    return plan


class _FakeClient:
    model = "fake-plan-model"

    def __init__(self, plan):
        self.plan = plan
        self.calls = 0

    def chat_json(self, messages, **kwargs):
        self.calls += 1
        return SimpleNamespace(content=json.dumps(self.plan), model=self.model,
                               usage={"prompt_tokens": 1, "completion_tokens": 1},
                               request_id="plan-1")


def _valid_plan():
    return {
        "schema_version": 1,
        "vulnerability_type": "CWE121",
        "root_cause": "unchecked copy",
        "affected_function": "multicall_bad",
        "affected_addresses": [],
        "affected_registers": ["rdi"],
        "affected_memory": ["stack:16"],
        "original_behavior": "copy and print",
        "required_invariant": "copy_len < 16",
        "repair_strategy": "guard_input_length",
        "failure_behavior": "reject oversized input",
        "permitted_calls": [],
        "expected_behavior": "valid input preserved",
        "verification_conditions": ["overflow_blocked", "valid_preserved"],
        "confidence": "medium",
    }


def test_valid_plan_is_hashable_and_no_assembly_call():
    client = _FakeClient(_valid_plan())
    result = _ai_plan_attempt(client, BINARY.read_bytes(), CASE, "full", False, None)
    assert client.calls == 1
    assert result["plan"] is not None
    assert result["plan_error"] == ""
    assert result["plan_sha256"]




def test_plan_expresses_structured_failure_behavior_and_matches_poc():
    client = _FakeClient(_cwe121_plan())
    result = _ai_plan_attempt(client, CWE121.read_bytes(), CASE121,
                              "full", False, None)
    assert result["plan"] is not None, result["plan_error"]
    assert result["plan_error"] == ""
    contract = result["failure_behavior"]
    assert contract is not None and contract["exit_code"] == 1
    assert contract["stderr"] == CWE121_STDERR
    assert result["failure_behavior_source"] == "plan"
    assert result["poc_failure_contract"] == {
        "exit_code": 1, "stdout": "", "stderr": CWE121_STDERR}


def test_plan_failure_behavior_contradicting_poc_is_typed():
    plan = _cwe121_plan()
    plan["repair"]["failure_behavior"]["stderr"] = "WRONG\n"
    client = _FakeClient(plan)
    result = _ai_plan_attempt(client, CWE121.read_bytes(), CASE121,
                              "full", False, None)
    assert result["plan"] is None
    assert result["plan_error"] == "failure_behavior_mismatch:stderr"
    assert client.calls == 2  # one planner-feedback retry, then fail closed


def _cwe121_repair_spec():
    spec, error = validate_spec(_cwe121_plan(), case=CASE121,
                                allowed_calls=set(), target_scope=None)
    assert error == ""
    return spec_from_plan(spec.to_dict())


def test_assembly_stage_uses_controlled_templates_from_plan_contract():
    repair_spec = _cwe121_repair_spec()
    assert failure_behavior_of(repair_spec) is not None
    assembly = (ROOT / "fixtures" / "hard-cases"
                / "cwe121_failure_contract.S").read_text()
    client = _AssemblyClient(assembly)
    result = _ai_prompt_attempt(client, CWE121.read_bytes(), CASE121,
                                "full", False, None,
                                repair_spec=repair_spec)
    assert result["validation_error"] is None, result["validation_error"]
    assert result["assembly"] is not None
    assert result["failure_behavior"]["exit_code"] == 1
    names = {item["name"] for item in result["controlled_templates"]}
    assert {"br_write_stderr", "br_exit_group"} <= names


def test_assembly_stage_without_contract_rejects_template_invocation():
    assembly = (ROOT / "fixtures" / "hard-cases"
                / "cwe121_failure_contract.S").read_text()
    client = _AssemblyClient(assembly)
    result = _ai_prompt_attempt(client, CWE121.read_bytes(), CASE121,
                                "full", False, None, repair_spec=None)
    # Without a plan-expressed failure contract no template is exposed, so
    # the invocation is rejected instead of being silently rewritten.
    assert result["failure_behavior"] is None
    assert result["controlled_templates"] == []
    assert "not allowed" in (result["validation_error"] or "")


CWE134 = (ROOT / "fixtures" / "repair-benchmark"
          / "CWE134_format_string" / "original.elf")
CASE134 = {
    "id": "cwe134-format-string", "target": "cwe134_bad",
    "capacity": 16, "arch": "x86_64", "sink_kind": "format_string",
    "contract": "uncontrolled format string",
    "poc": "fixtures/poc/repair-cwe134.json",
}


class _CapturingClient(_FakeClient):
    def __init__(self, plan):
        super().__init__(plan)
        self.messages = []

    def chat_json(self, messages, **kwargs):
        self.messages.append(messages)
        return super().chat_json(messages, **kwargs)


def _cwe134_plan(addresses):
    return {
        "schema_version": 2,
        "vulnerability": {
            "type": "CWE-134", "cwe": "CWE-134",
            "root_cause": "caller data used as the printf format string",
        },
        "program_context": {
            "function": "cwe134_bad", "addresses": addresses,
            "registers": ["rdi", "rsi"], "memory": ["[rbp-8]"],
            "capacity": 16, "allowed_calls": [],
        },
        "security_invariants": [
            "the printf format string is a program-controlled literal",
        ],
        "repair": {
            "strategy": "format_string",
            "failure_behavior": "caller data is never used as a format string",
            "expected_behavior": "benign input is printed unchanged",
        },
        "abi": {"architecture": "x86_64",
                "calling_convention": "sysv_amd64"},
        "verification": {
            "security_conditions": ["fixed format literal"],
            "regression_conditions": ["valid output preserved"],
        },
        "confidence": 0.9,
        "evidence_refs": ["static.target"],
    }


def test_planner_packet_publishes_target_scope():
    client = _CapturingClient(_cwe134_plan(["0x401156"]))
    result = _ai_plan_attempt(client, CWE134.read_bytes(), CASE134,
                              "full", False, None)
    assert result["plan"] is not None, result["plan_error"]
    packet = json.loads(client.messages[0][-1]["content"])
    assert "target_scope" in packet
    scope = packet["target_scope"]
    assert scope["name"] == "cwe134_bad"
    assert isinstance(scope["va"], int) and isinstance(scope["end"], int)
    assert scope["va"] < scope["end"]
    assert "target_scope" in packet["target_scope_rule"]


def test_cwe134_out_of_scope_callee_address_is_field_diagnosed():
    # Reproduces the historical PLAN_INVALID shape: the model listed the
    # callee printf VA (0x401050) in program_context.addresses.
    addresses = {
        "function_va": "0x401156", "call_va": "0x401177",
        "callee_va": "0x401050", "ret_va": "0x40117e",
    }
    client = _CapturingClient(_cwe134_plan(addresses))
    result = _ai_plan_attempt(client, CWE134.read_bytes(), CASE134,
                              "full", False, None)
    assert result["plan"] is None
    assert result["plan_error"] == "affected_address_out_of_scope"
    diagnostic = result["plan_invalid"]
    assert diagnostic["reason_code"] == "affected_address_out_of_scope"
    assert diagnostic["field"] == "program_context.addresses"
    assert "target_scope [0x401156" in diagnostic["expected"]
    assert "callee" in diagnostic["detail"]
    attempt = result["attempts"][0]
    assert attempt["diagnostics"]["field"] == "program_context.addresses"


def test_cwe134_in_scope_addresses_plan_is_valid():
    addresses = ["0x401156", "0x401177", "0x40117e"]
    client = _FakeClient(_cwe134_plan(addresses))
    result = _ai_plan_attempt(client, CWE134.read_bytes(), CASE134,
                              "full", False, None)
    assert result["plan"] is not None, result["plan_error"]
    assert result["plan"]["schema_version"] == 2
    assert result["plan"]["repair"]["strategy"] == "format_string"
    assert result["plan_invalid"] is None


def test_invalid_plan_is_typed_and_not_assembly():
    plan = _valid_plan()
    plan["permitted_calls"] = ["malloc"]
    client = _FakeClient(plan)
    result = _ai_plan_attempt(client, BINARY.read_bytes(), CASE, "full", False, None)
    assert result["plan"] is None
    assert result["plan_error"].startswith("permitted_call_not_allowed")
    # invalid plan gets one planner-feedback retry
    assert client.calls == 2
