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
    "capacity_check_mismatch": {
        "strategy": "capacity",
        "description": (
            "inlined duplicated destination range check whose minority copy "
            "tests the input size instead of the output capacity"
        ),
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
    "unavailable": "no runner/evidence; never a verified success",
    "static_only": "no runtime evidence; never a verified success",
}

# Declared acceptance/evidence models.  This registry is the only place that
# declares which evidence a repair class must supply: the verification gates
# enforce exactly these models and must not invent a different one.
#
# ``required_checks`` are check ids of the unified verification gate
# (``app.services.unified_verification.build``); ``legacy_required_checks`` are
# ids of the legacy ELF quick-repair gate
# (``app.services.binary_verification.build_verification``).
_COMMON_GATE_CHECKS = (
    "format",
    "candidate.present",
    "candidate.identity.original",
    "candidate.identity.patched",
    "container.reparse",
    "repair.action",
)
_RUNTIME_GATE_CHECKS = (
    "runtime.evidence",
    "runtime.tier",
    "runtime.contract",
)
_POC_GATE_CHECKS = (
    "poc.native.available",
    "poc.native.original_failure",
    "poc.native.candidate_pass",
    "poc.native.regression",
    "poc.native.stdout_signature",
)
_NATIVE_POC_CHECKS = _COMMON_GATE_CHECKS + _RUNTIME_GATE_CHECKS + _POC_GATE_CHECKS

EVIDENCE_PROFILES: dict[str, dict[str, Any]] = {
    "strict_template": {
        "description": (
            "Legacy ELF x86-64 repair against the reviewed strict template, "
            "verified by the template identity plus Unicorn stack-copy cases."
        ),
        "evidence_sources": ("runtime",),
        "required_checks": _COMMON_GATE_CHECKS + _RUNTIME_GATE_CHECKS,
        "legacy_required_checks": (
            "format",
            "candidate.present",
            "candidate.identity.original",
            "candidate.identity.patched",
            "patch.scope",
            "runtime.available",
            "runtime.cases",
            "runtime.no_overflow",
            "runtime.boundary_semantics",
            "strict.reviewed_template",
        ),
    },
    "emulated_instruction": {
        "description": (
            "Unicorn instruction/function emulation of the repaired function "
            "for stack-bound copy sinks.  The emulated oracle only models "
            "in-bounds cases that exit 0: guard/reject semantics (a candidate "
            "exit status of 1 on an over-limit input) cannot be represented, so "
            "non-stack destinations must never reuse this oracle."
        ),
        "evidence_sources": ("runtime",),
        "required_checks": _COMMON_GATE_CHECKS + _RUNTIME_GATE_CHECKS,
        "legacy_required_checks": (
            "format",
            "candidate.present",
            "candidate.identity.original",
            "candidate.identity.patched",
            "patch.scope",
            "runtime.available",
            "runtime.cases",
            "runtime.no_overflow",
        ),
    },
    "native_poc": {
        "description": (
            "External PoC/regression differential executed natively or in a "
            "guest runtime.  This is the declared evidence model for non-stack "
            "(heap/global) destinations and for hosts without an "
            "instruction-level runtime; no fabricated runtime evidence is "
            "allowed when the runner is unavailable."
        ),
        "evidence_sources": ("external_poc",),
        "required_checks": _NATIVE_POC_CHECKS,
        "legacy_required_checks": (),
    },
    "native_poc_rewrite": {
        "description": (
            "External PoC/regression differential plus byte-re-derived "
            "in-place rewrite actions (reviewed duplicated-capacity-check "
            "rewrite); every rewrite action is re-derived from the original "
            "and candidate bytes by the gate."
        ),
        "evidence_sources": ("external_poc", "rewrite_actions"),
        "required_checks": _NATIVE_POC_CHECKS + ("patch.rewrite",),
        "legacy_required_checks": (),
    },
}

# Default profile planned by a repair strategy.  Sink/evidence rules in
# ``resolve_profile`` can override this (heap/global sinks and external PoCs
# never use the emulated-instruction oracle).
STRATEGY_PROFILES: dict[str, str] = {
    "strict-template": "strict_template",
    "immediate": "emulated_instruction",
    "guard": "emulated_instruction",
    "capacity": "native_poc_rewrite",
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


# Sinks recovered by the container-neutral analyzer and consumed by the generic
# writer.  The sets are per-architecture because the analyzers have different
# emission paths (``analyzer._scan_x86_64``, ``analyzer_i386.scan_i386`` and
# ``analyzer._scan_arm64``); a cell must not advertise a class its analyzer
# cannot emit.  Container format is irrelevant: the arch dispatch is shared by
# ELF, PE and Mach-O.
_I386_ANALYZER_SINKS = ("memcpy_length", "unbounded_copy")
_X86_64_ANALYZER_SINKS = ("checked_copy", "memcpy_length", "syscall_length",
                          "unbounded_copy")
_ARM64_ANALYZER_SINKS = ("checked_copy", "memcpy_length", "unbounded_copy")
# The ELF/x86-64 cell additionally plans the reviewed capacity-check rewrite;
# it is the only cell that advertises the ``capacity`` strategy and sink class.
_ELF_X86_64_SINKS = _X86_64_ANALYZER_SINKS + ("capacity_check_mismatch",)

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
        sink_classes=_I386_ANALYZER_SINKS,
    ),
    RepairCell(
        container="elf",
        arch="x86_64",
        bits=64,
        endian="little",
        strategies=("strict-template", "immediate", "guard", "capacity"),
        # Native x86_64 hosts can execute this cell directly; qemu/Unicorn
        # remains the fallback on other hosts.
        runtime_tiers=("native_run", "emulated_run"),
        sink_classes=_ELF_X86_64_SINKS,
    ),
    RepairCell(
        container="elf",
        arch="arm64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_ARM64_ANALYZER_SINKS,
    ),
    RepairCell(
        container="pe",
        arch="i386",
        bits=32,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_I386_ANALYZER_SINKS,
    ),
    RepairCell(
        container="pe",
        arch="x86_64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_X86_64_ANALYZER_SINKS,
    ),
    RepairCell(
        container="pe",
        arch="arm64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("emulated_run",),
        sink_classes=_ARM64_ANALYZER_SINKS,
    ),
    RepairCell(
        container="macho",
        arch="x86_64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("native_run",),
        sink_classes=_X86_64_ANALYZER_SINKS,
    ),
    RepairCell(
        container="macho",
        arch="arm64",
        bits=64,
        endian="little",
        strategies=("immediate", "guard"),
        runtime_tiers=("native_run",),
        sink_classes=_ARM64_ANALYZER_SINKS,
    ),
)

#: Strategies actually exercised by the committed fixture corpus / test
#: evidence, per cell key.  This is a measurement, not a claim: any declared
#: strategy missing here is reported as ``untested_strategies`` in the matrix
#: payload instead of being silently presented as proven.
FIXTURE_STRATEGY_EVIDENCE: dict[str, tuple[str, ...]] = {
    # fixtures/elf/vuln-strcpy-x86.elf + fixtures/elf/vuln-memcpy-x86.elf
    "elf/i386/32/little": ("guard", "immediate"),
    # artifacts/vuln-elf (strict template), fixtures/elf/vuln-strcpy-x86_64.elf
    # (guard), fixtures/elf/vuln-capacity-confusion-x86_64.elf (capacity)
    "elf/x86_64/64/little": ("strict-template", "guard", "capacity"),
    "elf/arm64/64/little": ("guard",),
    "pe/i386/32/little": ("guard",),
    "pe/x86_64/64/little": ("guard",),
    "pe/arm64/64/little": ("guard",),
    "macho/x86_64/64/little": ("guard",),
    "macho/arm64/64/little": ("guard",),
}

_NON_GOALS = (
    "copy sinks whose destination capacity is not recoverable by the "
    "same-function analysis (dynamic sizes, pointer+offset aliases, "
    "cross-function allocations)",
    "sprintf/format-string expansion, use-after-free and other integer/loop defects",
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


def profile_for_strategy(strategy: str) -> str | None:
    """Return the profile a strategy plans by default, or ``None``."""
    return STRATEGY_PROFILES.get(str(strategy or ""))


def resolve_profile(
    *,
    has_runtime: bool = False,
    has_external_poc: bool = False,
    has_rewrite_actions: bool = False,
    capacity: bool = False,
    destination_kind: str = "stack",
) -> str:
    """Declare the evidence profile for the evidence a caller supplies.

    This is the pipeline's strategy/sink -> profile rule and the declared
    backward-compatible default for direct gate callers that do not pass an
    explicit profile.  Non-stack destinations must never be accepted through
    the stack/emulated-instruction oracle.
    """
    del has_runtime  # runtime hints never select the external-PoC model
    if capacity or has_rewrite_actions:
        return "native_poc_rewrite"
    if has_external_poc:
        return "native_poc"
    if str(destination_kind or "stack") != "stack":
        return "native_poc"
    return "emulated_instruction"


def is_known_profile(profile: str) -> bool:
    return str(profile or "") in EVIDENCE_PROFILES


def profile_required_checks(profile: str) -> tuple[str, ...]:
    meta = EVIDENCE_PROFILES.get(str(profile or ""))
    return tuple(meta["required_checks"]) if meta else ()


def profile_legacy_required_checks(profile: str) -> tuple[str, ...]:
    meta = EVIDENCE_PROFILES.get(str(profile or ""))
    return tuple(meta["legacy_required_checks"]) if meta else ()


def profile_evidence_sources(profile: str) -> tuple[str, ...]:
    meta = EVIDENCE_PROFILES.get(str(profile or ""))
    return tuple(meta["evidence_sources"]) if meta else ()


def _unavailable_capability(cell: RepairCell, reason: str) -> dict[str, Any]:
    """Fail-safe capability row used when the live probe cannot answer."""

    return {
        "cell_key": cell.key,
        "format": cell.container,
        "arch": cell.arch,
        "available": False,
        "tier": "unavailable",
        "engine": "none",
        "poc_available": False,
        "reason": reason,
        "source": "none",
    }


def measured_runtime_capabilities(
    cells: tuple[RepairCell, ...] | list[RepairCell] = REPAIR_CELLS,
) -> dict[str, dict[str, Any]]:
    """Measured (not declared) runtime capability per matrix cell.

    The declared ``runtime_tiers`` stay untouched; this is the live measurement
    from :func:`app.services.runtime.capabilities.probe`, keyed by cell key.  A
    probe error degrades that row to ``unavailable`` with the error in
    ``reason`` (fail closed, never a fabricated tier).
    """

    try:
        from app.services.runtime import capabilities
    except Exception as exc:  # noqa: BLE001 - matrix payload must stay buildable
        return {
            cell.key: _unavailable_capability(
                cell, f"capability probe unavailable: {type(exc).__name__}: {exc}"
            )
            for cell in cells
        }
    measured: dict[str, dict[str, Any]] = {}
    for cell in cells:
        try:
            item = capabilities.probe(cell.container, cell.arch)
            row = {
                "cell_key": cell.key,
                "format": str(item.get("format") or cell.container),
                "arch": str(item.get("arch") or cell.arch),
                "available": bool(item.get("available")),
                "tier": str(item.get("tier") or "unavailable"),
                "engine": str(item.get("engine") or "none"),
                "poc_available": bool(item.get("poc_available")),
                "reason": str(item.get("reason") or ""),
                "source": str(item.get("source") or "none"),
            }
        except Exception as exc:  # noqa: BLE001
            row = _unavailable_capability(
                cell, f"capability probe failed: {type(exc).__name__}: {exc}"
            )
        measured[cell.key] = row
    return measured


def _unavailable_contract(cell: RepairCell, reason: str) -> dict[str, Any]:
    """Fail-safe unified-contract row used when the contract cannot answer."""

    tiers = tuple(cell.runtime_tiers)
    declared = (
        "native_run" if "native_run" in tiers
        else "emulated_run" if "emulated_run" in tiers
        else "unavailable"
    )
    return {
        "cell_key": cell.key,
        "declared_tier": declared,
        "measured_tier": "unavailable",
        "poc_available": False,
        "emulated_available": False,
        "available": False,
        "reason": reason,
        "source": "none",
        "declared_available": False,
    }


def measured_contract_capabilities(
    cells: tuple[RepairCell, ...] | list[RepairCell] = REPAIR_CELLS,
) -> dict[str, dict[str, Any]]:
    """Unified capability contract per matrix cell, derived ONLY from the probe.

    Each row is :func:`app.services.runtime.capabilities.contract` for the cell's
    ``(container, arch)`` plus ``cell_key`` and a ``declared_available`` flag
    (``measured_tier == declared_tier``).  The declared ``runtime_tiers`` remain
    untouched; when the measured tier is not the declared one the contract row
    carries a non-empty ``reason`` explaining the gap (e.g. Mach-O/x86_64
    external PoC on arm64, PE external PoC, 32-bit Mach-O unavailable).  A
    contract error degrades that row to ``unavailable`` with the error in
    ``reason``: the payload never fabricates a tier.
    """

    try:
        from app.services.runtime import capabilities
    except Exception as exc:  # noqa: BLE001 - matrix payload must stay buildable
        return {
            cell.key: _unavailable_contract(
                cell, f"capability contract unavailable: {type(exc).__name__}: {exc}"
            )
            for cell in cells
        }
    fields = tuple(capabilities.CONTRACT_FIELDS)
    measured: dict[str, dict[str, Any]] = {}
    for cell in cells:
        try:
            item = capabilities.contract(cell.container, cell.arch)
            row: dict[str, Any] = {"cell_key": cell.key}
            for field in fields:
                value = item.get(field)
                if field in {"available", "poc_available", "emulated_available"}:
                    row[field] = bool(value)
                elif field in {"declared_tier", "measured_tier", "reason", "source"}:
                    row[field] = str(value or "")
                else:  # pragma: no cover - CONTRACT_FIELDS is closed above
                    row[field] = value
            row["declared_available"] = row["measured_tier"] == row["declared_tier"]
        except Exception as exc:  # noqa: BLE001
            row = _unavailable_contract(
                cell, f"capability contract failed: {type(exc).__name__}: {exc}"
            )
        measured[cell.key] = row
    return measured


def matrix_payload() -> dict[str, Any]:
    """English-ASCII coverage payload for ``GET /api/binary/matrix`` and docs."""
    cells: list[dict[str, Any]] = []
    for cell in REPAIR_CELLS:
        row = cell.to_dict()
        exercised = tuple(FIXTURE_STRATEGY_EVIDENCE.get(cell.key, ()))
        row["fixture_strategies"] = [
            strategy for strategy in cell.strategies if strategy in exercised
        ]
        row["untested_strategies"] = [
            strategy for strategy in cell.strategies if strategy not in exercised
        ]
        cells.append(row)
    return {
        "schema_version": SCHEMA_VERSION,
        "cells": cells,
        "fixture_strategy_evidence": {
            key: list(evidence) for key, evidence in FIXTURE_STRATEGY_EVIDENCE.items()
        },
        "sink_classes": {name: dict(meta) for name, meta in SINK_CLASSES.items()},
        # Declared analyzer capabilities that no shipped fixture exercises yet.
        # Kept explicit so a coverage audit can distinguish "declared but not
        # exercised" from a false matrix claim (no fake fixture evidence).
        "untested_sink_classes": ["checked_copy"],
        "dispositions": list(DISPOSITIONS),
        "runtime_tiers": dict(RUNTIME_TIERS),
        # Measured, per-cell runtime capability next to the declared tiers above:
        # a declared tier is not a claim that this host can produce it.
        "runtime_capabilities": measured_runtime_capabilities(),
        # Unified capability contract per cell (declared vs measured tier,
        # external-PoC/emulated availability, explicit reason).  Derived only
        # from capabilities.contract; a declared tier never becomes an
        # availability claim.
        "contract_capabilities": measured_contract_capabilities(),
        "evidence_profiles": {
            name: {
                "description": meta["description"],
                "evidence_sources": list(meta["evidence_sources"]),
                "required_checks": list(meta["required_checks"]),
                "legacy_required_checks": list(meta["legacy_required_checks"]),
            }
            for name, meta in EVIDENCE_PROFILES.items()
        },
        "strategy_profiles": dict(STRATEGY_PROFILES),
        "non_goals": list(_NON_GOALS),
        "notes": [
            "Every input is triaged; only matrix cells with a patchable sink "
            "produce a repaired candidate.",
            "static_only is opt-in, unverified and never counted as success.",
        ],
    }
