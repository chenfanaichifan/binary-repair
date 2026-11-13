"""HTTP contract for the unified scan/repair pipeline."""
from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app

ROOT = Path(__file__).resolve().parents[1]
ELF = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"
PE_VULN = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def _post(client: TestClient, path: str, data: bytes, name: str, **extra):
    form = {"csrf": CSRF_TOKEN, **extra}
    return client.post(
        path,
        files={"binary": (name, data, "application/octet-stream")},
        data=form,
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


def test_matrix_endpoint_is_english_ascii():
    client = _client()
    response = client.get("/api/binary/matrix")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == 1
    assert len(payload["cells"]) == 8
    assert "verified_patch" in payload["dispositions"]
    assert response.text.isascii()


def test_repair_pe_reports_verified_disposition():
    client = _client()
    response = _post(client, "/api/binary/repair", PE_VULN.read_bytes(), "vuln.exe")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["verified"] is True
    assert payload["disposition"] == "verified_patch"
    assert payload["delivery"]["download_allowed"] is True
    assert payload["report"]["schema_version"] == 4
    assert base64.b64decode(payload["patched_base64"])[:2] == b"MZ"


def test_repair_static_only_requires_opt_in(monkeypatch):
    import app.services.binary_pipeline as pipeline

    monkeypatch.setattr(pipeline, "_select_runtime", lambda *args, **kwargs: None)
    client = _client()
    data = PE_VULN.read_bytes()
    refused = _post(client, "/api/binary/repair", data, "vuln.exe")
    assert refused.status_code == 422
    assert refused.json()["disposition"] == "not_verified"
    allowed = _post(client, "/api/binary/repair", data, "vuln.exe",
                    allow_static_only="1")
    assert allowed.status_code == 200
    payload = allowed.json()
    assert payload["ok"] is True
    assert payload["verified"] is False
    assert payload["disposition"] == "static_only_patch"
    assert payload["delivery"]["download_allowed"] is True
    assert payload["delivery"]["verified"] is False
