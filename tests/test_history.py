"""Server-side conversation history: store bounds and the authenticated API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from app.services.history import (
    HistoryConflict,
    MAX_ENTRIES,
    HistoryError,
    HistoryStore,
    normalize_entries,
    validate_scope,
)


def test_store_roundtrip(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    assert store.load("job-abc")["entries"] == []
    entries = [
        {"kind": "message", "role": "user", "text": "hello", "at": "2026-01-01T00:00:00Z"},
        {"kind": "tool", "name": "plan", "summary": "ok", "at": "2026-01-01T00:00:01Z"},
    ]
    saved = store.save("job-abc", entries)
    assert saved["storage"] == "server"
    assert saved["updated_at"]
    loaded = store.load("job-abc")
    assert loaded["entries"] == entries
    assert loaded["updated_at"] == saved["updated_at"]
    cleared = store.delete("job-abc")
    assert cleared["deleted"] is True
    assert cleared["generation"] == 1
    assert store.load("job-abc")["entries"] == []


def test_store_rejects_bad_scopes_and_payloads(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    for bad in ("", "../etc", "a/b", "x" * 65):
        try:
            validate_scope(bad)
        except HistoryError:
            pass
        else:  # pragma: no cover
            raise AssertionError(bad)
    try:
        normalize_entries("nope")
    except HistoryError:
        pass
    else:  # pragma: no cover
        raise AssertionError("list required")
    try:
        normalize_entries([{"kind": "message"}] * (MAX_ENTRIES + 1))
    except HistoryError:
        pass
    else:  # pragma: no cover
        raise AssertionError("limit")
    try:
        normalize_entries([{"kind": "unknown"}])
    except HistoryError:
        pass
    else:  # pragma: no cover
        raise AssertionError("kind")
    try:
        normalize_entries([{"kind": "message", "text": "x" * (600 * 1024)}])
    except HistoryError:
        pass
    else:  # pragma: no cover
        raise AssertionError("size")


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    assert client.get("/?token=" + SESSION_TOKEN).status_code == 200
    return client


def test_history_api_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_HISTORY_DB", str(tmp_path / "history.db"))
    client = _client()
    scope = "job-history-test"
    entries = [{"kind": "message", "role": "user", "text": "hi", "at": "2026-01-01T00:00:00Z"}]

    assert client.put(f"/api/history/{scope}", json={"entries": entries}).status_code == 403
    saved = client.put(
        f"/api/history/{scope}",
        json={"entries": entries},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert saved.status_code == 200
    assert saved.json()["entries"] == entries
    loaded = client.get(f"/api/history/{scope}")
    assert loaded.status_code == 200
    assert loaded.json()["entries"] == entries
    assert loaded.json()["storage"] == "server"
    assert (tmp_path / "history.db").exists()


def test_history_api_rejects_bad_scope_and_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_HISTORY_DB", str(tmp_path / "history.db"))
    client = _client()
    assert client.get("/api/history/-bad").status_code == 404
    response = client.put(
        "/api/history/job-bad",
        json={"entries": [{"kind": "nope"}]},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 422
    response = client.put(
        "/api/history/job-bad",
        json={"entries": "nope"},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert response.status_code == 422


def test_draft_scope_can_be_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_HISTORY_DB", str(tmp_path / "history.db"))
    client = _client()
    entries = [{"kind": "message", "role": "assistant", "text": "draft", "at": "2026-01-01T00:00:00Z"}]
    saved = client.put(
        "/api/history/draft",
        json={"entries": entries},
        headers={"X-CSRF-Token": CSRF_TOKEN},
    )
    assert saved.status_code == 200
    assert client.get("/api/history/draft").json()["entries"] == entries
    assert client.delete("/api/history/draft").status_code == 403
    cleared = client.delete("/api/history/draft", headers={"X-CSRF-Token": CSRF_TOKEN})
    assert cleared.status_code == 200
    assert cleared.json()["deleted"] is True
    assert client.get("/api/history/draft").json()["entries"] == []


def test_stale_generation_cannot_resurrect_a_cleared_draft(tmp_path):
    store = HistoryStore(tmp_path / "history.db")
    entries = [{"kind": "message", "role": "user", "text": "old", "at": "2026-01-01T00:00:00Z"}]
    first = store.save("draft", entries)
    assert first["generation"] == 0
    cleared = store.delete("draft")
    assert cleared["generation"] == 1
    try:
        store.save("draft", entries, 0)
    except HistoryConflict:
        pass
    else:  # pragma: no cover
        raise AssertionError("stale generation accepted")
    assert store.load("draft")["entries"] == []
