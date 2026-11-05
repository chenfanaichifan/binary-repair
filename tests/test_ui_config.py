"""The landing selectors are configuration-driven, not decorative.

The page must render whatever catalogue the backend exposes, pass the choice on
to the console, and never trust an unknown id.
"""

import json

from fastapi.testclient import TestClient

from app import ui_config
from app.main import SESSION_TOKEN, app

client = TestClient(app, base_url="http://127.0.0.1")
assert client.get("/?token=" + SESSION_TOKEN).status_code == 200


def test_config_endpoint_shape():
    data = client.get("/api/ui-config").json()
    assert data["source"] == "builtin"
    assert {item["id"] for item in data["workspaces"]} >= {"local"}
    assert {item["id"] for item in data["modes"]} == {"standard", "demo"}
    assert data["defaults"]["workspace"] in {item["id"] for item in data["workspaces"]}
    assert data["defaults"]["mode"] in {item["id"] for item in data["modes"]}


def test_landing_renders_options_from_config():
    page = client.get("/")
    assert page.status_code == 200
    assert 'data-select="workspace"' in page.text
    assert 'data-select="mode"' in page.text
    assert 'name="workspace"' in page.text
    assert 'name="mode"' in page.text
    assert 'data-testid="landing-agent-cta"' in page.text


def test_file_source_overrides_defaults(tmp_path, monkeypatch):
    payload = {
        "workspaces": [{"id": "lab", "label": "实验室工作区", "detail": "内网只读"}],
        "modes": [{"id": "strict", "label": "严格模式", "detail": "双跑复核"}],
        "defaults": {"workspace": "lab", "mode": "strict"},
    }
    path = tmp_path / "ui.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("BINARYREPAIR_UI_CONFIG", str(path))

    data = ui_config.load_ui_config()
    assert data["source"].endswith("ui.json")
    assert data["defaults"] == {"workspace": "lab", "mode": "strict"}

    page = client.get("/")
    assert "实验室工作区" in page.text
    assert "严格模式" in page.text
    assert 'value="lab"' in page.text


def test_broken_file_falls_back_to_builtin(tmp_path, monkeypatch):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("BINARYREPAIR_UI_CONFIG", str(path))
    assert ui_config.load_ui_config()["source"] == "builtin"


def test_unknown_selection_falls_back_to_default():
    page = client.get("/agent/new?workspace=nope&mode=nope")
    assert page.status_code == 200
    assert 'data-workspace="local"' in page.text
    assert 'data-mode="standard"' in page.text


def test_demo_mode_enables_fixture_and_records_the_choice():
    page = client.get("/agent/new?mode=demo")
    assert 'data-fixture="1"' in page.text
    assert 'data-mode="demo"' in page.text
    assert 'data-testid="agent-workspace-chip"' in page.text
