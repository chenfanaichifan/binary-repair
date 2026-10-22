"""Dependency-free byte-audit primitives for Route A evidence.

These helpers compare the original and patched files at the byte level and are
used by the audit and the evidence bundle. They deliberately import nothing from
``pyelftools``/``capstone`` so they can be unit-tested without opening an ELF.

Rules (Gate 3, handoff 11 §3 item 2/3):

* every differing file byte must fall inside a declared interval;
* the bytes outside the declared intervals ("residue") must be identical in the
  original and the candidate;
* intervals are inclusive ``[start, end]`` pairs of zero-based file offsets and
  are merged when they touch, so a manifest cannot hide a gap.
"""

from __future__ import annotations

import hashlib


class ByteAuditError(ValueError):
    """Raised when a byte-level audit cannot be evaluated."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def changed_intervals(original: bytes, patched: bytes) -> list[tuple[int, int]]:
    """Return merged inclusive intervals of differing file offsets.

    ``ValueError`` when the files differ in length: a length change would move
    every following byte and cannot be expressed as a small edit set.
    """
    if len(original) != len(patched):
        raise ByteAuditError(
            f"length differs: original={len(original)} patched={len(patched)}"
        )
    intervals: list[tuple[int, int]] = []
    for offset, (a, b) in enumerate(zip(original, patched)):
        if a == b:
            continue
        if intervals and intervals[-1][1] + 1 == offset:
            intervals[-1] = (intervals[-1][0], offset)
        else:
            intervals.append((offset, offset))
    return intervals


def normalize_intervals(intervals) -> list[tuple[int, int]]:
    """Validate and merge a manifest's inclusive intervals."""
    parsed: list[tuple[int, int]] = []
    for item in intervals:
        if isinstance(item, dict):
            start, end = int(item["start"]), int(item["end"])
        else:
            start, end = int(item[0]), int(item[1])
        if start < 0 or end < start:
            raise ByteAuditError(f"invalid interval: {item!r}")
        parsed.append((start, end))
    parsed.sort()
    merged: list[tuple[int, int]] = []
    for start, end in parsed:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def intervals_as_dicts(intervals) -> list[dict]:
    return [
        {"start": start, "end": end, "size": end - start + 1}
        for start, end in normalize_intervals(intervals)
    ]


def off_interval_offsets(intervals, allowed: list[tuple[int, int]]) -> list[int]:
    """Return differing offsets outside the allowed set (sorted)."""
    allowed = normalize_intervals(allowed)
    outside: list[int] = []
    for start, end in intervals:
        for offset in range(start, end + 1):
            if not any(a <= offset <= b for a, b in allowed):
                outside.append(offset)
    return outside


def residue_sha256(original: bytes, patched: bytes, allowed) -> dict:
    """SHA-256 of the bytes that the edit claims not to touch.

    Returns both hashes and a ``match`` flag. Length differences are an error.
    """
    if len(original) != len(patched):
        raise ByteAuditError("cannot compare residue of differently sized files")
    allowed = normalize_intervals(allowed)
    keep_original = bytearray()
    keep_patched = bytearray()
    index = 0
    for start, end in allowed:
        keep_original += original[index:start]
        keep_patched += patched[index:start]
        index = end + 1
    keep_original += original[index:]
    keep_patched += patched[index:]
    left = sha256_bytes(bytes(keep_original))
    right = sha256_bytes(bytes(keep_patched))
    return {
        "original_residue_sha256": left,
        "patched_residue_sha256": right,
        "residue_bytes": len(keep_original),
        "match": left == right,
    }


def audit_changed_bytes(
    original: bytes,
    patched: bytes,
    declared_intervals,
) -> dict:
    """Full byte-level audit result for the edit manifest."""
    diffs = changed_intervals(original, patched)
    declared = normalize_intervals(declared_intervals)
    outside = off_interval_offsets(diffs, declared)
    residue = residue_sha256(original, patched, declared)
    return {
        "original_size": len(original),
        "patched_size": len(patched),
        "changed_intervals": intervals_as_dicts(diffs),
        "declared_intervals": intervals_as_dicts(declared),
        "changed_byte_count": sum(end - start + 1 for start, end in diffs),
        "outside_declared": [hex(offset) for offset in outside],
        "residue": residue,
        "pass": not outside and residue["match"] and len(original) == len(patched),
    }
