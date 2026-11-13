"""Two direct-AI binary repair paths on the /binary page (ai_plan + ai_bytes).

The page copy is Simplified Chinese; endpoint payloads stay English ASCII.
AI is always a FakeClient injected through ``app.main.client_from_env``: no real
provider is contacted and no network access is required.  The deterministic gate
(not the model) still owns the disposition and the download permission.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main
from app.main import CSRF_TOKEN, SESSION_TOKEN, app

ROOT = Path(__file__).resolve().parents[1]
ELF_X86_64 = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PE_X86_64 = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"

AI_TESTIDS = (
    "binary-ai-section",
    "binary-ai-file",
    "binary-ai-run-plan",
    "binary-ai-run-bytes",
    "binary-ai-allow-static",
    "binary-ai-plan-result",
    "binary-ai-bytes-result",
    "binary-ai-download",
    "binary-ai-status",
    "binary-ai-error",
)

PLAN_GUARD = {
    "schema_version": 1,
    "sink_index": 0,
    "strategy": "guard",
    "reason": "unbounded copy guard from the deterministic analysis packet",
}
PLAN_IMMEDIATE = {
    "schema_version": 1,
    "sink_index": 0,
    "strategy": "immediate",
    "reason": "immediate length exceeds stack capacity",
}


class FakeClient:
    """Minimal ``chat_json`` client; the endpoint only reads the response fields."""

    provider = "fake-provider"
    model = "fake-model"

    def __init__(self, payload: dict | str) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def chat_json(self, messages, *, max_tokens=None, thinking=False):
        self.calls.append({
            "messages": messages,
            "max_tokens": max_tokens,
            "thinking": thinking,
        })
        content = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return SimpleNamespace(
            content=content,
            model=self.model,
            usage={"prompt_tokens": 11, "completion_tokens": 22, "total_tokens": 33},
            request_id="req-fake-1",
        )


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def _use_fake(monkeypatch, payload) -> FakeClient:
    fake = FakeClient(payload)
    monkeypatch.setattr(main, "client_from_env", lambda: fake)
    return fake


def _post_ai(client: TestClient, path: str, fixture: Path, *, allow_static_only: bool = False):
    data = {"csrf": CSRF_TOKEN, "path": path}
    if allow_static_only:
        data["allow_static_only"] = "1"
    return client.post(
        "/api/binary/ai-repair",
        files={"binary": (fixture.name, fixture.read_bytes(), "application/octet-stream")},
        data=data,
    )


def test_binary_page_exposes_two_ai_paths_without_breaking_the_single_path():
    page = _client().get("/binary")
    assert page.status_code == 200
    for testid in AI_TESTIDS:
        assert f'data-testid="{testid}"' in page.text, testid
    # One download control per AI result card; each is hidden until allowed.
    assert page.text.count('data-testid="binary-ai-download"') == 2
    # Cards carry test-friendly state attributes; both start idle/blocked.
    assert page.text.count('data-state="idle"') == 2
    assert page.text.count('data-download="blocked"') == 2
    assert page.text.count('data-report="hidden"') == 2
    for marker in (
        "AI 直接修复（两条路径）",
        "AI 规划 + 确定性字节写回",
        "AI 直出机器码 / 字节补丁",
        "ai_plan",
        "ai_bytes",
        "允许未验证候选",
        "/api/binary/ai-paths",
        "/static/js/binary.js",
    ):
        assert marker in page.text, marker
    # The pre-existing deterministic single-path flow must stay intact.
    for testid in (
        "binary-page",
        "binary-file",
        "binary-scan",
        "binary-repair",
        "binary-allow-static",
        "binary-disposition",
        "binary-download",
        "binary-report",
        "binary-error",
    ):
        assert f'data-testid="{testid}"' in page.text, testid


def test_ai_assets_cover_the_two_paths_and_keep_user_data_out_of_html():
    client = _client()
    js = client.get("/static/js/binary.js")
    assert js.status_code == 200
    text = js.text
    for marker in (
        "/api/binary/ai-repair",
        "ai_plan",
        "ai_bytes",
        "download_allowed",
        "patched_base64",
        "Blob",
        "textContent",
        "binary-ai-run-plan",
        "binary-ai-run-bytes",
        "dataset.state",
        "dataset.disposition",
        "dataset.download",
        "dataset.report",
    ):
        assert marker in text, marker
    # Never interpolate user data / model text into HTML.
    assert "innerHTML" not in text
    css = client.get("/static/css/binary.css")
    assert css.status_code == 200
    assert ".binary-ai-card" in css.text
    assert ".binary-ai-path" in css.text


def test_i18n_overrides_cover_the_ai_section_strings():
    js = _client().get("/static/js/i18n-curated-extra.js")
    assert js.status_code == 200
    for marker in (
        "AI 直接修复（两条路径）",
        "AI 规划 + 确定性字节写回",
        "AI 直出机器码 / 字节补丁",
        "运行路径一（AI 规划）",
        "路径二运行中…",
        "AI 服务未配置（未设置 provider）",
    ):
        assert marker in js.text, marker
    assert "Direct AI repair (two paths)" in js.text


def test_ai_paths_contract_api_is_english_ascii():
    response = _client().get("/api/binary/ai-paths")
    assert response.status_code == 200
    cjk = [char for char in response.text if "\u4e00" <= char <= "\u9fff"]
    assert not cjk, cjk[:10]
    payload = response.json()
    ids = [path["id"] for path in payload["paths"]]
    assert ids == ["ai_plan", "ai_bytes"]
    for path in payload["paths"]:
        assert path["title"] and path["description"] and path["ai_outputs"]
    assert payload["invariants"]


def test_ai_plan_verified_repair_is_downloadable_and_sends_no_raw_bytes(monkeypatch):
    fake = _use_fake(monkeypatch, PLAN_GUARD)
    response = _post_ai(_client(), "ai_plan", PE_X86_64)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["path"] == "ai_plan"
    assert payload["verified"] is True
    assert payload["disposition"] == "verified_patch"
    delivery = payload["delivery"]
    assert delivery["download_allowed"] is True
    assert delivery["verified"] is True
    assert delivery["tier"] in {"emulated_run", "native_run"}
    assert payload["filename"].endswith(".exe")
    assert isinstance(payload["report"], dict)
    assert isinstance(payload["warnings"], list)
    assert base64.b64decode(payload["patched_base64"])[:2] == b"MZ"

    ai = payload["ai"]
    assert ai["path"] == "ai_plan"
    assert ai["requested"] is True
    assert ai["called"] is True
    assert ai["mode"] == "llm"
    assert ai["provider"] == "fake-provider"
    assert ai["model"] == "fake-model"
    assert ai["status"] == "accepted"
    assert len(ai["plan_sha256"]) == 64
    assert ai["validation"]["strategy"] == "guard"

    # The model got one bounded call in JSON mode; raw binary bytes are absent.
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["max_tokens"] == 700
    assert call["thinking"] is False
    assert call["messages"][0]["role"] == "system"
    packet = json.loads(call["messages"][1]["content"])
    assert packet["path"] == "ai_plan"
    assert packet["binary_sha256"] == payload["report"]["original_sha256"]
    assert "code_hex" not in json.dumps(packet)
    assert len(call["messages"][1]["content"]) < 4000


def test_ai_plan_static_only_is_unverified_but_downloadable(monkeypatch):
    _use_fake(monkeypatch, PLAN_IMMEDIATE)
    response = _post_ai(_client(), "ai_plan", ELF_X86_64, allow_static_only=True)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["path"] == "ai_plan"
    assert payload["verified"] is False
    assert payload["disposition"] == "static_only_patch"
    assert payload["delivery"]["download_allowed"] is True
    assert payload["delivery"]["verified"] is False
    assert payload["delivery"]["tier"] == "static_only"
    assert payload["warnings"]
    assert base64.b64decode(payload["patched_base64"])[:4] == b"\x7fELF"


def test_ai_plan_without_best_effort_fails_closed(monkeypatch):
    _use_fake(monkeypatch, PLAN_IMMEDIATE)
    response = _post_ai(_client(), "ai_plan", ELF_X86_64)
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["path"] == "ai_plan"
    assert payload["disposition"] == "not_verified"
    assert payload["ai"]["called"] is True
    assert payload["report"]["delivery"]["download_allowed"] is False
    assert "patched_base64" not in payload


def test_ai_plan_invalid_model_payload_is_rejected(monkeypatch):
    fake = _use_fake(monkeypatch, {"schema_version": 1, "sink_index": 99, "strategy": "guard"})
    response = _post_ai(_client(), "ai_plan", PE_X86_64)
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["disposition"] == "unsupported"
    assert payload["ai"]["status"] == "invalid"
    assert "sink_index" in payload["ai"]["error"]
    assert len(fake.calls) == 1


def test_ai_repair_without_provider_returns_503(monkeypatch):
    monkeypatch.setattr(main, "client_from_env", lambda: None)
    response = _post_ai(_client(), "ai_plan", PE_X86_64)
    assert response.status_code == 503
    payload = response.json()
    assert payload["ok"] is False
    assert payload["path"] == "ai_plan"
    assert payload["detail"] == "AI provider not configured"
    assert payload["ai"]["status"] == "unavailable"
    assert payload["ai"]["called"] is False
    assert isinstance(payload["report"], dict)
    assert "patched_base64" not in payload


def test_ai_repair_rejects_unknown_path(monkeypatch):
    monkeypatch.setattr(main, "client_from_env", lambda: None)
    response = _post_ai(_client(), "ai_bogus", PE_X86_64)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "path must be one of" in detail
    assert "ai_plan" in detail and "ai_bytes" in detail


def test_ai_repair_rejects_unrecognised_input(monkeypatch):
    _use_fake(monkeypatch, PLAN_GUARD)
    response = _client().post(
        "/api/binary/ai-repair",
        files={"binary": ("sample.bin", b"not a binary container", "application/octet-stream")},
        data={"csrf": CSRF_TOKEN, "path": "ai_plan"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["disposition"] == "invalid"
    assert payload["ai"]["called"] is False


def test_ai_bytes_guard_machine_code_is_validated_and_verified(monkeypatch):
    from app.services.repair.guards import abi_for, build_guard

    code = build_guard(abi_for("pe", "x86_64"), "strcpy", 16)
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": code.hex()},
    }
    fake = _use_fake(monkeypatch, payload)
    response = _post_ai(_client(), "ai_bytes", PE_X86_64)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["path"] == "ai_bytes"
    assert body["verified"] is True
    assert body["disposition"] == "verified_patch"
    assert body["delivery"]["download_allowed"] is True
    assert body["ai"]["status"] == "accepted"
    assert body["ai"]["validation"]["error"] is None
    assert body["ai"]["validation"]["actions"]
    assert body["filename"].endswith(".exe")
    assert base64.b64decode(body["patched_base64"])[:2] == b"MZ"
    assert len(fake.calls) == 1
    assert fake.calls[0]["max_tokens"] == 1800
    packet = json.loads(fake.calls[0]["messages"][1]["content"])
    assert packet["path"] == "ai_bytes"
    assert "executable_sections" in packet
    assert "limits" in packet


def test_ai_bytes_privileged_machine_code_fails_closed(monkeypatch):
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": "0f05"},  # syscall: always rejected by the validator
    }
    _use_fake(monkeypatch, payload)
    response = _post_ai(_client(), "ai_bytes", PE_X86_64)
    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert body["path"] == "ai_bytes"
    assert body["ai"]["status"] == "invalid"
    assert body["ai"]["error"]
    assert "patched_base64" not in body
