"""CGC inventory: paired challenge binaries, no execution."""
import struct
from pathlib import Path

from app.services.binary_datasets import inventory_cgc


def _elf64(path: Path, machine: int = 62) -> None:
    """Minimal 64-bit little-endian ELF header (enough for format detection)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    head = b"\x7fELF" + b"\x02\x01\x01" + b"\x00" * 9
    head += struct.pack("<H", 2) + struct.pack("<H", machine)
    head += b"\x00" * 44
    path.write_bytes(head)


def _macho64(path: Path, cputype: int = 0x0100000C) -> None:
    """Minimal 64-bit little-endian Mach-O header (arm64 by default)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    head = b"\xcf\xfa\xed\xfe" + struct.pack("<I", cputype) + b"\x00" * 24
    path.write_bytes(head)


def test_cgc_pairs_challenge_and_patched(tmp_path):
    _elf64(tmp_path / "challenges" / "Demo" / "Demo")
    _elf64(tmp_path / "challenges" / "Demo" / "Demo_patched")
    payload = inventory_cgc(tmp_path)
    assert payload["available"] is True
    assert payload["counts"] == {
        "binaries": 2,
        "challenges": 1,
        "paired": 1,
        "formats": ["elf"],
        "repair_supported": 2,
    }
    assert payload["pairs"][0]["paired"] is True
    assert payload["records"][0]["dataset"] == "cgc"
    assert payload["records"][0]["arch"] == "x86_64"
    assert payload["records"][0]["repair_supported"] is True


def test_cgc_macho_pair_is_not_repair_supported(tmp_path):
    _macho64(tmp_path / "challenges" / "Demo" / "Demo")
    _macho64(tmp_path / "challenges" / "Demo" / "Demo_patched")
    payload = inventory_cgc(tmp_path)
    assert payload["counts"] == {
        "binaries": 2,
        "challenges": 1,
        "paired": 1,
        "formats": ["macho"],
        "repair_supported": 0,
    }
    record = payload["records"][0]
    assert record["format"] == "macho"
    assert record["arch"] == "arm64"
    assert record["repair_supported"] is False


def test_cgc_missing_root_is_unknown(tmp_path):
    payload = inventory_cgc(tmp_path / "missing")
    assert payload["available"] is False
    assert payload["reason"] == "root_not_found"
