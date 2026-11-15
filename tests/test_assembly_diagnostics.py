"""P10 assembly policy/diagnostics/feedback tests (no provider)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

from app.services.ai_assembly_repair import _validate_assembly_text
from app.services.repair.assembly_diagnostics import parse_assembler_stderr
from app.services.repair.assembly_feedback import build_assembly_feedback
from app.services.repair.assembly_policy import check_assembly_policy
from scripts.run_hard_benchmark import _ai_prompt_attempt

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "fixtures" / "hard-cases" / "vuln-hardcases-c-x86_64.elf"


def test_absolute_branch_is_typed_not_rewritten():
    text = (
        ".intel_syntax noprefix\n.text\n"
        "cmp eax, 16\njge 0x4011b1\n.Lok:\nret\n"
    )
    result = check_assembly_policy(text, "x86_64")
    assert not result.ok
    diagnostic = result.diagnostics[0]
    assert diagnostic.error_class == "absolute_branch_target"
    assert diagnostic.line == 4
    assert "0x4011b1" in diagnostic.token
    try:
        _validate_assembly_text(text, "x86_64", [])
    except ValueError as exc:
        assert getattr(exc, "error_class", "") == "assembly_validation"
        assert getattr(exc, "diagnostics", [])[0].error_class == "absolute_branch_target"
    else:
        raise AssertionError("absolute branch accepted")


def test_local_label_assembly_is_accepted():
    text = (
        ".intel_syntax noprefix\n.text\n"
        "cmp eax, 16\njge .Lfail\n.Lok:\nret\n.Lfail:\nret\n"
    )
    assert check_assembly_policy(text, "x86_64").ok
    assert _validate_assembly_text(text, "x86_64", [])


def test_assembler_stderr_is_structured():
    rows = parse_assembler_stderr(
        "repair.s:3:8: error: invalid operand for instruction\njge 0x4011b1\n"
        "        ^\n"
    )
    assert rows
    assert rows[0].line == 3
    assert rows[0].error_class == "invalid_operand"
    assert "invalid operand" in rows[0].message


def test_feedback_contains_diagnostic_without_rewrite():
    feedback = build_assembly_feedback(
        "jge 0x4011b1\n",
        [{"error_class": "absolute_branch_target", "message": "use local label", "line": 1}],
    )
    assert feedback["diagnostics"][0]["error_class"] == "absolute_branch_target"
    assert any("Do not change the meaning" in item for item in feedback["instructions"])


class _FakeClient:
    model = "fake-assembly-model"

    def __init__(self, assemblies):
        self.assemblies = list(assemblies)
        self.calls = 0

    def chat_json(self, messages, **kwargs):
        assembly = self.assemblies[min(self.calls, len(self.assemblies) - 1)]
        self.calls += 1
        return SimpleNamespace(
            content=json.dumps({"schema_version": 1, "assembly": assembly}),
            model=self.model, usage={}, request_id=f"fake-{self.calls}",
        )


def test_absolute_branch_gets_feedback_retry_then_local_label():
    client = _FakeClient([
        ".intel_syntax noprefix\n.text\ncmp eax,16\njge 0x4011b1\nret\n",
        ".intel_syntax noprefix\n.text\ncmp eax,16\njge .Lfail\nret\n.Lfail:\nret\n",
    ])
    result = _ai_prompt_attempt(
        client, BINARY.read_bytes(),
        {"target": "multicall_bad", "capacity": 16, "contract": "preserve"},
        "full", False, None,
    )
    assert client.calls == 2
    assert result["assembly"] is not None
    assert result["attempts"][0]["diagnostics"][0]["error_class"] == "absolute_branch_target"
    assert result["attempts"][1]["validation_error"] is None
