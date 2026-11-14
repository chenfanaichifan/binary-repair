"""Path B assembly validation feedback/retry (no provider network)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

from scripts.run_hard_benchmark import _ai_prompt_attempt

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "fixtures" / "hard-cases" / "vuln-hardcases-c-x86_64.elf"


class _FakeClient:
    model = "fake-assembly-model"

    def __init__(self, assemblies: list[str]):
        self.assemblies = list(assemblies)
        self.calls = 0

    def chat_json(self, messages, **kwargs):
        assembly = self.assemblies[min(self.calls, len(self.assemblies) - 1)]
        self.calls += 1
        return SimpleNamespace(
            content=json.dumps({"schema_version": 1, "assembly": assembly}),
            model=self.model,
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            request_id=f"fake-{self.calls}",
        )


def _case():
    return {
        "target": "multicall_bad",
        "capacity": 16,
        "contract": "preserve behavior",
    }


def test_ud2_is_retried_then_valid_assembly_used():
    client = _FakeClient([
        ".intel_syntax noprefix\n.text\nud2\n",
        ".intel_syntax noprefix\n.text\nret\n",
    ])
    result = _ai_prompt_attempt(
        client, BINARY.read_bytes(), _case(), "full", False, None,
    )
    assert client.calls == 2
    assert result["assembly"] is not None
    assert result["validation_error"] is None
    assert [a["validation_error_class"] for a in result["attempts"]] == [
        "assembly_forbidden", None,
    ]


def test_persistent_ud2_stays_typed_and_not_injected():
    client = _FakeClient([".intel_syntax noprefix\n.text\nud2\n"] * 2)
    result = _ai_prompt_attempt(
        client, BINARY.read_bytes(), _case(), "full", False, None,
    )
    assert client.calls == 2
    assert result["assembly"] is not None  # returned for exact error evidence
    assert result["validation_error_class"] == "assembly_forbidden"
    assert all(a["validation_error"] for a in result["attempts"])


def test_inject_target_reports_typed_ud2_and_no_candidate_reason():
    from scripts.run_hard_benchmark import _inject_target, _target_va
    from app.services.containers import detect_container

    data = BINARY.read_bytes()
    container = detect_container(data)
    target = "multicall_bad"
    assert _target_va(container, target) is not None
    patched, meta = _inject_target(
        data, target, 16, ".intel_syntax noprefix\n.text\nud2\n", [],
    )
    assert patched is None
    assert meta["error_class"] == "assembly_forbidden"
    assert meta["error_token"] == "ud2"
