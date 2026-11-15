"""Planner-stage tests: structured plan before assembly, no injection."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.run_hard_benchmark import _ai_plan_attempt

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "fixtures" / "hard-cases" / "vuln-hardcases-c-x86_64.elf"
CASE = {"id": "hard-multicall", "target": "multicall_bad",
        "capacity": 16, "contract": "guard the 16-byte copy"}


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


def test_invalid_plan_is_typed_and_not_assembly():
    plan = _valid_plan()
    plan["permitted_calls"] = ["malloc"]
    client = _FakeClient(plan)
    result = _ai_plan_attempt(client, BINARY.read_bytes(), CASE, "full", False, None)
    assert result["plan"] is None
    assert result["plan_error"].startswith("permitted_call_not_allowed")
    # invalid plan gets one planner-feedback retry
    assert client.calls == 2
