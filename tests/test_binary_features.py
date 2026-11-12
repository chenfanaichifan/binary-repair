"""Static binary feature extraction: missing/unsupported inputs stay explicit."""
from pathlib import Path

import pytest

from app.services.binary_features import extract_features


def test_missing_file_is_an_error():
    with pytest.raises(FileNotFoundError):
        extract_features("/definitely/not/here")


def test_non_binary_is_reported_not_parsed_as_elf(tmp_path):
    path = tmp_path / "not-a-binary"
    path.write_bytes(b"hello")
    payload = extract_features(path)
    assert payload["format"] is None
    assert payload["sha256"]
    assert payload["size"] == 5
