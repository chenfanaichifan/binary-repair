"""CGC inventory: paired challenge binaries, no execution."""
from pathlib import Path

from app.services.binary_datasets import inventory_cgc


def _bin(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x7fELF" + body)


def test_cgc_pairs_challenge_and_patched(tmp_path):
    _bin(tmp_path / "challenges" / "Demo" / "Demo", b"vuln")
    _bin(tmp_path / "challenges" / "Demo" / "Demo_patched", b"patch")
    payload = inventory_cgc(tmp_path)
    assert payload["available"] is True
    assert payload["counts"] == {"binaries": 2, "challenges": 1, "paired": 1}
    assert payload["pairs"][0]["paired"] is True
    assert payload["records"][0]["dataset"] == "cgc"


def test_cgc_missing_root_is_unknown(tmp_path):
    payload = inventory_cgc(tmp_path / "missing")
    assert payload["available"] is False
    assert payload["reason"] == "root_not_found"
