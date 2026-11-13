"""Single source of truth for the deterministic binary repair matrix (v5).

The pipeline is deliberately *matrix driven*: an input is repairable only when
its container/architecture/bitness/endian matches one of the cells below **and**
the analyzer finds a patchable sink from a supported sink class.  Everything
else returns an explicit ``analysis_only`` / ``unsupported`` disposition; no
module may hard-code a different matrix.

The module is dependency-free (duck-typed ``container`` argument) so it can be
imported by the pipeline, the verification gate, the HTTP API and the CLI
without creating import cycles.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 1

# Sink kinds produced by ``app.services.repair.analyzer`` and consumed by
# ``app.services.repair.writer``.  ``strategy`` names the generic repair action.
SINK_CLASSES: dict[str, dict[str, str]] = {
    "unbounded_copy": {
        "strategy": "guard",
        "description": "strcpy/strcat/stpcpy into a analysed destination",
    },
    "immediate_length": {
        "strategy": "immediate",
        "description": "constant length operand of a bounded copy/read/write",
    },
    "memcpy_length": {
        "strategy": "immediate",
        "description": "constant length operand passed to memcpy/memmove",
    },
    "syscall_length": {
        "strategy": "immediate",
        "description": "constant length operand of a direct read/write syscall",
    },
    "checked_copy": {
        "strategy": "immediate",
        "description": "constant length operand of a checked copy helper",
    },
}

DISPOSITIONS = (
    "verified_patch",
    "static_only_patch",
    "not_verified",
    "analysis_only",
    "unsupported",
    "rejected",
    "invalid",
)

RUNTIME_TIERS = {
    "native_run": "the repaired candidate executed natively on the host",
    "emulated_run": "the repaired function executed under Unicorn",
    "static_only": "no runtime evidence; never a verified success",
}


@dataclass(frozen=True)
class RepairCell:
    """One supported (container, arch, bits, endian) repair cell."""

    container: str
    arch: str
    bits: int
    endian: str
    strategies: tuple[str, ...]
    runtime_tiers: tuple[str, ...]
    sink_classes: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.container}/{self.arch}/{self.bits}/{self.endian}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "container": self.container,
            "arch": self.arch,
            "bits": self.bits,
            "endian": self.endian,
            "strategies": list(self.strategies),
            "runtime_tiers": list(self.runtime_tiers),
            "sink_classes": list(self.sink_classes),
        }


_ALL_SINKS = tuple(sorted(SINK_CLASSES))

# The deterministic repair matrix.  Only little-endian thin containers are
# listed; fat Mach-O, 32-bit Mach-O, arm32, riscv, mips, powerpc and big-endian
# inputs are intentionally outside the matrix (analysis-only).
REPAIR_CELLS: tuple[RepairCell, ...] = (
    RepairCell(
        container="elf",
        arch="i386",
        bits=32,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_ALL_SINKS,
    ),
    RepairCell(
        container="elf",
        arch="x86_64",
        bits=64,
        endian="little",
        strategies=("strict-template", "immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_ALL_SINKS,
    ),
    RepairCell(
        container="elf",
        arch="arm64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_ALL_SINKS,
    ),
    RepairCell(
        container="pe",
        arch="i386",
        bits=32,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_ALL_SINKS,
    ),
    RepairCell(
        container="pe",
        arch="x86_64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_ALL_SINKS,
    ),
    RepairCell(
        container="pe",
        arch="arm64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_ALL_SINKS,
    ),
    RepairCell(
        container="macho",
        arch="x86_64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("native_run",),
        sink_classes=_ALL_SINKS,
    ),
    RepairCell(
        container="macho",
        arch="arm64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("native_run",),
        sink_classes=_ALL_SINKS,
    ),
)

_NON_GOALS = (
    "heap, global and non-imported inline copy sinks",
    "sprintf/format-string expansion, UAF, integer and loop defects",
    "arm32, riscv, mips, powerpc and big-endian machine-code repair",
    "32-bit Mach-O and fat Mach-O rewriting",
    "Windows / macOS native execution beyond the existing Mach-O path",
)


def _attr(container: Any, name: str, default: Any = None) -> Any:
    return getattr(container, name, default)


def repair_cell(container: Any) -> RepairCell | None:
    """Return the matching repair cell, or ``None`` for analysis-only input."""
    fmt = str(_attr(container, "format", "unknown"))
    arch = str(_attr(container, "arch", "unknown"))
    bits = _attr(container, "bits")
    endian = str(_attr(container, "endian", "little"))
    if endian != "little":
        return None
    for cell in REPAIR_CELLS:
        if (cell.container, cell.arch, cell.bits) == (fmt, arch, bits):
            return cell
    return None


def is_repairable(container: Any) -> bool:
    return repair_cell(container) is not None


def supported_pairs() -> set[tuple[str, str]]:
    """Backward-compatible ``(format, arch)`` set used by old call sites."""
    return {(cell.container, cell.arch) for cell in REPAIR_CELLS}


def plans_strategy(cell: RepairCell, strategy: str) -> bool:
    return strategy == "auto" or strategy in cell.strategies


def matrix_payload() -> dict[str, Any]:
    """English-ASCII coverage payload for ``GET /api/binary/matrix`` and docs."""
    return {
        "schema_version": SCHEMA_VERSION,
        "cells": [cell.to_dict() for cell in REPAIR_CELLS],
        "sink_classes": {name: dict(meta) for name, meta in SINK_CLASSES.items()},
        "dispositions": list(DISPOSITIONS),
        "runtime_tiers": dict(RUNTIME_TIERS),
        "non_goals": list(_NON_GOALS),
        "notes": [
            "Every input is triaged; only matrix cells with a patchable sink "
            "produce a repaired candidate.",
            "static_only is opt-in, unverified and never counted as success.",
        ],
    }
