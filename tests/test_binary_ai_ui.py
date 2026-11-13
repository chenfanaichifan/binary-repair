"""Two product direct-repair paths on the /binary page.

Path 1 ``asm_roundtrip``: disassemble the target ELF function, let the AI rewrite
the assembly, assemble it with clang, inject the machine-code block and redirect
the function entry.

Path 2 ``binary_direct``: the AI emits raw machine-code bytes / same-length byte
edits (no assembly text, no decompiled C); a strict validator gates the bytes and
the deterministic gate still owns the disposition.

The page copy is Simplified Chinese; endpoint payloads stay English ASCII.  AI is
always a FakeClient injected through ``app.main.client_from_env``: no real
provider is contacted and no network access is required.
"""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import CSRF_TOKEN, SESSION_TOKEN, app

ROOT = Path(__file__).resolve().parents[1]
ELF_I386 = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf"
PE_X86_64 = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"

AI_TESTIDS = (
    "binary-ai-section",
    "binary-ai-file",
    "binary-ai-run-asm",
    "binary-ai-run-direct",
    "binary-ai-allow-static",
    "binary-ai-asm-result",
    "binary-ai-direct-result",
    "binary-ai-asm-status",
    "binary-ai-direct-status",
    "binary-ai-download",
    "binary-ai-error",
)

#: A complete i386 cdecl replacement for ``vuln(const char *src)``: bounded copy
#: of at most 15 bytes plus NUL into the recovered 16-byte stack buffer.
ASM_I386_GUARD = """.intel_syntax noprefix
push ebp
mov ebp, esp
sub esp, 0x20
mov eax, dword ptr [ebp + 8]
lea edx, [ebp - 0x10]
push esi
push edi
mov edi, edx
mov esi, eax
mov ecx, 15
.Lcopy:
test ecx, ecx
je .Ldone
mov al, byte ptr [esi]
test al, al
je .Ldone
mov byte ptr [edi], al
inc esi
inc edi
dec ecx
jmp .Lcopy
.Ldone:
mov byte ptr [edi], 0
pop edi
pop esi
leave
ret
"""


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


#: The asm round-trip path shells out to the host assembler (clang); the other
#: contracts are pure Python and always run.
requires_clang = pytest.mark.skipif(
    shutil.which("clang") is None,
    reason="host assembler (clang) is required for the asm round-trip path",
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


def test_binary_page_exposes_the_two_product_ai_paths():
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
        "路径一：汇编往返修复",
        "路径二：直接二进制修复",
        "asm_roundtrip",
        "binary_direct",
        "反汇编目标函数",
        "不反编译 C",
        "允许未验证候选",
        "/api/binary/ai-paths",
        "/static/js/binary.js",
    ):
        assert marker in page.text, marker
    # The previous protocol-style path ids are gone from the product UI.
    for legacy in ("binary-ai-run-plan", "binary-ai-run-bytes", "ai_plan", "ai_bytes"):
        assert legacy not in page.text, legacy
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
        "asm_roundtrip",
        "binary_direct",
        "download_allowed",
        "patched_base64",
        "Blob",
        "textContent",
        "binary-ai-run-asm",
        "binary-ai-run-direct",
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
    for marker in (".binary-ai-card", ".binary-ai-path", ".binary-ai-card-status"):
        assert marker in css.text, marker


def test_i18n_overrides_cover_the_new_ai_path_copy():
    js = _client().get("/static/js/i18n-curated-extra.js")
    assert js.status_code == 200
    for marker in (
        "路径一：汇编往返修复",
        "路径二：直接二进制修复",
        "运行路径一（汇编往返）",
        "运行路径二（直接二进制）",
        "两条 AI 路径的边界。",
        "运行中…",
    ):
        assert marker in js.text, marker
    assert "Assembly round-trip repair" in js.text
    assert "Direct binary repair" in js.text


def test_ai_paths_contract_api_lists_the_two_product_paths():
    response = _client().get("/api/binary/ai-paths")
    assert response.status_code == 200
    cjk = [char for char in response.text if "\u4e00" <= char <= "\u9fff"]
    assert not cjk, cjk[:10]
    payload = response.json()
    assert [path["id"] for path in payload["paths"]] == ["asm_roundtrip", "binary_direct"]
    for path in payload["paths"]:
        assert path["title"] and path["description"] and path["ai_outputs"]
    assert payload["invariants"]
    assert any("assembly" in item.lower() for item in payload["invariants"])


@requires_clang
def test_asm_roundtrip_verified_repair_is_downloadable(monkeypatch):
    fake = _use_fake(monkeypatch, {"schema_version": 1, "assembly": ASM_I386_GUARD})
    response = _post_ai(_client(), "asm_roundtrip", ELF_I386)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["path"] == "asm_roundtrip"
    assert payload["verified"] is True
    assert payload["disposition"] == "verified_patch"
    delivery = payload["delivery"]
    assert delivery["download_allowed"] is True
    assert delivery["verified"] is True
    assert delivery["tier"] in {"emulated_run", "native_run"}
    assert payload["filename"].endswith(".elf")
    assert isinstance(payload["report"], dict)
    assert base64.b64decode(payload["patched_base64"])[:4] == b"\x7fELF"

    ai = payload["ai"]
    assert ai["path"] == "asm_roundtrip"
    assert ai["requested"] is True
    assert ai["called"] is True
    assert ai["mode"] == "llm"
    assert ai["provider"] == "fake-provider"
    assert ai["model"] == "fake-model"
    assert ai["status"] == "accepted"
    validation = ai["validation"]
    assert len(validation["assembly_sha256"]) == 64
    assert isinstance(validation["code_bytes"], int) and validation["code_bytes"] > 0
    assert validation["method"]
    assert validation["cave_va"]

    # One bounded assembly call; the packet carries the disassembly but no bytes.
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["max_tokens"] == 1400
    assert call["thinking"] is False
    assert call["messages"][0]["role"] == "system"
    packet = json.loads(call["messages"][1]["content"])
    assert packet["path"] == "asm_roundtrip"
    assert packet["arch"] == "i386"
    assert packet["binary_sha256"] == payload["report"]["original_sha256"]
    assert "original_disassembly" in packet
    assert "code_hex" not in json.dumps(packet)


def test_asm_roundtrip_rejects_invalid_assembly(monkeypatch):
    fake = _use_fake(monkeypatch, {"schema_version": 1, "assembly": "syscall"})
    response = _post_ai(_client(), "asm_roundtrip", ELF_I386)
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["path"] == "asm_roundtrip"
    assert payload["disposition"] == "unsupported"
    assert payload["ai"]["status"] == "invalid"
    assert "assembly" in payload["ai"]["error"].lower()
    assert payload["detail"]
    assert "patched_base64" not in payload
    assert len(fake.calls) == 1


def test_asm_roundtrip_rejects_non_elf_input(monkeypatch):
    _use_fake(monkeypatch, {"schema_version": 1, "assembly": ASM_I386_GUARD})
    response = _post_ai(_client(), "asm_roundtrip", PE_X86_64)
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["path"] == "asm_roundtrip"
    assert payload["disposition"] == "unsupported"
    assert "ELF" in payload["detail"]
    assert payload["ai"]["status"] == "not_attempted"


def test_binary_direct_verified_repair_is_downloadable(monkeypatch):
    from app.services.repair.guards import abi_for, build_guard

    code = build_guard(abi_for("pe", "x86_64"), "strcpy", 16)
    payload_in = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": code.hex()},
    }
    fake = _use_fake(monkeypatch, payload_in)
    response = _post_ai(_client(), "binary_direct", PE_X86_64)
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["path"] == "binary_direct"
    assert payload["verified"] is True
    assert payload["disposition"] == "verified_patch"
    assert payload["delivery"]["download_allowed"] is True
    assert payload["filename"].endswith(".exe")
    assert base64.b64decode(payload["patched_base64"])[:2] == b"MZ"
    ai = payload["ai"]
    assert ai["status"] == "accepted"
    assert ai["validation"]["error"] is None
    assert ai["validation"]["actions"]
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["max_tokens"] == 1800
    assert call["thinking"] is False
    packet = json.loads(call["messages"][1]["content"])
    # The direct path reuses the existing byte-patch packet builder; only the
    # public response ``path`` is the product-level ``binary_direct`` id.
    assert "path" in packet
    assert packet["binary_sha256"] == payload["report"]["original_sha256"]
    assert "executable_sections" in packet
    assert "limits" in packet
    assert "code_hex" not in json.dumps(packet)


def test_binary_direct_privileged_machine_code_fails_closed(monkeypatch):
    _use_fake(monkeypatch, {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": "0f05"},  # syscall: always rejected by the validator
    })
    response = _post_ai(_client(), "binary_direct", PE_X86_64)
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["path"] == "binary_direct"
    assert payload["ai"]["status"] == "invalid"
    assert payload["ai"]["error"]
    assert "patched_base64" not in payload


def test_ai_repair_without_provider_returns_503_for_both_paths(monkeypatch):
    monkeypatch.setattr(main, "client_from_env", lambda: None)
    client = _client()
    for path, fixture in (("asm_roundtrip", ELF_I386), ("binary_direct", PE_X86_64)):
        response = _post_ai(client, path, fixture)
        assert response.status_code == 503, path
        payload = response.json()
        assert payload["ok"] is False
        assert payload["path"] == path
        assert payload["detail"] == "AI provider not configured"
        assert payload["ai"]["status"] == "unavailable"
        assert payload["ai"]["called"] is False
        assert isinstance(payload["report"], dict)
        assert "patched_base64" not in payload


def test_ai_repair_rejects_unknown_path(monkeypatch):
    monkeypatch.setattr(main, "client_from_env", lambda: None)
    response = _post_ai(_client(), "ai_plan", PE_X86_64)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "path must be one of" in detail
    assert "asm_roundtrip" in detail and "binary_direct" in detail
