"""HTTP contract for the unified scan/repair pipeline."""
from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def _post(client: TestClient, path: str, data: bytes, name: str):
    return client.post(
        path,
        files={"binary": (name, data, "application/octet-stream")},
        data={"csrf": CSRF_TOKEN},
    )


def test_scan_endpoint_reports_all_formats():
    client = _client()
    for path, name, fmt in (
        (ELF, "vuln.elf", "elf"),
        (PE, "cli.exe", "pe"),
    ):
        response = _post(client, "/api/binary/scan", path.read_bytes(), name)
        assert response.status_code == 200
        assert response.json()["scan"]["format"] == fmt


def test_repair_endpoint_returns_downloadable_elf():
    client = _client()
    response = _post(client, "/api/binary/repair", ELF.read_bytes(), "vuln.elf")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["report"]["status"] == "patched"
    assert payload["report"]["format"] == "elf"
    assert base64.b64decode(payload["patched_base64"])[:4] == b"\x7fELF"


def test_repair_endpoint_fails_closed_for_unsupported_pe():
    client = _client()
    response = _post(client, "/api/binary/repair", PE.read_bytes(), "cli.exe")
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["report"]["candidate_available"] is False
    assert payload["report"]["status"] == "unsupported"


def test_scan_endpoint_rejects_unknown_input():
    client = _client()
    response = _post(client, "/api/binary/scan", b"not a binary", "x.bin")
    assert response.status_code == 422
    assert response.json()["ok"] is False
