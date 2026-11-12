"""Model request contract: 32K output budget and thinking enabled."""
from __future__ import annotations

import json

import httpx

from app.services.assistant_llm import HttpJsonClient
from app.services.code_repair import repair_code


def test_httpx_payload_enables_thinking_and_32k():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={
            "model": "deepseek-test",
            "choices": [{"message": {"content": "{\"ok\": true}"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    client = HttpJsonClient(
        api_key="sk-test-0123456789abcdef",
        base_url="https://example.invalid/v1",
        model="deepseek-test",
        transport=httpx.MockTransport(handler),
    )
    client.chat_json([{"role": "user", "content": "hi"}], max_tokens=32768, thinking=True)
    assert seen["max_tokens"] == 32768
    assert seen["thinking"] == {"type": "enabled"}
    assert "temperature" not in seen


def test_code_repair_requests_thinking_and_32k():
    seen = {}

    class FakeClient:
        def chat_json(self, messages, **kwargs):
            seen.update(kwargs)
            return type("Response", (), {
                "content": json.dumps({
                    "language": "c",
                    "title": "bounded copy",
                    "summary": "Use snprintf.",
                    "confidence": "high",
                    "findings": [{"title": "unbounded copy", "severity": "high", "line": 1}],
                    "patched_code": 'void f(char *p, size_t n) { snprintf(p, n, "%s", "x"); }',
                    "notes": ["caller must pass capacity"],
                }),
                "model": "fake",
            })()

    result = repair_code("void f(char *p){strcpy(p, \"x\");}", "c", client=FakeClient())
    assert seen["max_tokens"] == 32768
    assert seen["thinking"] is True
    assert result["repair_origin"] == "ai"
