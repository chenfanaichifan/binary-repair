"""Universal binary repair page (/binary) and its HTTP contract.

The page copy is Simplified Chinese; API payloads and exports stay English
ASCII.  The static-only case is reproduced deterministically by disabling the
native Mach-O runtime: the deterministic gate then reports ``inconclusive``
rather than ``rejected``, which is exactly the opt-in best-effort path.
"""

from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app

ROOT = Path(__file__).resolve().parents[1]
ELF_X86_64 = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
MACHO_X86_64 = ROOT / "fixtures" / "macho" / "vuln-strcpy-x86_64"

TESTIDS = (
    "binary-page",
    "binary-file",
    "binary-scan",
    "binary-repair",
    "binary-allow-static",
    "binary-disposition",
    "binary-download",
    "binary-report",
    "binary-error",
)


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def _post(client: TestClient, path: str, *, data: bytes, name: str, extra: dict[str, str] | None = None):
    form = {"csrf": CSRF_TOKEN}
    form.update(extra or {})
    return client.post(
        path,
        files={"binary": (name, data, "application/octet-stream")},
        data=form,
    )


def test_binary_page_renders_chinese_ui_testids_and_assets():
    page = _client().get("/binary")
    assert page.status_code == 200
    for testid in TESTIDS:
        assert f'data-testid="{testid}"' in page.text, testid
    for marker in (
        "任意二进制修复",
        "允许未验证候选",
        "确定性矩阵",
        "AI 不参与判定",
        "边界说明",
        "/static/js/binary.js",
        "/static/css/binary.css",
        "/api/binary/matrix",
        'name="csrf"',
        'data-csrf="',
    ):
        assert marker in page.text, marker
    # Server-rendered coverage keeps the English-ASCII matrix identifiers.
    assert "elf/x86_64/64/little" in page.text
    assert "verified_patch" in page.text
    assert "static_only_patch" in page.text


def test_sidebar_links_to_binary_page_from_shell_pages():
    client = _client()
    for path in ("/guide", "/methods", "/settings", "/connectors", "/agent"):
        page = client.get(path)
        assert page.status_code == 200, path
        assert 'href="/binary"' in page.text, path
        assert 'data-testid="sidebar-binary"' in page.text, path


def test_binary_assets_are_served_and_js_keeps_user_data_out_of_html():
    client = _client()
    js = client.get("/static/js/binary.js")
    assert js.status_code == 200
    for marker in (
        "/api/binary/scan",
        "/api/binary/repair",
        "allow_static_only",
        "download_allowed",
        "patched_base64",
        "disposition",
        "Blob",
        "textContent",
    ):
        assert marker in js.text, marker
    # A user-controlled filename must never be interpolated into HTML.
    assert "innerHTML" not in js.text
    css = client.get("/static/css/binary.css")
    assert css.status_code == 200
    assert ".binary-badge" in css.text
    assert ".binary-drop" in css.text


def test_i18n_overrides_cover_the_binary_page():
    js = _client().get("/static/js/i18n-curated-extra.js")
    assert js.status_code == 200
    for marker in ("任意二进制修复", "未验证，仅静态证据", "确定性矩阵", "边界说明"):
        assert marker in js.text, marker
    assert "Repair any binary" in js.text


def test_agent_quick_repair_panel_offers_optional_poc_manifest():
    """The quick-repair card exposes an optional PoC manifest picker.

    The review card is rendered by ``agent.js`` (not the Jinja template), so the
    contract is checked on the served script: a visible Chinese label, an
    ``.json`` file input with a stable testid, a conditional FormData append, and
    display-only strategy/runtime chips.  No new verdict logic is asserted here:
    success still comes from ``payload.decision.success``.
    """
    client = _client()
    page = client.get("/agent/new")
    assert page.status_code == 200
    assert "/static/js/agent.js" in page.text
    js = client.get("/static/js/agent.js")
    assert js.status_code == 200
    for marker in (
        "agent-poc-manifest",
        "PoC / 回归用例清单（可选，JSON）",
        "pocInput.accept",
        ".json,application/json",
        'form.append("poc_manifest"',
        "if (state.pocManifest)",
        "策略 capacity-check",
        "verification.scope",
        "运行时 ",
        "runtime.evidence",
    ):
        assert marker in js.text, marker
    # The optional manifest must not become a required field and must not drive
    # the verdict.
    assert "var success = decision.success === true;" in js.text


def test_matrix_api_is_english_ascii():
    response = _client().get("/api/binary/matrix")
    assert response.status_code == 200
    cjk = [char for char in response.text if "\u4e00" <= char <= "\u9fff"]
    assert not cjk, cjk[:10]
    payload = response.json()
    assert payload["cells"]
    assert payload["sink_classes"]
    assert payload["non_goals"]
    assert "verified_patch" in payload["dispositions"]
    assert "static_only_patch" in payload["dispositions"]


def test_scan_returns_matrix_findings_and_limitations():
    response = _post(
        _client(), "/api/binary/scan", data=ELF_X86_64.read_bytes(), name="vuln.elf"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    scan = payload["scan"]
    assert scan["format"] == "elf"
    assert scan["arch"] == "x86_64"
    assert scan["bits"] == 64
    assert scan["endian"] == "little"
    assert scan["matrix"]["cell"] == "elf/x86_64/64/little"
    assert scan["matrix"]["repairable"] is True
    assert scan["findings"]
    assert isinstance(scan["limitations"], list)


def test_verified_repair_returns_downloadable_candidate():
    response = _post(
        _client(), "/api/binary/repair", data=ELF_X86_64.read_bytes(), name="vuln.elf"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["verified"] is True
    assert payload["disposition"] == "verified_patch"
    delivery = payload["delivery"]
    assert delivery["download_allowed"] is True
    assert delivery["verified"] is True
    assert delivery["tier"] in {"emulated_run", "native_run"}
    assert payload["filename"].endswith(".elf")
    assert isinstance(payload["report"], dict)
    assert isinstance(payload["warnings"], list)
    assert base64.b64decode(payload["patched_base64"])[:4] == b"\x7fELF"


def test_static_only_repair_is_unverified_but_downloadable(monkeypatch):
    monkeypatch.setattr("app.services.runtime.macho_native.available", lambda: False)
    response = _post(
        _client(),
        "/api/binary/repair",
        data=MACHO_X86_64.read_bytes(),
        name="vuln.macho",
        extra={"allow_static_only": "1"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["verified"] is False
    assert payload["disposition"] == "static_only_patch"
    delivery = payload["delivery"]
    assert delivery["download_allowed"] is True
    assert delivery["verified"] is False
    assert delivery["tier"] == "static_only"
    assert payload["warnings"]
    assert payload["filename"].endswith(".macho")
    # 64-bit little-endian Mach-O magic: the bytes are really the patched container.
    assert base64.b64decode(payload["patched_base64"])[:4] == b"\xcf\xfa\xed\xfe"


def test_repair_without_static_opt_in_fails_closed(monkeypatch):
    monkeypatch.setattr("app.services.runtime.macho_native.available", lambda: False)
    response = _post(
        _client(), "/api/binary/repair", data=MACHO_X86_64.read_bytes(), name="vuln.macho"
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["disposition"] == "not_verified"
    assert payload["report"]["delivery"]["download_allowed"] is False
    assert "patched_base64" not in payload


def test_repair_rejects_unrecognised_input_with_english_ascii_payload():
    response = _post(
        _client(), "/api/binary/repair", data=b"not a binary container", name="sample.bin"
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["disposition"] == "invalid"
    assert payload["report"]["disposition"] == "invalid"
