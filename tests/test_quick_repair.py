"""One-click ELF repair: bounded read and downloadable patched ELF."""
from __future__ import annotations

import base64
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from app.services import binary_repair_engine as engine
from app.services.binary_quick_repair import QuickRepairError, quick_repair_elf

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"


def test_quick_repair_bounds_read_and_write():
    original = VULN.read_bytes()
    patched, report = quick_repair_elf(original)
    assert report.capacity == 16
    assert report.mode == "strict"
    assert report.original_sha256 != report.patched_sha256
    assert bytes(patched) != original
    assert b"input too long" in patched
    assert b"\xba\x11\x00\x00\x00" in patched  # read 17 bytes for detection


def test_quick_repair_api_returns_download():
    client = TestClient(app, base_url="http://127.0.0.1")
    client.get("/?token=" + SESSION_TOKEN)
    response = client.post(
        "/api/binary/quick-repair",
        files={"binary": ("vuln.elf", VULN.read_bytes(), "application/octet-stream")},
        data={"csrf": CSRF_TOKEN},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert base64.b64decode(payload["patched_base64"])[:4] == b"\x7fELF"
    assert payload["report"]["capacity"] == 16
    assert payload["report"]["mode"] == "strict"


def test_quick_repair_fails_closed_without_runtime_evidence(monkeypatch):
    monkeypatch.setattr(
        engine,
        "_runtime_summary",
        lambda patched, capacity: {"available": False, "error": "simulated evidence gap"},
    )
    with pytest.raises(QuickRepairError, match="verification did not pass"):
        quick_repair_elf(VULN.read_bytes())


def test_quick_repair_api_fails_closed_without_runtime_evidence(monkeypatch):
    monkeypatch.setattr(
        engine,
        "_runtime_summary",
        lambda patched, capacity: {"available": False, "error": "simulated evidence gap"},
    )
    client = TestClient(app, base_url="http://127.0.0.1")
    client.get("/?token=" + SESSION_TOKEN)
    response = client.post(
        "/api/binary/quick-repair",
        files={"binary": ("vuln.elf", VULN.read_bytes(), "application/octet-stream")},
        data={"csrf": CSRF_TOKEN},
    )
    assert response.status_code == 422
    assert "verification did not pass" in response.json()["detail"].lower()


def test_quick_repair_rejects_non_elf():
    client = TestClient(app, base_url="http://127.0.0.1")
    client.get("/?token=" + SESSION_TOKEN)
    response = client.post(
        "/api/binary/quick-repair",
        files={"binary": ("x.bin", b"hello", "application/octet-stream")},
        data={"csrf": CSRF_TOKEN},
    )
    assert response.status_code == 422
    assert "not an elf" in response.json()["detail"].lower()
