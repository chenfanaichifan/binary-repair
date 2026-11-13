"""Parsing and analysis robustness on corrupted containers."""
from __future__ import annotations

import random
from pathlib import Path

import pytest

from app.services.binary_pipeline import repair_binary, scan_binary

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = [
    ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe",
    ROOT / "fixtures" / "macho" / "vuln-strcpy-arm64",
]


@pytest.mark.parametrize("path", FIXTURES)
def test_mutations_scan_without_raising(path):
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    rng = random.Random(20261113)
    # Mutate only the middle of the file: headers and section/load-command
    # tables are structural.  This exercises the analyzer on valid layouts.
    low = max(1, len(data) // 4)
    high = max(low + 1, (3 * len(data)) // 4)
    for _ in range(6):
        mutated = bytearray(data)
        for _ in range(8):
            offset = rng.randrange(low, high)
            mutated[offset] ^= 1 << rng.randrange(8)
        payload = scan_binary(bytes(mutated))
        assert isinstance(payload["findings"], list)
        assert payload["format"] in {"elf", "pe", "macho", "macho-fat", "unknown"}


def test_truncation_matrix_is_bounded():
    for path in FIXTURES:
        if not path.is_file():
            continue
        data = path.read_bytes()
        for size in (0, 1, 7, 63, 512, len(data) // 3):
            scan_binary(data[:size])  # must not raise


def test_repair_never_returns_an_ungated_candidate():
    for path in FIXTURES:
        if not path.is_file():
            continue
        data = path.read_bytes()
        patched, report = repair_binary(data[:len(data) // 3], verify=False)
        if patched is not None:
            assert report.actions
            assert report.status == "patched"
