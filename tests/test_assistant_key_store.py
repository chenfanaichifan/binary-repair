from __future__ import annotations

import os
from pathlib import Path

from app.services import assistant_key_store


def test_key_round_trip_is_masked_and_removable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BINARYREPAIR_ASSISTANT_KEY_FILE", str(tmp_path / "assistant.key"))
    monkeypatch.delenv("BINARYREPAIR_ASSISTANT_PROVIDER_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    raw_key = "sk-test-0123456789abcdef"
    saved = assistant_key_store.save_key(raw_key)
    assert saved["configured"] is True
    assert assistant_key_store.load_key() == raw_key

    raw = (tmp_path / "assistant.key").read_bytes()
    assert raw_key.encode() not in raw

    status = assistant_key_store.key_status()
    assert status["configured"] is True
    assert status["source"] == "stored"
    assert status["masked"] != raw_key
    assert raw_key not in status["masked"]
    assert status["can_clear"] is True

    assert assistant_key_store.clear_key() is True
    assert assistant_key_store.load_key() == ""
    assert assistant_key_store.key_status()["configured"] is False


def test_environment_key_wins_and_cannot_be_cleared(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BINARYREPAIR_ASSISTANT_KEY_FILE", str(tmp_path / "assistant.key"))
    monkeypatch.setenv("BINARYREPAIR_ASSISTANT_PROVIDER_KEY", "sk-env-0123456789")
    assistant_key_store.save_key("sk-stored-0123456789")
    status = assistant_key_store.key_status()
    assert status["source"] == "environment"
    assert status["can_clear"] is False


def test_mask_reveals_only_last_four() -> None:
    key = "sk-abcdefghijklmnopqrstuvwxyz1234"
    masked = assistant_key_store.mask_key(key)
    assert masked.endswith(key[-4:])
    assert key[:4] not in masked
    assert masked.count("*") == len(key) - 4


def test_short_and_non_ascii_keys_are_rejected(tmp_path, monkeypatch) -> None:
    import pytest
    monkeypatch.setenv("BINARYREPAIR_ASSISTANT_KEY_FILE", str(tmp_path / "assistant.key"))
    with pytest.raises(ValueError):
        assistant_key_store.save_key("short")
    with pytest.raises(ValueError):
        assistant_key_store.save_key("sk-abcdefghijklmnop\u0000")


def test_stale_temp_file_does_not_block_save(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BINARYREPAIR_ASSISTANT_KEY_FILE", str(tmp_path / "assistant.key"))
    (tmp_path / "assistant.key.tmp").write_text("stale", encoding="utf-8")
    assistant_key_store.save_key("sk-stale-0123456789abcdef")
    assert assistant_key_store.load_key() == "sk-stale-0123456789abcdef"


def test_literal_secret_names_and_windows_aliases_are_rejected() -> None:
    from pathlib import Path
    for name in ("assistant.key", "ASSISTANT.KEY", "assistant.key.", "assistant.key ",
                 "assistant.key::$DATA", ".env", ".env.", "session.token",
                 "SESSION.TOKEN ", "session.token::$DATA"):
        assert assistant_key_store.is_secret_file(Path(name)), name
