"""Local session and CSRF guard tests (Technical Design section 11)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app

FORM = {
    "defect": "strcpy in stack_buf does not check length; overlong input writes out of bounds",
    "valid_tests": "valid: hello",
    "environment": "Ubuntu x86-64 VM (test)",
    "valid_domain": "Input length 0-64 bytes",
    "forbidden": "Out-of-bounds write",
    "invalid_outcome": "Return error code 1",
    "assumptions": "Single process",
}


def _client() -> TestClient:
    return TestClient(app, base_url="http://127.0.0.1")


def test_healthz_is_public_but_pages_require_a_session():
    client = _client()
    assert client.get("/agent/new").status_code == 401
    assert client.get("/healthz").status_code == 200
    assert client.get("/?token=wrong-token").status_code == 401

    bootstrapped = _client()
    assert bootstrapped.get("/?token=" + SESSION_TOKEN).status_code == 200
    assert bootstrapped.get("/agent/new").status_code == 200


def test_unauthenticated_browser_gets_a_help_page():
    client = _client()
    response = client.get("/agent/new", headers={"accept": "text/html"})
    assert response.status_code == 401
    assert "需要本地会话" in response.text
    # The unauthenticated response must never hand out the session credential.
    assert SESSION_TOKEN not in response.text
    assert "?token=" not in response.text


def test_unauthenticated_pages_never_embed_the_session_token():
    client = _client()
    for path in ("/", "/agent/new", "/agent"):
        response = client.get(path, headers={"accept": "text/html"})
        assert response.status_code == 401, path
        assert SESSION_TOKEN not in response.text, path
        assert "session.token" in response.text or "start.ps1" in response.text, path


def test_csrf_token_is_required_for_post_forms():
    client = _client()
    client.get("/?token=" + SESSION_TOKEN)

    missing = client.post(
        "/jobs",
        data=FORM,
        files={"binary": ("sample.bin", b"\x7fELF demo", "application/octet-stream")},
        follow_redirects=False,
    )
    assert missing.status_code == 403
    assert "CSRF" in missing.json()["detail"]

    accepted = client.post(
        "/jobs",
        data={**FORM, "csrf": CSRF_TOKEN},
        files={"binary": ("sample.bin", b"\x7fELF demo", "application/octet-stream")},
        follow_redirects=False,
    )
    assert accepted.status_code == 303


def test_cross_origin_post_is_rejected():
    client = _client()
    client.get("/?token=" + SESSION_TOKEN)

    rejected = client.post(
        "/jobs",
        data={**FORM, "csrf": CSRF_TOKEN},
        files={"binary": ("sample.bin", b"\x7fELF demo", "application/octet-stream")},
        headers={"origin": "http://evil.example"},
        follow_redirects=False,
    )
    assert rejected.status_code == 403
    assert "Cross-origin" in rejected.json()["detail"]


def test_token_bootstrap_preserves_query_intent():
    """The one redirect that sets the cookie must not drop new/q/workspace."""
    response = _client().get(
        "/agent/new?new=1&workspace=local&q=hello&token=" + SESSION_TOKEN,
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("/agent/new?")
    assert "new=1" in location
    assert "workspace=local" in location
    assert "q=hello" in location
    assert "token=" not in location
    assert response.cookies.get("br_session") == SESSION_TOKEN


def test_host_allowlist_can_be_extended_for_lan_or_tunnel(monkeypatch):
    from app.main import _host_allowed

    assert _host_allowed("127.0.0.1")
    assert not _host_allowed("evil.example")
    monkeypatch.setenv("BINARYREPAIR_ALLOW_TUNNEL", "1")
    assert _host_allowed("demo.ngrok-free.dev")
    assert _host_allowed("demo.ngrok-free.app")
    assert not _host_allowed("evil.example")
