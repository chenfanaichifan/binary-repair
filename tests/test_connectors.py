"""Connector inventory and the declarative plugin interface.

The registry is read-only: it must report configuration without leaking
credentials, and it must never execute a manifest.
"""

import json

from fastapi.testclient import TestClient

from app.main import SESSION_TOKEN, app
from app.services.connectors import DEFAULT_PLUGIN_DIR, connector_snapshot

CJK = __import__("re").compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef]")


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    client.get("/?token=" + SESSION_TOKEN)
    return client


def test_snapshot_reports_the_builtin_connectors_without_secrets(monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_ASSISTANT_PROVIDER_KEY", "sk-secret-value")
    monkeypatch.delenv("BINARYREPAIR_PLUGIN_DIR", raising=False)
    snapshot = connector_snapshot()
    ids = [row["id"] for row in snapshot["connectors"]]
    assert ids[0] == "assistant"
    assert ids[-1] == "plugins"
    for expected in ("assistant", "controller", "workspace", "plugins", "mcp", "git",
                     "webhook", "artifacts", "ghidra", "rizin", "angr", "frida"):
        assert expected in ids
    categories = {row["category"] for row in snapshot["connectors"]}
    assert categories == {"model", "analysis", "workflow", "storage", "plugin"}
    assert snapshot["counts"]["total"] == len(ids)
    blob = json.dumps(snapshot)
    assert "sk-secret-value" not in blob
    assert snapshot["plugin_dir_source"] in {"default", "env"}


def test_plugin_manifests_are_inert_and_validated(tmp_path, monkeypatch):
    good = tmp_path / "review.json"
    good.write_text(json.dumps({
        "id": "review-hook",
        "name": "Review hook",
        "kind": "connector",
        "description": "Posts a review comment when a bundle is exported.",
        "enabled": True,
    }), encoding="utf-8")
    bad = tmp_path / "broken.json"
    bad.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("BINARYREPAIR_PLUGIN_DIR", str(tmp_path))

    snapshot = connector_snapshot()
    assert [plugin["id"] for plugin in snapshot["plugins"]] == ["review-hook"]
    assert snapshot["plugin_dir_source"] == "env"
    assert snapshot["warnings"] and "broken.json" in snapshot["warnings"][0]


def test_plugin_loader_counts_default_directory(monkeypatch):
    monkeypatch.delenv("BINARYREPAIR_PLUGIN_DIR", raising=False)
    snapshot = connector_snapshot()
    loader = next(row for row in snapshot["connectors"] if row["id"] == "plugins")
    assert loader["status"] == "ready"
    assert DEFAULT_PLUGIN_DIR == "plugins"


def test_connectors_api_is_ascii_and_never_echoes_a_key(monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_ASSISTANT_PROVIDER_KEY", "sk-should-not-appear")
    response = _client().get("/api/connectors")
    assert response.status_code == 200
    assert "sk-should-not-appear" not in response.text
    assert not CJK.search(response.text)
    payload = response.json()
    assert {row["id"] for row in payload["connectors"]} >= {"assistant", "controller", "plugins"}


def test_connectors_page_renders_cards_and_the_plugin_panel():
    response = _client().get("/connectors")
    assert response.status_code == 200
    assert 'data-testid="connectors-page"' in response.text
    assert 'data-testid="connector-assistant"' in response.text
    assert 'data-testid="plugin-panel"' in response.text
    assert "插件（与连接器分开）" in response.text
    assert 'data-testid="connector-ghidra"' in response.text
    assert 'data-testid="connector-angr"' in response.text
    assert 'data-testid="plugin-ghidra-export"' in response.text
    assert "接入四步" in response.text
    assert "官方文档" in response.text
