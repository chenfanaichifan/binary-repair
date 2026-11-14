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
    resolve_profile,
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


def _capacity_payload_capacity(capacity: dict[str, Any] | None) -> int | None:
    """Best-effort capacity value from a reviewed capacity payload."""
    if not isinstance(capacity, dict):
        return None
    value = capacity.get("capacity")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    sites = capacity.get("sites")
    if isinstance(sites, list):
        for site in sites:
            if not isinstance(site, dict):
                continue
            for key in ("capacity", "block_size", "size"):
                size = site.get(key)
                if isinstance(size, int) and not isinstance(size, bool) and size > 0:
                    return size
    return None


def _evidence_profile(
    *,
    external_poc: dict[str, Any] | None,
    runtime: Any,
    destination_kind: str,
    requested_strategy: str,
    report_strategy: str,
    capacity_payload: dict[str, Any] | None = None,
    rewrite_actions: list[dict[str, Any]] | None = None,
) -> str:
    """Choose the declared evidence profile for one produced candidate.

    Priorities (declared in ``repair_matrix.resolve_profile``):

    * capacity strategy or rewrite evidence -> ``native_poc_rewrite``;
    * external PoC manifest -> ``native_poc``;
    * non-stack (heap/global) destination -> ``native_poc`` (never the
      stack/Unicorn oracle);
    * otherwise -> ``emulated_instruction`` with the existing runtime evidence.
    """
    capacity = (
        str(requested_strategy or "") == "capacity"
        or str(report_strategy or "") == "capacity"
        or capacity_payload is not None
    )
    return resolve_profile(
        has_runtime=runtime is not None,
        has_external_poc=external_poc is not None,
        has_rewrite_actions=bool(rewrite_actions),
        capacity=capacity,
        destination_kind=destination_kind,
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
    rewrite_actions: list[dict[str, Any]] | None = None,
    capacity: dict[str, Any] | None = None,
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
    elif capacity is not None or (kinds and kinds <= {"capacity_check_rewrite"}):
        # Reviewed duplicated-capacity-check rewrite: the engine action kind (or
        # an explicit capacity payload) names the strategy, never "ai-bytes".
        report.strategy = "capacity"
    elif not report.strategy or report.strategy == "none":
        report.strategy = "ai-bytes"
    report.mode = "capacity-check" if report.strategy == "capacity" else report.strategy
    guard_sink = next((sink for sink in sinks if sink.kind == "unbounded_copy"), None)
    if guard_sink is not None:
        report.capacity = guard_sink.capacity
    elif sinks:
        report.capacity = sinks[0].capacity
    else:
        # Capacity-check candidates carry no analyzer Sink; the reviewed
        # capacity payload (or its first site) names the block capacity.
        report.capacity = _capacity_payload_capacity(capacity)

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
    # The analyzer classifies the destination storage (the heap engine adds
    # ``destination_kind``; until then every sink is a stack destination).  A
    # heap/global destination must never be accepted through the stack/Unicorn
    # oracle: that is an acceptance-model mismatch, so it falls back to the
    # external PoC profile with no runtime evidence.
    destination_kind = str(getattr(runtime_sink, "destination_kind", "stack") or "stack")
    runtime = None
    if runtime_sink is not None and destination_kind == "stack":
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
    profile = _evidence_profile(
        external_poc=external_poc,
        runtime=runtime,
        destination_kind=destination_kind,
        requested_strategy=requested_strategy,
        report_strategy=report.strategy,
        capacity_payload=capacity,
        rewrite_actions=rewrite_actions,
    )
    cell = repair_cell(container)
    # The declared evidence model for the external-PoC profiles is the manifest
    # differential; the stack/Unicorn runtime model is not part of that claim,
    # so the two oracles are never mixed in one gate packet.
    external_model = profile in {"native_poc", "native_poc_rewrite"}
    verification = build_unified(
        format_name=container.format,
        arch=container.arch,
        original=data,
        candidate=patched,
        actions=report.actions,
        runtime=None if external_model else runtime,
        reparse_ok=reparse_ok,
        original_sha256=report.original_sha256,
        patched_sha256=report.patched_sha256,
        poc=None if external_model else poc,
        external_poc=external_poc,
        profile=profile,
        rewrite_actions=rewrite_actions,
        cell=cell.to_dict() if cell is not None else None,
        capacity=capacity,
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


# ---------------------------------------------------------------------------
# Reviewed capacity-check rewrite (Lead-owned engine + shared gate tail).
# ---------------------------------------------------------------------------

def _capacity_engine():
    """Lazily resolve the reviewed capacity-check rewrite engine.

    The engine lives in its own optional module, so the import stays lazy: the
    pipeline remains importable without it and tests can substitute the
    returned callable.
    """
    from app.services.repair.capacity import repair_capacity_confusion

    return repair_capacity_confusion


def _capacity_payload(cap_report: Any) -> dict[str, Any]:
    """Canonical capacity payload for the unified gate.

    Starts from the engine's own ``to_dict()`` and pins the exact action list
    the gate re-derives from the original/candidate bytes.
    """
    payload: dict[str, Any] = {}
    if hasattr(cap_report, "to_dict"):
        try:
            candidate = cap_report.to_dict()
        except Exception:  # noqa: BLE001 - report rendering must not hide bytes
            candidate = None
        if isinstance(candidate, dict):
            payload.update(candidate)
    actions: list[dict[str, Any]] = []
    for item in getattr(cap_report, "actions", []) or []:
        if hasattr(item, "to_dict"):
            actions.append(dict(item.to_dict()))
        elif isinstance(item, dict):
            actions.append(dict(item))
    payload["actions"] = actions
    payload.setdefault("sites", [])
    payload.setdefault("message_actions", [])
    if not isinstance(payload.get("limitations"), list):
        payload["limitations"] = [str(payload["limitations"])]
    return payload


def _finish_capacity(
    data: bytes,
    container: ContainerInfo,
    patched: bytes,
    report: UnifiedBinaryReport,
    actions: list[dict[str, Any]],
    payload: dict[str, Any],
    *,
    requested_strategy: str,
    verify: bool,
    allow_static_only: bool,
    poc_manifest: dict[str, Any] | None,
) -> RepairOutcome:
    """Gate one capacity candidate through the shared reparse/evidence tail.

    ``finish_candidate`` derives strategy ``capacity``/mode ``capacity-check``
    from the action kind, keeps the runtime oracle out of this profile (the
    rewrites have no stack/Unicorn execution model), selects the declared
    ``native_poc_rewrite`` profile and makes the unified gate re-derive every
    rewrite action from the original/candidate bytes.  Without a PoC/regression
    manifest there is no runtime evidence, so the result stays
    ``not_verified``/inconclusive and never ``verified_patch``.
    """
    outcome = finish_candidate(
        data,
        container,
        patched,
        [],
        actions,
        report=report,
        requested_strategy=requested_strategy,
        verify=verify,
        allow_static_only=allow_static_only,
        poc_manifest=poc_manifest,
        rewrite_actions=actions,
        capacity=payload,
    )
    verification = outcome.report.verification
    if isinstance(verification, dict) and not verification.get("engine"):
        # Keep the reviewed profile observable in the packet without changing
        # any gate check or verdict.
        verification["engine"] = "capacity-check"
    return outcome


def _attempt_capacity(
    data: bytes,
    container: ContainerInfo,
    *,
    requested_strategy: str,
    verify: bool,
    allow_static_only: bool,
    poc_manifest: dict[str, Any] | None,
) -> tuple[RepairOutcome | None, list[str]]:
    """Try the reviewed duplicated-capacity-check rewrite.

    Returns ``(outcome, diagnostics)``; ``outcome`` is ``None`` when the engine
    found no reviewed site (fail-closed) and the caller keeps its own report.
    """
    try:
        engine = _capacity_engine()
    except Exception as exc:  # noqa: BLE001 - optional engine must not crash the pipeline
        return None, [f"capacity-check engine unavailable: {type(exc).__name__}: {exc}"]
    try:
        patched, cap_report = engine(data)
    except Exception as exc:  # noqa: BLE001 - malformed input is evidence, not a crash
        return None, [f"capacity-check engine error: {type(exc).__name__}: {exc}"]
    if patched is None:
        return None, [
            str(item) for item in (getattr(cap_report, "limitations", None) or [])
            if str(item).strip()
        ]
    payload = _capacity_payload(cap_report)
    actions = [dict(item) for item in payload.get("actions", []) if isinstance(item, dict)]
    if not actions:
        return None, ["capacity-check engine produced a candidate without rewrite actions"]
    report = _base_report(data, container)
    report.mode = "capacity-check"
    report.strategy = "capacity"
    report.findings = [
        dict(site) for site in payload.get("sites", []) if isinstance(site, dict)
    ]
    report.limitations = [
        str(item) for item in payload.get("limitations", [])
        if str(item).strip() and str(item) not in report.limitations
    ]
    return _finish_capacity(
        data, container, patched, report, actions, payload,
        requested_strategy=requested_strategy,
        verify=verify,
        allow_static_only=allow_static_only,
        poc_manifest=poc_manifest,
    ), []


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
        # The reviewed duplicated-capacity-check rewrite has its own engine and
        # evidence profile: it is selected explicitly, or tried as the
        # fail-closed fallback when the legacy immediate engine finds nothing.
        # Its only runtime evidence is the caller-supplied PoC/regression
        # manifest executed by a native/emulated guest; without that evidence
        # the gate stays inconclusive (never verified_patch).
        if strategy == "capacity":
            cap_outcome, diagnostics = _attempt_capacity(
                data, container,
                requested_strategy="capacity", verify=verify,
                allow_static_only=allow_static_only, poc_manifest=poc_manifest,
            )
            if cap_outcome is not None:
                return cap_outcome
            report.strategy = "capacity"
            report.mode = "capacity-check"
            report.supported = False
            report.error = (
                diagnostics[-1] if diagnostics
                else "no reviewed capacity-check divergence was found"
            )
            report.limitations = list(diagnostics) or [report.error]
            report.universal["reason"] = report.error
            _set_disposition(report, "analysis_only")
            return RepairOutcome(None, report)
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
            # Legacy engine found nothing: fall back to the reviewed capacity
            # rewrite (the only deterministic capability that covers a
            # runtime-length copy behind an inlined duplicated range check).
            if strategy == "auto" and plans_strategy(cell, "capacity"):
                cap_outcome, diagnostics = _attempt_capacity(
                    data, container,
                    requested_strategy="capacity", verify=verify,
                    allow_static_only=allow_static_only,
                    poc_manifest=poc_manifest,
                )
                if cap_outcome is not None:
                    return cap_outcome
                for text in diagnostics:
                    if text not in report.limitations:
                        report.limitations.append(text)
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
