from __future__ import annotations

from pathlib import Path

from app.services.elf_mapping import MappingStatus, map_offset, map_va

ROOT = Path(__file__).resolve().parents[1]


def _elf() -> bytes:
    return (ROOT / "fixtures/repair-benchmark/CWE787_index_write/original.elf").read_bytes()


def test_known_file_backed_va_maps_to_offset_and_back() -> None:
    data = _elf()
    mapping = map_va(data, 0x401000)
    assert mapping.status is MappingStatus.MAPPED_FILE_BACKED
    assert mapping.file_offset is not None
    reverse = map_offset(data, mapping.file_offset)
    assert reverse.status is MappingStatus.MAPPED_FILE_BACKED
    assert reverse.va == 0x401000


def test_unmapped_va_fails_closed() -> None:
    assert map_va(_elf(), 0xDEAD0000).status is MappingStatus.OUTSIDE_PT_LOAD


def test_out_of_file_offset_fails_closed() -> None:
    assert map_offset(_elf(), 10**9).status is MappingStatus.INVALID_FILE_RANGE
