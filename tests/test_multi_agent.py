"""Bounded main-agent -> reviewer-agent -> revision loop."""
from __future__ import annotations

import json
from types import SimpleNamespace

from app.services.code_repair import repair_code


def _patch(body: str) -> dict:
    return {
        "language": "c",
        "title": "bounded copy",
        "summary": "Use snprintf.",
        "confidence": "high",
        "findings": [{"title": "unbounded copy", "severity": "high", "line": 1, "cwe": "CWE-120"}],
        "patched_code": body,
        "notes": ["reviewed"],
    }


class ScriptedAgents:
    def __init__(self):
        self.calls = []
        self.repairs = [
            _patch('void f(char *p, size_t n) { snprintf(p, sizeof(p), "%s", "x"); }'),
            _patch('void f(char *p, size_t n) { snprintf(p, n, "%s", "x"); }'),
        ]
        self.reviews = [
            {"verdict": "needs_changes", "issues": [
                {"severity": "high", "line": 1, "issue": "sizeof(pointer) is not capacity",
                 "suggestion": "use n"}
            ], "notes": []},
            {"verdict": "pass", "issues": [], "notes": ["capacity is now explicit"]},
        ]

    def chat_json(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        system = messages[0]["content"]
        if "independent reviewer agent" in system:
            payload = self.reviews.pop(0)
        else:
            payload = self.repairs.pop(0)
        return SimpleNamespace(content=json.dumps(payload), model="fake-agent")


def test_main_and_reviewer_iterate_until_pass():
    client = ScriptedAgents()
    result = repair_code("void f(char *p){strcpy(p, \"x\");}", "c", client=client)
    assert result["repair_origin"] == "ai"
    assert result["changed"] is True
    assert result["agent_rounds"] == 2
    assert len(result["review_history"]) == 2
    assert result["review_history"][0]["verdict"] == "needs_changes"
    assert result["review_history"][1]["verdict"] == "pass"
    assert result["patched_code"] == 'void f(char *p, size_t n) { snprintf(p, n, "%s", "x"); }'
    assert client.calls[0][1]["max_tokens"] == 262144
    assert client.calls[0][1]["thinking"] is True
    assert client.calls[2][1]["thinking"] is True


def test_reviewer_rejects_after_bounded_rounds_then_falls_back():
    class NeverPasses(ScriptedAgents):
        def __init__(self):
            super().__init__()
            self.repairs = [
                _patch('void f(char *p, size_t n) { snprintf(p, n, "%s", "x"); }')
            ] * 3
            self.reviews = [
                {"verdict": "needs_changes", "issues": [{"severity": "high", "line": 1,
                 "issue": "still unsafe", "suggestion": "fix"}], "notes": []}
            ] * 3

    result = repair_code("void f(char *p){strcpy(p, \"x\");}", "c", client=NeverPasses())
    assert result["repair_origin"] == "rule"
    assert result["ai_attempted"] is True
    assert result["ai_error"] == "review_not_passed"
