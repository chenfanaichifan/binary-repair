"""Dependency-free tests for the Route A byte-audit primitives.

These tests use synthetic bytes only: they never open, parse, or execute the
fixture ELF, so they can run wherever Python runs. The ELF-dependent Route A
tests live in ``test_routea_cave.py`` and must run in the guest (handoff 13 §5).
"""

from __future__ import annotations

import pytest

from routea.byteaudit import (
    ByteAuditError,
    audit_changed_bytes,
    changed_intervals,
    intervals_as_dicts,
    off_interval_offsets,
    residue_sha256,
    sha256_bytes,
)


def test_changed_intervals_merge_adjacent_offsets() -> None:
    original = bytes(range(16))
    patched = bytearray(original)
    patched[3] = 0xFF
    patched[4] = 0xEE
    patched[10] = 0x00
    assert changed_intervals(original, bytes(patched)) == [(3, 4), (10, 10)]


def test_changed_intervals_rejects_length_change() -> None:
    with pytest.raises(ByteAuditError):
        changed_intervals(b"abc", b"abcd")


def test_intervals_are_inclusive_and_merged() -> None:
    assert intervals_as_dicts([(0, 1), (2, 3), (9, 9)]) == [
        {"start": 0, "end": 3, "size": 4},
        {"start": 9, "end": 9, "size": 1},
    ]


def test_off_interval_offsets_finds_undeclared_byte() -> None:
    outside = off_interval_offsets([(0, 1), (8, 8)], [(0, 1)])
    assert outside == [8]


def test_residue_matches_when_edits_are_declared() -> None:
    original = b"abcdefgh"
    patched = b"abcXefgh"
    result = residue_sha256(original, patched, [(3, 3)])
    assert result["match"] is True
    assert result["original_residue_sha256"] == result["patched_residue_sha256"]


def test_residue_rejects_length_change() -> None:
    with pytest.raises(ByteAuditError):
        residue_sha256(b"abc", b"ab", [])


def test_audit_changed_bytes_passes_inside_declared_intervals() -> None:
    original = b"0123456789"
    patched = b"012345678X"
    result = audit_changed_bytes(original, patched, [(9, 9)])
    assert result["pass"] is True
    assert result["outside_declared"] == []
    assert result["changed_intervals"] == [{"start": 9, "end": 9, "size": 1}]


def test_audit_changed_bytes_fails_outside_declared_intervals() -> None:
    original = b"0123456789"
    patched = b"01X345678X"
    result = audit_changed_bytes(original, patched, [(9, 9)])
    assert result["pass"] is False
    assert result["outside_declared"] == ["0x2"]


def test_sha256_bytes_is_stable() -> None:
    assert sha256_bytes(b"") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
