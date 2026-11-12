"""Settings, usage guide and task-management surfaces."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    client.get("/?token=" + SESSION_TOKEN)
    return client


def test_settings_page_exposes_all_controls_and_assets():
    page = _client().get("/settings")
    assert page.status_code == 200
    for marker in (
        'data-testid="settings-page"',
        'data-setting="density"',
        'data-setting="fontSize"',
        'data-setting="codeFont"',
        'data-setting="sendKey"',
        'data-setting="autoScroll"',
        'data-setting="historySync"',
        'data-setting="defaultWorkspace"',
        'data-setting="defaultMode"',
        'id="settings-clear-server"',
        "/static/js/settings.js",
        "/static/css/custom-select.css",
        "/static/js/custom-select.js",
        "data-lang-set=\"ja\"",
        "data-lang-set=\"ko\"",
        "data-lang-set=\"fr\"",
        "data-lang-set=\"it\"",
        "data-lang-set=\"pt\"",
        "data-lang-set=\"es\"",
        'name="csrf"',
    ):
        assert marker in page.text
    assert "跟随服务端默认" in page.text


def test_guide_is_complete_and_linked_from_the_sidebar():
    client = _client()
    guide = client.get("/guide")
    assert guide.status_code == 200
    for marker in (
        'data-testid="guide-page"',
        'id="start"',
        'id="code"',
        'id="binary"',
        'id="tasks"',
        'id="history"',
        'id="settings"',
        'id="connectors"',
        'id="methods"',
        'id="keys"',
        'id="trouble"',
    ):
        assert marker in guide.text
    assert "命令面板" in guide.text
    assert "Ctrl/Cmd" in guide.text
    assert "<svg" in guide.text
    assert "guide-table" in guide.text
    assert "guide-steps" in guide.text
    assert "guide-figure" in guide.text
    assert "https://cwe.mitre.org/" in guide.text
    for path in ("/agent", "/connectors", "/methods", "/settings"):
        page = client.get(path)
        assert page.status_code == 200
        assert 'href="/guide"' in page.text
        assert 'href="/settings"' in page.text


def test_task_management_and_composer_controls_are_shipped():
    client = _client()
    agent = client.get("/agent/new")
    assert 'id="ds-job-search"' in agent.text
    assert 'id="ds-workspace-button"' in agent.text
    assert 'id="ds-palette"' in agent.text
    assert "/static/js/palette.js" in agent.text
    js = client.get("/static/js/jobs-list.js").text
    assert "togglePin" in js
    assert "renameTask" in js
    assert "removeTask" in js
    assert "taskSort" in js
    assert 'id="ds-mobile-menu"' in agent.text
    assert 'id="ds-drawer-close"' in agent.text
    assert 'id="ds-lang-switch"' not in agent.text
    assert "data-lang-set=\"en\"" in agent.text
    i18n = client.get("/static/js/i18n-data.js").text
    assert "简体中文" in i18n and "繁體中文" in i18n and "日本語" in i18n
    assert "한국어" in i18n and "Français" in i18n and "Español" in i18n
    launch = client.get("/agent")
    assert 'data-testid="launch-card"' in launch.text
    assert 'data-launch-mode="live"' in launch.text
    assert 'data-launch-mode="demo"' in launch.text
    assert 'data-scenario="success"' in launch.text
    assert 'data-scenario="failure"' in launch.text
    agent_js = client.get("/static/js/agent.js").text
    assert 'id="agent-plus-menu"' in agent.text
    assert "loadTextFiles" in agent_js
    assert "data-plus" in agent_js
    assert "BRSettings" in agent_js
    settings_js = client.get("/static/js/settings.js").text
    assert "window.BRSettings" in settings_js
    assert "clearServerHistory" in settings_js
    assert "br.settings.v1" in settings_js


def test_clear_all_server_history_requires_csrf_and_clears(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_HISTORY_DB", str(tmp_path / "history.db"))
    client = _client()
    entries = [{"kind": "message", "role": "user", "text": "x", "at": "2026-01-01T00:00:00Z"}]
    saved = client.put(
        "/api/history/job-abc",
        json={"entries": entries},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert saved.status_code == 200
    assert client.delete("/api/history").status_code == 403
    cleared = client.delete("/api/history", headers={"X-CSRF-Token": CSRF_TOKEN})
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] == 1
    assert client.get("/api/history/job-abc").json()["entries"] == []
