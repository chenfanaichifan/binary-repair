"""One-click, pattern-based binary repair for a bounded read.

This is deliberately narrow and fail-closed.  It recognizes:

    sub rsp, N
    ...
    xor eax,eax / xor edi,edi / mov rsi,rsp / mov edx,BIG / syscall

and rewrites the read (and following write) length to N.  It never executes the
input.  The returned candidate must also pass the structured verification gate
(including Unicorn runtime evidence) before this legacy API hands it back; a
candidate with missing evidence is not a success.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from elftools.elf.elffile import ELFFile

from app.services.binary_repair_engine import repair_elf
from app.services.binary_verification import build_verification

MD = Cs(CS_ARCH_X86, CS_MODE_64)
MAX_INPUT = 20 * 1024 * 1024


class QuickRepairError(RuntimeError):
    pass


@dataclass(frozen=True)
class QuickRepairReport:
    original_sha256: str
    patched_sha256: str
    capacity: int
    offsets: list[int]
    before: list[str]
    after: list[str]
    limitations: list[str]
    mode: str = "bounds-only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def quick_repair_elf(data: bytes) -> tuple[bytes, QuickRepairReport]:
    """Delegate to the direct byte engine; keep this API for the GUI/tests."""
    if len(data) > MAX_INPUT:
        raise QuickRepairError("ELF exceeds the 20 MiB limit")
    patched, report = repair_elf(data)
    if patched is None:
        detail = report.limitations[-1] if report.limitations else "unsupported binary"
        raise QuickRepairError(detail)
    verification = build_verification(report, original=data, patched=patched)
    if not verification.gate.success:
        raise QuickRepairError(
            f"verification did not pass: {verification.gate.reason}"
        )
    return patched, QuickRepairReport(
        original_sha256=report.original_sha256,
        patched_sha256=report.patched_sha256,
        capacity=report.capacity or 0,
        offsets=report.offsets,
        before=[],
        after=[],
        limitations=report.limitations,
        mode=report.mode,
    )
