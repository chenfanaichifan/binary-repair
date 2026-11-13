"""Bounded, no-crash contract for arbitrary input bytes."""
from __future__ import annotations

import random
from pathlib import Path

from app.services.binary_pipeline import repair_any, scan_binary
from app.services.repair_matrix import DISPOSITIONS

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = tuple(
    path for path in (
        ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf",
        ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf",
        ROOT / "fixtures" / "elf" / "vuln-strcpy-arm64.elf",
        ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe",
        ROOT / "fixtures" / "pe" / "vuln-strcpy-arm64.exe",
        ROOT / "fixtures" / "macho" / "vuln-strcpy-x86_64",
        ROOT / "fixtures" / "macho" / "vuln-strcpy-arm64",
    ) if path.is_file()
)


def _mutations(seed: bytes, rng: random.Random) -> bytes:
    data = bytearray(seed[: max(32, len(seed) // 3)])
    for _ in range(rng.randrange(1, 10)):
        pos = rng.randrange(len(data))
        data[pos] ^= 1 << rng.randrange(8)
    return bytes(data)


def test_arbitrary_and_mutated_inputs_never_raise_and_are_typed():
    rng = random.Random(20261113)
    seeds = [path.read_bytes() for path in FIXTURES]
    samples: list[bytes] = [b"", b"\x7fELF", b"MZ", b"\xcf\xfa\xed\xfe", b"\x00" * 64]
    samples += [bytes(rng.randrange(256) for _ in range(rng.randrange(0, 768)))
                for _ in range(250)]
    for i in range(250):
        samples.append(_mutations(seeds[i % len(seeds)], rng))
    for index, data in enumerate(samples):
        scan = scan_binary(data)
        assert isinstance(scan, dict), index
        outcome = repair_any(data, verify=False)
        report = outcome.report
        assert report.disposition in DISPOSITIONS, (index, report.disposition)
        assert isinstance(report.error, (str, type(None))), index
        if report.disposition in {"verified_patch"}:
            # verify=False must never claim a verified candidate.
            raise AssertionError(f"unexpected verified disposition without verification at {index}")
