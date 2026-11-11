"""Theme switch and the single-intake contract.

The console is the only way to create a repair job. The form intake is retired
and must not reappear through a template, a static asset, or the landing page.
"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import SESSION_TOKEN, app

ROOT = Path(__file__).resolve().parents[1]
LANDING = (ROOT / "app/templates/landing.html").read_text(encoding="utf-8")
BASE = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
THEME_JS = (ROOT / "app/static/js/theme.js").read_text(encoding="utf-8")
DS_CSS = (ROOT / "app/static/css/ds.css").read_text(encoding="utf-8")
HOME_CSS = (ROOT / "app/static/css/home.css").read_text(encoding="utf-8")

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200


def test_theme_switch_has_three_states_and_prepaint_boot():
    page = client.get("/")
    for pref in ("light", "dark", "system"):
        assert f'data-theme-set="{pref}"' in page.text
    assert 'data-theme="' not in page.text  # set by script, not hardcoded
    assert "br.theme" in page.text
    assert "/static/js/theme.js" in page.text
    assert 'data-theme-set="system"' in client.get("/agent/new").text


def test_theme_script_follows_the_system_and_persists_choice():
    assert 'matchMedia("(prefers-color-scheme: dark)")' in THEME_JS
    assert 'localStorage.setItem(KEY, pref)' in THEME_JS
    assert 'setAttribute("data-theme", theme)' in THEME_JS
    assert ":root[data-theme=\"dark\"]" in DS_CSS
    assert ":root[data-theme=\"dark\"] .ds-home-body" in HOME_CSS


def test_console_is_the_only_intake():
    landing = client.get("/")
    for copy in ("表单建单", "使用表单上传", "/jobs/new"):
        assert copy not in landing.text
    agent = client.get("/agent/new")
    assert "改用表单建单" not in agent.text
    assert "agent-switch-form" not in agent.text
    index = client.get("/agent")
    assert "用表单创建" not in index.text
    assert "agent-start-form" not in index.text
    # Old links keep working, but only as a redirect to the console.
    redirect = client.get("/jobs/new", follow_redirects=False)
    assert redirect.status_code == 303
    assert redirect.headers["location"] == "/agent/new?new=1"


def test_retired_form_assets_are_gone():
    for path in ("/static/css/setup-handdrawn.css", "/static/js/setup-wizard.js"):
        assert client.get(path).status_code == 404, path
    assert not (ROOT / "app/templates/setup.html").exists()
