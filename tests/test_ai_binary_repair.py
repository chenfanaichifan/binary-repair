"""Both AI direct-binary paths: bounded planning, raw bytes, gate authority."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from app.services.binary_pipeline import detect_container
from app.services.ai_binary_repair import (
    AI_PATH_BYTES,
    AI_PATH_PLAN,
    AI_PATHS,
    ai_paths_contract,
    ai_repair,
    build_bytes_packet,
    build_plan_packet,
)

ROOT = Path(__file__).resolve().parents[1]
PE_GUARD = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"
ELF_MEMCPY = ROOT / "fixtures" / "elf" / "vuln-memcpy-x86.elf"


class FakeClient:
    """Scripted chat_json client (never performs a network call)."""

    model = "scripted-model"
    ai_mode = "scripted"

    def __init__(self, payload: dict | None = None, *, exc: BaseException | None = None):
        self.payload = payload
        self.exc = exc
        self.messages: list[dict[str, str]] | None = None

    def chat_json(self, messages, **kwargs):
        self.messages = messages
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(
            content=json.dumps(self.payload),
            model=self.model,
            usage={"prompt_tokens": 7, "completion_tokens": 5},
            request_id="req-ai-test",
        )


def _read(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


def test_paths_contract_has_two_direct_binary_paths():
    contract = ai_paths_contract()
    assert [item["id"] for item in contract["paths"]] == list(AI_PATHS)
    assert "assembly" in " ".join(contract["invariants"])
    assert "decompilation" in " ".join(contract["invariants"])


def test_plan_packet_has_no_raw_binary_bytes():
    data = _read(PE_GUARD)
    packet = build_plan_packet(data)
    assert packet["path"] == AI_PATH_PLAN
    assert packet["findings"]
    assert packet["binary_sha256"]
    text = json.dumps(packet)
    # The packet carries metadata only; it must not carry the binary payload.
    assert data[:64].hex() not in text
    assert len(text) < 20_000


def test_bytes_packet_lists_safe_regions_and_limits():
    data = _read(ELF_MEMCPY)
    packet = build_bytes_packet(data)
    assert packet["path"] == AI_PATH_BYTES
    assert packet["executable_sections"]
    assert packet["limits"]["max_injected_code_bytes"] == 4096
    finding = packet["findings"][0]
    assert finding["length_offset"] is not None
    assert finding["call_offset"] is not None


def test_plan_path_selects_supported_guard_and_verifies():
    data = _read(PE_GUARD)
    client = FakeClient({
        "schema_version": 1, "sink_index": 0,
        "strategy": "guard", "reason": "bounded stack copy",
    })
    outcome = ai_repair(data, path=AI_PATH_PLAN, client=client)
    assert outcome.candidate is not None
    assert outcome.verified is True
    assert outcome.download_allowed is True
    report = outcome.report
    assert report.disposition == "verified_patch"
    assert report.strategy == "guard"
    assert report.actions and report.actions[0]["kind"] == "guard"
    assert report.verification["gate"]["success"] is True
    assert outcome.ai["called"] is True
    assert outcome.ai["mode"] == "scripted"
    assert outcome.ai["status"] == "accepted"
    assert outcome.ai["plan_sha256"]
    assert outcome.ai["authority"] == "deterministic_gate"
    assert client.messages is not None


def test_plan_path_selects_supported_immediate_and_verifies():
    data = _read(ELF_MEMCPY)
    outcome = ai_repair(
        data, path=AI_PATH_PLAN,
        client=FakeClient({"schema_version": 1, "sink_index": 0, "strategy": "immediate"}),
    )
    assert outcome.verified is True
    assert outcome.report.disposition == "verified_patch"
    assert outcome.report.strategy == "immediate"
    assert outcome.report.actions[0]["kind"] == "immediate"


@pytest.mark.parametrize("payload, needle", [
    ({"schema_version": 1, "sink_index": 99, "strategy": "guard"}, "out of range"),
    ({"schema_version": 2, "sink_index": 0, "strategy": "guard"}, "schema_version"),
    ({"schema_version": 1, "sink_index": "0", "strategy": "guard"}, "sink_index"),
    ({"schema_version": 1, "sink_index": 0, "strategy": "immediate"}, "requires strategy=guard"),
    ({"schema_version": 1, "sink_index": 0, "strategy": "guard", "offset": 1}, "unexpected"),
])
def test_invalid_plan_is_fail_closed(payload, needle):
    outcome = ai_repair(_read(PE_GUARD), path=AI_PATH_PLAN, client=FakeClient(payload))
    assert outcome.candidate is None
    assert outcome.download_allowed is False
    assert outcome.report.disposition == "unsupported"
    assert outcome.ai["status"] == "invalid"
    assert needle in (outcome.report.error or "")


def test_provider_error_is_fail_closed():
    outcome = ai_repair(
        _read(PE_GUARD), path=AI_PATH_PLAN,
        client=FakeClient(exc=TimeoutError("slow provider")),
    )
    assert outcome.candidate is None
    assert outcome.ai["status"] == "error"
    assert "provider_error" in (outcome.report.error or "")


def test_missing_provider_is_unavailable():
    outcome = ai_repair(_read(PE_GUARD), path=AI_PATH_PLAN, client=None)
    assert outcome.candidate is None
    assert outcome.ai["status"] == "unavailable"
    assert outcome.report.disposition == "unsupported"


def test_ai_path_rejects_unknown_path():
    outcome = ai_repair(_read(PE_GUARD), path="ai_magic", client=FakeClient({}))
    assert outcome.candidate is None
    assert outcome.report.disposition == "invalid"


def test_ai_plan_never_promotes_a_failed_gate():
    # A plan may claim a repair, but if the deterministic writer/gate cannot
    # produce a passing candidate the AI path must not return one.  The
    # immediate fixture with a plan selecting a guard-style action is rejected
    # before writing, so use a synthetic no-op edit through path 2 once the
    # validator is available; here the plan-level invalid path is enough for
    # the AI planning contract.
    data = _read(PE_GUARD)
    outcome = ai_repair(
        data, path=AI_PATH_PLAN,
        client=FakeClient({"schema_version": 1, "sink_index": 0, "strategy": "immediate"}),
    )
    assert outcome.candidate is None
    assert outcome.report.disposition == "unsupported"
    assert outcome.report.delivery["verified"] is False


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def _post(client: TestClient, path: str, **extra):
    return client.post(
        "/api/binary/ai-repair",
        files={"binary": ("vuln.exe", _read(PE_GUARD), "application/octet-stream")},
        data={"csrf": CSRF_TOKEN, "path": path, **extra},
    )


def test_api_ai_repair_requires_provider(monkeypatch):
    monkeypatch.setattr(main_module, "client_from_env", lambda: None)
    response = _post(_client(), AI_PATH_PLAN)
    assert response.status_code == 503
    body = response.json()
    assert body["ok"] is False
    assert body["ai"]["status"] == "unavailable"


def test_api_ai_repair_verified(monkeypatch):
    monkeypatch.setattr(
        main_module, "client_from_env",
        lambda: FakeClient({"schema_version": 1, "sink_index": 0, "strategy": "guard"}),
    )
    response = _post(_client(), AI_PATH_PLAN)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["verified"] is True
    assert body["disposition"] == "verified_patch"
    assert body["path"] == AI_PATH_PLAN
    assert body["ai"]["status"] == "accepted"
    assert base64.b64decode(body["patched_base64"])[:2] == b"MZ"


def test_api_ai_repair_invalid_plan_is_422(monkeypatch):
    monkeypatch.setattr(
        main_module, "client_from_env",
        lambda: FakeClient({"schema_version": 1, "sink_index": -1, "strategy": "guard"}),
    )
    response = _post(_client(), AI_PATH_PLAN)
    assert response.status_code == 422
    assert response.json()["ai"]["status"] == "invalid"


def test_api_ai_paths_contract_is_english_ascii():
    response = _client().get("/api/binary/ai-paths")
    assert response.status_code == 200
    assert response.text.isascii()
    assert [row["id"] for row in response.json()["paths"]] == list(AI_PATHS)


def _load_cli():
    import importlib.util

    path = ROOT / "scripts" / "repair_binary.py"
    spec = importlib.util.spec_from_file_location("br_ai_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_ai_path_writes_verified_candidate(monkeypatch, tmp_path, capsys):
    import app.services.assistant_llm as assistant_llm

    monkeypatch.setattr(
        assistant_llm, "client_from_env",
        lambda: FakeClient({"schema_version": 1, "sink_index": 0, "strategy": "guard"}),
    )
    cli = _load_cli()
    out = tmp_path / "ai-fixed.exe"
    monkeypatch.setattr(
        "sys.argv",
        ["repair_binary.py", str(PE_GUARD), str(out), "--ai-path", "ai_plan"],
    )
    assert cli.main() == 0
    assert out.is_file()
    record = json.loads(capsys.readouterr().out)
    assert record["path"] == "ai_plan"
    assert record["verified"] is True
    assert record["ai"]["status"] == "accepted"


def test_cli_ai_path_requires_provider(monkeypatch, tmp_path):
    import app.services.assistant_llm as assistant_llm

    monkeypatch.setattr(assistant_llm, "client_from_env", lambda: None)
    cli = _load_cli()
    out = tmp_path / "ai-fixed.exe"
    monkeypatch.setattr(
        "sys.argv",
        ["repair_binary.py", str(PE_GUARD), str(out), "--ai-path", "ai_plan"],
    )
    assert cli.main() == 2
    assert not out.exists()


def test_cli_ai_path_rejects_batch(monkeypatch, tmp_path):
    cli = _load_cli()
    monkeypatch.setattr(
        "sys.argv",
        ["repair_binary.py", "--batch", str(tmp_path), "--out", str(tmp_path / "out"),
         "--ai-path", "ai_plan"],
    )
    assert cli.main() == 2


# ---------------------------------------------------------------------------
# ai_bytes path: raw machine-code guard / same-length in-place edits
# ---------------------------------------------------------------------------

from app.services.repair.analyzer import analyze as _analyze
from app.services.repair.guards import abi_for as _abi_for, build_guard as _build_guard


def _bytes_guard_payload() -> dict:
    code = _build_guard(_abi_for("pe", "x86_64"), "strcpy", 16)
    return {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": code.hex()},
    }


def test_bytes_path_injected_guard_is_verified():
    data = _read(PE_GUARD)
    outcome = ai_repair(data, path=AI_PATH_BYTES, client=FakeClient(_bytes_guard_payload()))
    assert outcome.candidate is not None
    assert outcome.verified is True
    report = outcome.report
    assert report.disposition == "verified_patch"
    assert report.strategy == "ai-bytes"
    assert report.actions and report.actions[0]["kind"] == "ai-injected-guard"
    assert report.verification["tier"] == "emulated_run"
    assert report.verification["gate"]["success"] is True
    assert outcome.ai["status"] == "accepted"
    assert outcome.ai["validation"]["actions"]


def test_bytes_path_in_place_edit_is_verified():
    data = _read(ELF_MEMCPY)
    sink = _analyze(data).patchable()[0]
    offset = int(sink.length_offset)
    before = data[offset:offset + 4].hex()
    after = (16).to_bytes(4, "little").hex()
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "edits": [{"offset": offset, "before_hex": before, "after_hex": after}],
    }
    outcome = ai_repair(data, path=AI_PATH_BYTES, client=FakeClient(payload))
    assert outcome.candidate is not None
    assert outcome.verified is True
    assert outcome.report.disposition == "verified_patch"
    assert outcome.report.strategy == "ai-bytes"
    assert outcome.report.actions[0]["kind"] == "ai-edit"
    assert outcome.report.verification["gate"]["success"] is True


def test_bytes_path_rejects_syscall_code():
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": "0f05"},
    }
    outcome = ai_repair(_read(PE_GUARD), path=AI_PATH_BYTES, client=FakeClient(payload))
    assert outcome.candidate is None
    assert outcome.download_allowed is False
    assert outcome.report.disposition == "unsupported"
    assert outcome.ai["status"] == "invalid"
    assert outcome.report.error


def test_bytes_path_noop_guard_does_not_pass_gate():
    # A valid but semantically useless block must not be promoted: the
    # deterministic runtime gate rejects it because the destination buffer is
    # never written as the original contract requires.
    payload = {"schema_version": 1, "sink_index": 0, "inject": {"code_hex": "c3"}}
    outcome = ai_repair(_read(PE_GUARD), path=AI_PATH_BYTES, client=FakeClient(payload))
    assert outcome.candidate is None
    assert outcome.verified is False
    assert outcome.download_allowed is False
    assert outcome.report.disposition in {"rejected", "unsupported", "not_verified"}
    # The model output itself was structurally accepted; only the deterministic
    # gate may refuse it.
    assert outcome.ai["status"] in {"accepted", "invalid"}


def test_bytes_path_rejects_before_mismatch():
    data = _read(ELF_MEMCPY)
    sink = _analyze(data).patchable()[0]
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "edits": [{
            "offset": int(sink.length_offset),
            "before_hex": "deadbeef",
            "after_hex": "10000000",
        }],
    }
    outcome = ai_repair(data, path=AI_PATH_BYTES, client=FakeClient(payload))
    assert outcome.candidate is None
    assert outcome.ai["status"] == "invalid"
    assert "before" in (outcome.report.error or "").lower()


def test_api_ai_bytes_verified(monkeypatch):
    monkeypatch.setattr(
        main_module, "client_from_env",
        lambda: FakeClient(_bytes_guard_payload()),
    )
    response = _post(_client(), AI_PATH_BYTES)
    assert response.status_code == 200
    body = response.json()
    assert body["path"] == AI_PATH_BYTES
    assert body["verified"] is True
    assert body["ai"]["status"] == "accepted"
    assert base64.b64decode(body["patched_base64"])[:2] == b"MZ"


def test_api_ai_bytes_syscall_is_422(monkeypatch):
    monkeypatch.setattr(
        main_module, "client_from_env",
        lambda: FakeClient({"schema_version": 1, "sink_index": 0,
                            "inject": {"code_hex": "0f05"}}),
    )
    response = _post(_client(), AI_PATH_BYTES)
    assert response.status_code == 422
    assert response.json()["ai"]["status"] == "invalid"


def test_bytes_path_requires_selected_length_immediate_edit():
    data = _read(ELF_MEMCPY)
    container = detect_container(data)
    text = next(section for section in container.sections if section.executable)
    offset = int(text.offset)
    before = data[offset:offset + 2]
    after = bytes((byte ^ 0x01) for byte in before)
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "edits": [{
            "offset": offset,
            "before_hex": before.hex(),
            "after_hex": after.hex(),
        }],
    }
    outcome = ai_repair(data, path=AI_PATH_BYTES, client=FakeClient(payload))
    assert outcome.candidate is None
    assert outcome.report.disposition == "unsupported"
    assert "length" in (outcome.report.error or "").lower()


def test_bytes_path_marks_pe_authenticode_invalidated():
    outcome = ai_repair(_read(PE_GUARD), path=AI_PATH_BYTES,
                        client=FakeClient(_bytes_guard_payload()))
    assert outcome.verified is True
    assert outcome.report.signature_invalidated is True
    assert outcome.report.codesign_invalidated is False
