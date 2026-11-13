"""Unified, fail-closed dispatch for direct binary repair (v5).

The pipeline is container-neutral and matrix driven:

* ``containers.detect_container`` identifies ELF / PE / Mach-O and resolves
  imported call targets (PLT, IAT/thunk, Mach-O stubs);
* ``repair_matrix`` is the single source of truth for the supported
  (container, arch, bits) cells;
* ``repair.analyzer`` recovers copy sinks and their capacity;
* ``repair.writer`` applies in-place immediate patches or injects an executable
  guard section and redirects the call;
* Mach-O candidates are verified by native execution on macOS; PE, i386 and
  AArch64 ELF candidates by Unicorn instruction-level execution.

Every input gets a deterministic disposition:

* ``verified_patch``   - candidate + native/emulated runtime gate passed;
* ``static_only_patch``- candidate produced but no runtime evidence, explicitly
  opted in with ``allow_static_only=True`` (never ``verified``);
* ``not_verified``     - a candidate exists but delivery was not allowed;
* ``analysis_only``    - recognised container, no patchable sink;
* ``unsupported``      - recognised container outside the repair matrix;
* ``rejected``         - the deterministic gate rejected the candidate;
* ``invalid``          - empty/oversized/unrecognised input.

Anything outside the matrix returns no candidate.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.containers import ContainerInfo, detect_container
from app.services.repair.analyzer import Analysis, Sink, analyze
from app.services.repair.guards import abi_for
from app.services.repair.writer import repair_with_sinks
from app.services.repair_matrix import (
    DISPOSITIONS,
    SINK_CLASSES,
    RepairCell,
    is_repairable,
    matrix_payload,
    plans_strategy,
    repair_cell,
    supported_pairs,
)
from app.services.runtime import emulated, macho_native

MAX_INPUT_BYTES = 20 * 1024 * 1024

# Backward-compatible legacy constant (format/arch pairs).  New code must use
# ``repair_matrix`` so bitness/endianness are checked as well.
SUPPORTED_REPAIR = supported_pairs()

_CONTAINER_FORMATS = {"elf", "pe", "macho", "macho-fat"}


@dataclass
class UnifiedBinaryReport:
    """One report shape for ELF, PE and Mach-O (schema v4)."""

    schema_version: int = 4
    format: str = "unknown"
    arch: str = "unknown"
    backend: str = "unknown"
    strategy: str = "none"
    status: str = "unsupported"
    supported: bool = False
    original_sha256: str = ""
    patched_sha256: str = ""
    mode: str = "unsupported"
    capacity: int | None = None
    findings: list[dict[str, Any]] = field(default_factory=list)
    offsets: list[int] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    container: dict[str, Any] = field(default_factory=dict)
    universal: dict[str, Any] = field(default_factory=dict)
    signature_invalidated: bool = False
    codesign_invalidated: bool = False
    candidate_available: bool = False
    error: str | None = None
    disposition: str = "invalid"
    matrix: dict[str, Any] = field(default_factory=dict)
    delivery: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    slices: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ai: dict[str, Any] = field(default_factory=dict)
    poc: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "findings": [dict(item) for item in self.findings],
            "actions": [dict(item) for item in self.actions],
        }


@dataclass
class RepairOutcome:
    """Result of one ``repair_any`` call."""

    candidate: bytes | None
    report: UnifiedBinaryReport
    verified: bool = False
    download_allowed: bool = False


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _container_dict(container: ContainerInfo) -> dict[str, Any]:
    return {
        "format": container.format,
        "arch": container.arch,
        "bits": container.bits,
        "endian": container.endian,
        "image_base": container.image_base,
        "slices": container.slices,
        "imports": len(container.imports),
        "sections": len(container.sections),
    }


def detect_format(data: bytes) -> tuple[str, str, int | None]:
    """Return ``(format, arch, bits)`` without executing the file."""
    container = detect_container(data)
    fmt = container.format if container.format in _CONTAINER_FORMATS else "unknown"
    arch = container.arch if fmt != "unknown" else "unknown"
    return fmt, arch, container.bits


def _matrix_dict(cell: RepairCell | None) -> dict[str, Any]:
    if cell is None:
        return {
            "cell": None,
            "repairable": False,
            "strategies": [],
            "runtime_tiers": [],
            "sink_classes": [],
        }
    return {
        "cell": cell.key,
        "repairable": True,
        "strategies": list(cell.strategies),
        "runtime_tiers": list(cell.runtime_tiers),
        "sink_classes": list(cell.sink_classes),
    }


def _coverage_dict() -> dict[str, Any]:
    payload = matrix_payload()
    return {
        "schema_version": payload["schema_version"],
        "sink_classes": sorted(SINK_CLASSES),
        "non_goals": list(payload["non_goals"]),
    }


class _SliceContainer:
    """Duck-typed container used only for per-slice matrix lookups."""

    def __init__(self, arch: str, bits: int) -> None:
        self.format = "macho"
        self.arch = arch
        self.bits = bits
        self.endian = "little"


def _slice_container(arch: str, bits: int) -> _SliceContainer:
    return _SliceContainer(arch, bits)


def _macho_slices(data: bytes) -> list[dict[str, Any]]:
    """Best-effort per-slice metadata for a fat Mach-O; never raises."""
    try:
        import lief

        parsed = lief.MachO.parse(list(data))
        if parsed is None:
            return []
        count = int(getattr(parsed, "size", 1) or 1)
        rows: list[dict[str, Any]] = []
        for index in range(count):
            try:
                binary = parsed.at(index)
                cpu = str(binary.header.cpu_type)
            except Exception:  # noqa: BLE001
                continue
            arch = (
                "x86_64" if "X86_64" in cpu else
                "arm64" if "ARM64" in cpu else
                "i386" if "X86" in cpu or "I386" in cpu else
                "arm" if "ARM" in cpu else "unknown"
            )
            bits = 64 if "64" in cpu else 32
            slice_supported = repair_cell(
                _slice_container(arch, bits)
            ) is not None
            rows.append({
                "index": index,
                "cpu": cpu,
                "arch": arch,
                "bits": bits,
                # Per-slice architecture support, not a fat-rewrite claim:
                # fat Mach-O rewriting remains outside the repair matrix.
                "supported": slice_supported,
                "container_rewrite": False,
            })
        return rows
    except Exception:  # noqa: BLE001
        return []


def _set_disposition(
    report: UnifiedBinaryReport,
    disposition: str,
    *,
    verified: bool = False,
    download_allowed: bool = False,
    tier: str = "static_only",
) -> None:
    if disposition not in DISPOSITIONS:
        raise ValueError(f"unknown disposition: {disposition}")
    report.disposition = disposition
    report.delivery = {
        "download_allowed": bool(download_allowed),
        "verified": bool(verified),
        "tier": tier,
    }


def _unsupported(
    container: ContainerInfo,
    data: bytes,
    reason: str,
    *,
    disposition: str = "unsupported",
) -> UnifiedBinaryReport:
    report = _base_report(data, container)
    report.limitations = [reason]
    report.error = reason
    report.universal["reason"] = reason
    _set_disposition(report, disposition)
    return report


def _base_report(data: bytes, container: ContainerInfo) -> UnifiedBinaryReport:
    cell = repair_cell(container)
    return UnifiedBinaryReport(
        format=container.format if container.format != "unknown" else "unknown",
        arch=container.arch,
        backend=container.format if container.format in _CONTAINER_FORMATS else "unknown",
        original_sha256=_sha(data),
        patched_sha256=_sha(data),
        container=_container_dict(container),
        universal={
            "detected": container.format in _CONTAINER_FORMATS,
            "repairable": cell is not None,
            "reason": "",
        },
        matrix=_matrix_dict(cell),
        coverage=_coverage_dict(),
        slices=_macho_slices(data) if container.format == "macho-fat" else [],
    )


def _sink_to_finding(sink: Sink) -> dict[str, Any]:
    return {
        "kind": sink.kind,
        "address": hex(sink.call_va or 0),
        "callee": sink.callee,
        "capacity": sink.capacity,
        "dest_offset": sink.dest_rel,
        "before": sink.length,
        "after": sink.capacity,
        "patchable": sink.patchable,
        "confidence": sink.confidence,
        "strategy": SINK_CLASSES.get(sink.kind, {}).get("strategy", "none"),
        "detail": sink.detail,
    }


def scan_binary(data: bytes) -> dict[str, Any]:
    """Scan any container; never writes or executes.  Schema v4."""
    if len(data) > MAX_INPUT_BYTES:
        return {
            "schema_version": 4,
            "format": "unknown",
            "arch": "unknown",
            "backend": "none",
            "supported": False,
            "repair_supported": False,
            "findings": [],
            "limitations": [f"input exceeds {MAX_INPUT_BYTES} bytes"],
            "matrix": _matrix_dict(None),
        }
    analysis: Analysis = analyze(data)
    container = analysis.container
    cell = repair_cell(container)
    patchable = analysis.patchable()
    repair_supported = bool(cell is not None and patchable)
    result: dict[str, Any] = {
        "schema_version": 4,
        "format": container.format,
        "arch": container.arch,
        "bits": container.bits,
        "endian": container.endian,
        "backend": container.format,
        "supported": container.format in _CONTAINER_FORMATS,
        "repair_supported": repair_supported,
        "findings": [_sink_to_finding(sink) for sink in analysis.sinks],
        "limitations": list(analysis.limitations),
        "container": _container_dict(container),
        "matrix": _matrix_dict(cell),
        "coverage": _coverage_dict(),
        "slices": _macho_slices(data) if container.format == "macho-fat" else [],
    }
    if not result["supported"]:
        result["limitations"].append(
            f"{container.format}/{container.arch}: unrecognised container"
        )
    elif cell is None:
        result["limitations"].append(
            f"{container.format}/{container.arch}/{container.bits}: outside the repair matrix"
        )
    return result


def _from_elf_legacy(
    container: ContainerInfo,
    data: bytes,
    patched: bytes | None,
    raw: Any,
    *,
    verify: bool,
) -> UnifiedBinaryReport:
    report = _base_report(data, container)
    report.backend = raw.backend or "elf"
    report.strategy = raw.strategy or "none"
    report.status = raw.status or ("patched" if patched else "unsupported")
    report.supported = bool(raw.supported and patched is not None)
    report.mode = raw.mode
    report.capacity = raw.capacity
    raw_findings = getattr(raw, "findings", [])
    if isinstance(raw_findings, (str, bytes)) or not isinstance(raw_findings, (list, tuple)):
        raw_findings = [raw_findings] if raw_findings else []
    normalized = []
    for item in raw_findings:
        if hasattr(item, "to_dict"):
            normalized.append(dict(item.to_dict()))
        elif isinstance(item, dict):
            normalized.append(dict(item))
    report.findings = normalized
    report.offsets = list(raw.offsets)
    report.limitations = list(raw.limitations)
    report.runtime = dict(raw.runtime or {})
    report.verification = dict(raw.verification or {})
    if patched is not None:
        report.patched_sha256 = _sha(patched)
        report.candidate_available = True
    if verify and patched is not None and report.arch == "x86_64":
        try:
            from app.services.binary_verification import build_verification

            verification = build_verification(raw, original=data, patched=patched)
            report.verification = {
                "packet": verification.packet,
                "gate": asdict(verification.gate),
                "tier": "emulated_run",
                "engine": "unicorn-x86-64",
            }
            if not verification.gate.success:
                # Fail closed: a failed gate must not leave a downloadable
                # candidate behind (the historical fail-open path).
                report.status = "not_verified"
                report.supported = False
                report.candidate_available = False
                report.limitations.append(
                    f"verification gate did not pass: {verification.gate.reason}"
                )
        except Exception as exc:  # noqa: BLE001
            report.status = "not_verified"
            report.supported = False
            report.candidate_available = False
            report.limitations.append(
                f"verification unavailable: {type(exc).__name__}: {exc}"
            )
    if patched is not None:
        report.verification.setdefault("static_reparse", True)
    return report


def _select_runtime(data: bytes, container: ContainerInfo, sink: Sink):
    """Select native/emulated evidence for the sink that was repaired.

    Both guard sinks (strcpy/strcat) and length-aware immediate sinks
    (memcpy/memmove, syscall/checked copies) are passed to the runtime; the
    runtime's copy hook is length-aware when ``copy_kind``/``callee`` say so.
    """
    capacity = int(sink.capacity or 0)
    kind = sink.kind
    callee = sink.callee
    if container.format == "macho":
        if not macho_native.available():
            return None
        return macho_native.run(data, arch=container.arch, capacity=capacity)
    if container.format == "pe" and container.arch in {"x86_64", "arm64", "i386"}:
        abi = "cdecl_x86" if container.arch == "i386" else abi_for(container.format, container.arch)
        return emulated.emulate(
            data, container,
            function_va=sink.function_va,
            dest_rel=int(sink.dest_rel or 0),
            capacity=capacity,
            abi=abi,
            copy_kind=kind, callee=callee,
        )
    if container.format == "elf" and container.arch in {"arm64", "i386", "x86_64"}:
        abi = (
            "cdecl_x86" if container.arch == "i386"
            else "aapcs64" if container.arch == "arm64"
            else "sysv_x86_64"
        )
        return emulated.emulate(
            data, container,
            function_va=sink.function_va,
            dest_rel=int(sink.dest_rel or 0),
            capacity=capacity,
            abi=abi,
            copy_kind=kind, callee=callee,
        )
    return None


def _primary_repair_function(sinks: list[Sink]) -> int | None:
    """Pick one deterministic function for the repaired candidate.

    v5 runtime evidence executes exactly one repaired function.  Patching
    unrelated functions discovered by a whole-image scan (for example a
    statically linked C runtime's own memcpy wrapper) would ship patches that
    the native/emulated cases never execute.  Prefer an unbounded-copy guard
    sink, then the earliest call site, and keep every action inside that one
    function.  Additional vulnerable functions are left for a later pass and
    are reported as a limitation.
    """
    if not sinks:
        return None
    preferred = [sink for sink in sinks if sink.kind == "unbounded_copy"]
    pool = preferred or sinks
    chosen = min(pool, key=lambda sink: (int(sink.function_va or 0), int(sink.call_va or 0)))
    return int(chosen.function_va or 0)


def _generic_repair(
    data: bytes,
    container: ContainerInfo,
    *,
    strategy: str,
    verify: bool,
    allow_static_only: bool,
    poc_manifest: dict[str, Any] | None = None,
) -> RepairOutcome:
    analysis = analyze(data)
    all_sinks = analysis.patchable()
    report = _base_report(data, container)
    if not all_sinks:
        report.limitations = list(analysis.limitations)
        report.error = report.limitations[-1] if report.limitations else "unsupported"
        report.universal["reason"] = report.error
        _set_disposition(report, "analysis_only")
        return RepairOutcome(None, report)

    function_va = _primary_repair_function(all_sinks)
    sinks = [
        sink for sink in all_sinks
        if int(sink.function_va or 0) == function_va
    ] or all_sinks[:1]
    skipped = len(all_sinks) - len(sinks)
    if skipped:
        report.limitations.append(
            f"{skipped} patchable sink(s) in other functions were not patched; "
            "v5 repairs one function per candidate and the runtime gate executes "
            "that function only"
        )

    report.findings = [_sink_to_finding(sink) for sink in sinks]
    result = repair_with_sinks(data, container, sinks)
    report.limitations.extend(result.limitations)
    report.signature_invalidated = result.signature_invalidated
    report.codesign_invalidated = result.codesign_invalidated
    if not result.ok or result.patched is None:
        report.status = "unsupported"
        report.supported = False
        report.error = report.limitations[-1] if report.limitations else "repair failed"
        report.universal["reason"] = report.error
        _set_disposition(report, "unsupported")
        return RepairOutcome(None, report)

    return finish_candidate(
        data, container, result.patched, sinks, [dict(a) for a in result.actions],
        report=report, requested_strategy=strategy,
        verify=verify, allow_static_only=allow_static_only,
        poc_manifest=poc_manifest,
    )


def finish_candidate(
    data: bytes,
    container: ContainerInfo,
    patched: bytes,
    sinks: list[Sink],
    actions: list[dict[str, Any]],
    *,
    report: UnifiedBinaryReport,
    requested_strategy: str = "auto",
    strategy_check: bool = True,
    verify: bool,
    allow_static_only: bool,
    poc_manifest: dict[str, Any] | None = None,
) -> RepairOutcome:
    """Apply the shared reparse/runtime/gate tail to any produced candidate.

    Used by the deterministic writer and by both AI binary-repair paths.  The
    candidate bytes may come from a template writer or from an AI-supplied
    machine-code/byte patch; the deterministic gate is the only authority that
    can turn them into ``verified_patch``.
    """
    report.actions = [dict(action) for action in actions]
    report.offsets = [
        int(action["offset"]) for action in actions
        if isinstance(action.get("offset"), int)
    ]
    report.patched_sha256 = _sha(patched)
    report.candidate_available = True
    kinds = {str(action.get("kind")) for action in actions}
    if "guard" in kinds:
        report.strategy = "guard"
    elif kinds and kinds <= {"immediate"}:
        report.strategy = "immediate"
    elif not report.strategy or report.strategy == "none":
        report.strategy = "ai-bytes"
    report.mode = report.strategy
    guard_sink = next((sink for sink in sinks if sink.kind == "unbounded_copy"), None)
    report.capacity = guard_sink.capacity if guard_sink is not None else sinks[0].capacity

    if strategy_check and not plans_strategy(repair_cell(container) or _NO_CELL, requested_strategy):
        report.supported = False
        report.candidate_available = False
        report.error = f"requested strategy {requested_strategy} is not in the repair matrix"
        _set_disposition(report, "unsupported")
        return RepairOutcome(None, report)

    patched_container = detect_container(patched)
    reparse_ok = (
        patched_container.format == container.format
        and patched_container.arch == container.arch
        and not patched_container.limitations
    )
    if not reparse_ok:
        report.supported = False
        report.candidate_available = False
        report.status = "rejected"
        report.error = "patched candidate failed container reparse"
        report.patched_sha256 = _sha(data)
        _set_disposition(report, "rejected")
        return RepairOutcome(None, report)

    if not verify:
        tier = "static_only"
        report.status = "not_verified"
        report.supported = False
        report.verification = {"tier": tier, "static_reparse": True}
        disposition = "static_only_patch" if allow_static_only else "not_verified"
        _set_disposition(
            report, disposition,
            verified=False, download_allowed=allow_static_only, tier=tier,
        )
        if not allow_static_only:
            report.error = "runtime verification was not requested"
        else:
            report.warnings.append(
                "static-only candidate: no runtime evidence; not a verified repair"
            )
        return RepairOutcome(
            patched if allow_static_only else None, report,
            verified=False, download_allowed=allow_static_only,
        )

    from app.services.unified_verification import build as build_unified

    runtime_sink = guard_sink if guard_sink is not None else (sinks[0] if sinks else None)
    runtime = None
    if runtime_sink is not None:
        runtime = _select_runtime(patched, patched_container, runtime_sink)
    if runtime is not None:
        report.runtime = runtime.to_dict()
    poc = None
    if runtime is not None and runtime_sink is not None:
        # PoC-style differential predicate: the same runtime probe must fail on
        # the original bytes and pass on the candidate.  This is still
        # instruction-level emulation/native function execution, not a guest
        # kernel replay; it is a required predicate when the original runtime is
        # available for the selected sink.
        original_runtime = _select_runtime(data, container, runtime_sink)
        if (
            original_runtime is not None
            and original_runtime.verdict in {"pass", "fail"}
            and original_runtime.cases
        ):
            poc = {
                "kind": "capacity_overflow_differential",
                "engine": original_runtime.engine,
                "tier": original_runtime.tier,
                "inputs": sorted({case.input_len for case in original_runtime.cases}),
                "original_verdict": original_runtime.verdict,
                "candidate_verdict": runtime.verdict,
                "original_cases": [case.to_dict() for case in original_runtime.cases],
            }
        else:
            report.limitations.append(
                "PoC differential predicate was not added: original runtime "
                "evidence is unavailable for this sink"
            )
    external_poc = None
    if poc_manifest is not None:
        try:
            from app.services.poc_runner import run_poc

            external_poc = run_poc(data, patched, poc_manifest).to_dict()
            report.poc = external_poc
            if external_poc.get("status") == "unavailable":
                report.limitations.append(
                    "PoC manifest was supplied but no runtime runner is available "
                    "on this host; the gate will not claim verification"
                )
        except Exception as exc:  # noqa: BLE001
            external_poc = {
                "schema_version": 1, "status": "fail", "runner": "",
                "limitations": [f"PoC runner error: {type(exc).__name__}: {exc}"],
            }
            report.poc = external_poc
            report.limitations.append(external_poc["limitations"][0])
    verification = build_unified(
        format_name=container.format,
        arch=container.arch,
        original=data,
        candidate=patched,
        actions=report.actions,
        runtime=runtime,
        reparse_ok=reparse_ok,
        original_sha256=report.original_sha256,
        patched_sha256=report.patched_sha256,
        poc=poc,
        external_poc=external_poc,
    )
    report.verification = {
        "packet": verification.packet,
        "gate": asdict(verification.gate),
        "tier": verification.packet["scope"]["runtime_tier"],
        "engine": runtime.engine if runtime is not None else "",
        "static_reparse": True,
    }
    gate = verification.gate
    if gate.success:
        report.status = "patched"
        report.supported = True
        report.candidate_available = True
        _set_disposition(
            report, "verified_patch",
            verified=True, download_allowed=True,
            tier=verification.packet["scope"]["runtime_tier"],
        )
        return RepairOutcome(patched, report, verified=True, download_allowed=True)

    tier = verification.packet["scope"]["runtime_tier"]
    report.supported = False
    if gate.outcome == "rejected":
        report.status = "not_verified"
        report.candidate_available = False
        report.error = f"verification gate did not pass: {gate.reason}"
        _set_disposition(report, "rejected", tier=tier)
        return RepairOutcome(None, report)

    report.status = "not_verified"
    if allow_static_only:
        _set_disposition(
            report, "static_only_patch",
            verified=False, download_allowed=True, tier="static_only",
        )
        report.warnings.append(
            "runtime evidence is unavailable; the candidate is static-only and "
            "must not be reported as a verified repair"
        )
        return RepairOutcome(patched, report, verified=False, download_allowed=True)
    report.error = (
        "runtime evidence is unavailable; re-run with allow_static_only to "
        "obtain an unverified candidate"
    )
    _set_disposition(report, "not_verified", tier=tier)
    return RepairOutcome(None, report)


class _NoCell:
    strategies: tuple[str, ...] = ()
    container = ""
    arch = ""
    bits = 0
    endian = ""


_NO_CELL = _NoCell()


def repair_any(
    data: bytes,
    *,
    backend: str = "auto",
    strategy: str = "auto",
    verify: bool = True,
    allow_static_only: bool = False,
    poc_manifest: dict[str, Any] | None = None,
) -> RepairOutcome:
    """Repair any input; return a deterministic disposition and optional bytes.

    A candidate is returned only when it is verified, or when
    ``allow_static_only`` is explicitly enabled (then ``verified`` is false).
    """
    container = detect_container(data)
    fmt, arch = container.format, container.arch

    if len(data) > MAX_INPUT_BYTES or len(data) == 0:
        reason = "empty input" if not data else f"input exceeds {MAX_INPUT_BYTES} bytes"
        report = _base_report(data, container)
        report.status = "unsupported"
        report.error = reason
        report.limitations = [reason]
        report.universal["reason"] = reason
        _set_disposition(report, "invalid")
        return RepairOutcome(None, report)

    report = _base_report(data, container)
    if fmt not in _CONTAINER_FORMATS:
        report.status = "unsupported"
        report.error = (
            container.limitations[-1] if container.limitations
            else "unrecognised container magic"
        )
        report.limitations = list(container.limitations) or [report.error]
        _set_disposition(report, "invalid")
        return RepairOutcome(None, report)
    if container.arch in {"", "unknown"} or container.bits is None:
        report.status = "unsupported"
        report.error = (
            container.limitations[-1] if container.limitations
            else f"malformed {fmt} container"
        )
        report.limitations = list(container.limitations) or [report.error]
        _set_disposition(report, "invalid")
        return RepairOutcome(None, report)

    if backend != "auto" and backend != fmt:
        report.error = f"requested backend {backend} does not match {fmt}"
        report.limitations = [report.error]
        _set_disposition(report, "unsupported")
        return RepairOutcome(None, report)

    cell = repair_cell(container)
    if cell is None:
        reason = (
            f"no repair backend for {fmt}/{arch}"
            if container.endian == "little"
            else f"big-endian {fmt}/{arch} is outside the repair matrix"
        )
        report.error = reason
        report.limitations = [reason]
        report.universal["reason"] = reason
        _set_disposition(report, "unsupported")
        return RepairOutcome(None, report)

    if fmt == "elf" and arch == "x86_64":
        # The legacy ELF x86-64 engine repairs the old syscall fixture.  The v4/v5
        # generic analyzer owns guard/immediate repair for the new ELF x86-64
        # fixture; route those sinks through the container-neutral writer so the
        # same deterministic one-function policy and runtime gate apply.
        if any(sink.kind == "unbounded_copy" for sink in analyze(data).patchable()):
            return _generic_repair(
                data, container, strategy=strategy, verify=verify,
                allow_static_only=allow_static_only,
                poc_manifest=poc_manifest,
            )
        from app.services.binary_repair_engine import repair_elf

        try:
            patched, raw = repair_elf(data)
        except Exception as exc:  # noqa: BLE001 - malformed input is evidence, not a crash
            report.status = "unsupported"
            report.error = f"ELF parse failure: {type(exc).__name__}: {exc}"
            report.limitations = [report.error]
            _set_disposition(report, "invalid")
            return RepairOutcome(None, report)
        report = _from_elf_legacy(container, data, patched, raw, verify=verify)
        if strategy != "auto" and (
            report.strategy != strategy or not plans_strategy(cell, strategy)
        ):
            report.error = f"requested strategy {strategy} does not match selected {report.strategy}"
            report.supported = False
            report.candidate_available = False
            report.limitations.append(report.error)
            _set_disposition(report, "unsupported")
            return RepairOutcome(None, report)
        if patched is None:
            report.supported = False
            report.error = report.limitations[-1] if report.limitations else "unsupported"
            report.universal["reason"] = report.error
            _set_disposition(report, "analysis_only")
            return RepairOutcome(None, report)
        if not verify:
            report.status = "not_verified"
            disposition = "static_only_patch" if allow_static_only else "not_verified"
            _set_disposition(
                report, disposition,
                verified=False, download_allowed=allow_static_only, tier="static_only",
            )
            if allow_static_only:
                report.warnings.append(
                    "static-only candidate: no runtime evidence; not a verified repair"
                )
            else:
                report.candidate_available = False
                report.error = "runtime verification was not requested"
            return RepairOutcome(
                patched if allow_static_only else None, report,
                verified=False, download_allowed=allow_static_only,
            )
        gate = (report.verification or {}).get("gate") or {}
        if gate.get("success") is True:
            report.status = "patched"
            report.supported = True
            report.candidate_available = True
            _set_disposition(
                report, "verified_patch",
                verified=True, download_allowed=True,
                tier=report.verification.get("tier") or "emulated_run",
            )
            return RepairOutcome(patched, report, verified=True, download_allowed=True)
        report.status = "not_verified"
        report.candidate_available = False
        report.supported = False
        if not report.error:
            report.error = "verification gate did not pass"
        _set_disposition(report, "rejected", tier=report.verification.get("tier") or "")
        return RepairOutcome(None, report)

    outcome = _generic_repair(
        data, container,
        strategy=strategy, verify=verify, allow_static_only=allow_static_only,
    )
    outcome.report.matrix = _matrix_dict(cell)
    return outcome


def repair_binary(
    data: bytes,
    *,
    backend: str = "auto",
    strategy: str = "auto",
    verify: bool = True,
) -> tuple[bytes | None, UnifiedBinaryReport]:
    """Backward-compatible wrapper around :func:`repair_any`.

    ``verify=False`` maps to ``allow_static_only=True`` so callers that
    explicitly ask for an unverified candidate keep receiving bytes, but the
    report now says ``not_verified``/``static_only_patch``.
    """
    outcome = repair_any(
        data, backend=backend, strategy=strategy,
        verify=verify, allow_static_only=not verify,
    )
    candidate = outcome.candidate if outcome.download_allowed else None
    return candidate, outcome.report
