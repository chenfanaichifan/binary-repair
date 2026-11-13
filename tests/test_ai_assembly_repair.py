"""Path 1: disassemble to assembly, repair in assembly, assemble and inject."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from app.services.ai_binary_repair import AI_PATHS, ASM_PATH, ai_paths_contract
from app.services.ai_assembly_repair import asm_repair

ROOT = Path(__file__).resolve().parents[1]
ELF_I386 = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf"
ELF_X86_64 = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"
ELF_ARM64 = ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf"
PE = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"

pytestmark = pytest.mark.skipif(
    shutil.which("clang") is None, reason="host assembler clang is unavailable"
)

ASM_I386 = r"""
.intel_syntax noprefix
.text
.globl repair_entry
repair_entry:
    push ebp
    mov ebp, esp
    sub esp, 32
    mov eax, dword ptr [ebp+8]
    lea edx, [ebp-16]
    xor ecx, ecx
.Lloop:
    cmp ecx, 15
    jae .Ldone
    mov bl, byte ptr [eax+ecx]
    mov byte ptr [edx+ecx], bl
    test bl, bl
    je .Ldone
    inc ecx
    jmp .Lloop
.Ldone:
    mov byte ptr [edx+ecx], 0
    leave
    ret
"""

ASM_X86_64 = r"""
.intel_syntax noprefix
.text
.globl repair_entry
repair_entry:
    push rbp
    mov rbp, rsp
    sub rsp, 32
    mov rsi, rdi
    lea rdi, [rbp-16]
    xor ecx, ecx
.Lloop:
    cmp ecx, 15
    jae .Ldone
    mov al, byte ptr [rsi+rcx]
    mov byte ptr [rdi+rcx], al
    test al, al
    je .Ldone
    inc ecx
    jmp .Lloop
.Ldone:
    mov byte ptr [rdi+rcx], 0
    leave
    ret
"""

ASM_ARM64 = r"""
.text
.globl repair_entry
repair_entry:
    sub sp, sp, #32
    add x2, sp, #16
    mov x3, #0
.Lloop:
    cmp x3, #15
    b.hs .Ldone
    ldrb w4, [x0, x3]
    strb w4, [x2, x3]
    cbz w4, .Ldone
    add x3, x3, #1
    b .Lloop
.Ldone:
    strb wzr, [x2, x3]
    add sp, sp, #32
    ret
"""


class FakeClient:
    model = "scripted-assembler"
    ai_mode = "scripted"

    def __init__(self, assembly: str | None = None, *, exc: BaseException | None = None):
        self.assembly = assembly
        self.exc = exc
        self.packet: dict | None = None

    def chat_json(self, messages, **kwargs):
        if self.exc is not None:
            raise self.exc
        self.packet = json.loads(messages[-1]["content"])
        return SimpleNamespace(
            content=json.dumps({"schema_version": 1, "assembly": self.assembly}),
            model=self.model,
            usage={"prompt_tokens": 9, "completion_tokens": 5},
            request_id="req-asm-test",
        )


def _read(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


def test_public_contract_has_assembly_and_direct_paths():
    contract = ai_paths_contract()
    assert [item["id"] for item in contract["paths"]] == list(AI_PATHS)
    assert contract["paths"][0]["id"] == ASM_PATH
    assert "assembly" in contract["paths"][0]["description"].lower()
    assert "no assembly text" in contract["paths"][1]["description"].lower() or \
        "no assembly" in contract["paths"][1]["description"].lower()
    assert "path 1 does use assembly text" in " ".join(contract["invariants"])


@pytest.mark.parametrize("fixture, assembly", [
    (ELF_I386, ASM_I386),
    (ELF_X86_64, ASM_X86_64),
    (ELF_ARM64, ASM_ARM64),
])
def test_assembly_path_is_verified(fixture: Path, assembly: str):
    data = _read(fixture)
    client = FakeClient(assembly)
    outcome = asm_repair(data, client=client)
    assert outcome.candidate is not None
    assert outcome.verified is True
    assert outcome.download_allowed is True
    report = outcome.report
    assert report.disposition == "verified_patch"
    assert report.strategy == "assembly-roundtrip"
    assert report.actions and report.actions[0]["kind"] == "assembly-function"
    assert report.verification["gate"]["success"] is True
    assert outcome.ai["status"] == "accepted"
    assert outcome.ai["validation"]["assembly_sha256"]
    assert outcome.ai["validation"]["code_bytes"] > 0
    assert client.packet is not None
    assert "original_disassembly" in client.packet
    assert "call" not in client.packet["original_disassembly"].split("\n")[0]


def test_assembly_path_rejects_forbidden_assembly():
    bad = ASM_I386.replace("leave\n    ret", "syscall\n    ret")
    outcome = asm_repair(_read(ELF_I386), client=FakeClient(bad))
    assert outcome.candidate is None
    assert outcome.verified is False
    assert outcome.report.disposition == "unsupported"
    assert outcome.ai["status"] == "invalid"


def test_assembly_path_rejects_call_instruction():
    bad = ASM_I386.replace(
        "    leave\n    ret",
        "    mov eax, 0x401000\n    call eax\n    leave\n    ret",
    )
    outcome = asm_repair(_read(ELF_I386), client=FakeClient(bad))
    assert outcome.candidate is None
    assert outcome.ai["status"] == "invalid"


def test_assembly_path_requires_provider():
    outcome = asm_repair(_read(ELF_I386), client=None)
    assert outcome.candidate is None
    assert outcome.ai["status"] == "unavailable"


def test_assembly_path_is_elf_only():
    outcome = asm_repair(_read(PE), client=FakeClient(ASM_I386))
    assert outcome.candidate is None
    assert "ELF" in (outcome.report.error or "")


def test_assembly_path_rejects_unknown_arch():
    outcome = asm_repair(_read(ELF_ARM64), client=FakeClient("not assembly"))
    assert outcome.candidate is None
    assert outcome.report.disposition == "unsupported"


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def test_api_assembly_path_verified(monkeypatch):
    monkeypatch.setattr(
        main_module, "client_from_env", lambda: FakeClient(ASM_I386),
    )
    response = _client().post(
        "/api/binary/ai-repair",
        files={"binary": ("vuln.elf", _read(ELF_I386), "application/octet-stream")},
        data={"csrf": CSRF_TOKEN, "path": ASM_PATH},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["path"] == ASM_PATH
    assert body["verified"] is True
    assert body["disposition"] == "verified_patch"
    assert body["patched_base64"].startswith("f0VMR")
    assert body["ai"]["status"] == "accepted"


def test_api_assembly_path_invalid_is_422(monkeypatch):
    monkeypatch.setattr(
        main_module, "client_from_env", lambda: FakeClient("not assembly"),
    )
    response = _client().post(
        "/api/binary/ai-repair",
        files={"binary": ("vuln.elf", _read(ELF_I386), "application/octet-stream")},
        data={"csrf": CSRF_TOKEN, "path": ASM_PATH},
    )
    assert response.status_code == 422
    assert response.json()["ai"]["status"] == "invalid"
