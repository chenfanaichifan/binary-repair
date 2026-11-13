"""Unified, fail-closed dispatch for direct binary repair (v4).

The pipeline is container-neutral:

* ``containers.detect_container`` identifies ELF / PE / Mach-O and resolves
  imported call targets (PLT, IAT/thunk, Mach-O stubs);
* ``repair.analyzer`` recovers stack-buffer copy sinks and their capacity;
* ``repair.writer`` applies in-place immediate patches or injects an executable
  guard section and redirects the call;
* Mach-O candidates are verified by native execution on macOS; PE and AArch64
  ELF candidates by Unicorn instruction-level execution.

Anything outside the declared matrix returns ``unsupported`` without writing a
candidate.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.containers import ContainerInfo, detect_container
from app.services.repair.analyzer import Analysis, Sink, analyze
from app.services.repair.guards import abi_for
from app.services.repair.writer import repair_with_sinks
from app.services.runtime import emulated, macho_native

MAX_INPUT_BYTES = 20 * 1024 * 1024

SUPPORTED_REPAIR = {
    ("elf", "x86_64"),
    ("elf", "arm64"),
    ("pe", "x86_64"),
    ("pe", "arm64"),
    ("macho", "arm64"),
    ("macho", "x86_64"),
}


@dataclass
class UnifiedBinaryReport:
    """One report shape for ELF, PE and Mach-O (schema v3)."""

    schema_version: int = 3
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

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "findings": [dict(item) for item in self.findings],
            "actions": [dict(item) for item in self.actions],
        }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
    fmt = container.format if container.format in {
        "elf", "pe", "macho", "macho-fat",
    } else "unknown"
    arch = container.arch if fmt != "unknown" else "unknown"
    return fmt, arch, container.bits


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
        "detail": sink.detail,
    }


def scan_binary(data: bytes) -> dict[str, Any]:
    """Scan any supported container; never writes or executes."""
    if len(data) > MAX_INPUT_BYTES:
        return {
            "schema_version": 3,
            "format": "unknown",
            "arch": "unknown",
            "backend": "none",
            "supported": False,
            "repair_supported": False,
            "findings": [],
            "limitations": [f"input exceeds {MAX_INPUT_BYTES} bytes"],
        }
    analysis: Analysis = analyze(data)
    container = analysis.container
    repair_supported = bool(analysis.patchable()) and (
        (container.format, container.arch) in SUPPORTED_REPAIR
    )
    result: dict[str, Any] = {
        "schema_version": 3,
        "format": container.format,
        "arch": container.arch,
        "bits": container.bits,
        "backend": container.format,
        "supported": container.format in {"elf", "pe", "macho", "macho-fat"},
        "repair_supported": repair_supported,
        "findings": [_sink_to_finding(sink) for sink in analysis.sinks],
        "limitations": list(analysis.limitations),
        "container": _container_dict(container),
    }
    if not result["supported"]:
        result["limitations"].append(
            f"{container.format}/{container.arch} is outside the repair matrix"
        )
    return result


def _base_report(data: bytes, container: ContainerInfo) -> UnifiedBinaryReport:
    return UnifiedBinaryReport(
        format=container.format if container.format != "unknown" else "unknown",
        arch=container.arch,
        backend=container.format,
        original_sha256=_sha(data),
        patched_sha256=_sha(data),
        container=_container_dict(container),
        universal={
            "detected": container.format in {"elf", "pe", "macho", "macho-fat"},
            "repairable": (container.format, container.arch) in SUPPORTED_REPAIR,
            "reason": "",
        },
    )


def _unsupported(container: ContainerInfo, data: bytes, reason: str) -> UnifiedBinaryReport:
    report = _base_report(data, container)
    report.limitations = [reason]
    report.error = reason
    report.universal["reason"] = reason
    return report


def _from_elf_legacy(container: ContainerInfo, data: bytes, patched: bytes | None,
                     raw: Any, *, verify: bool) -> UnifiedBinaryReport:
    report = _base_report(data, container)
    report.backend = raw.backend or "elf"
    report.strategy = raw.strategy or "none"
    report.status = raw.status or ("patched" if patched else "unsupported")
    report.supported = bool(raw.supported and patched is not None)
    report.mode = raw.mode
    report.capacity = raw.capacity
    report.findings = [dict(item) for item in raw.findings]
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
                report.status = "not_verified"
                report.limitations.append(
                    f"verification gate did not pass: {verification.gate.reason}"
                )
        except Exception as exc:  # noqa: BLE001
            report.status = "not_verified"
            report.limitations.append(
                f"verification unavailable: {type(exc).__name__}: {exc}"
            )
    if patched is not None:
        report.verification.setdefault("static_reparse", True)
    return report


def _select_runtime(data: bytes, container: ContainerInfo, sink: Sink):
    capacity = int(sink.capacity or 0)
    if container.format == "macho":
        if not macho_native.available():
            return None
        return macho_native.run(data, arch=container.arch, capacity=capacity)
    if container.format == "pe" and container.arch in {"x86_64", "arm64"}:
        return emulated.emulate(
            data, container,
            function_va=sink.function_va,
            dest_rel=int(sink.dest_rel or 0),
            capacity=capacity,
            abi=abi_for(container.format, container.arch),
        )
    if container.format == "elf" and container.arch == "arm64":
        return emulated.emulate(
            data, container,
            function_va=sink.function_va,
            dest_rel=int(sink.dest_rel or 0),
            capacity=capacity,
            abi="aapcs64",
        )
    return None


def repair_binary(
    data: bytes,
    *,
    backend: str = "auto",
    strategy: str = "auto",
    verify: bool = True,
) -> tuple[bytes | None, UnifiedBinaryReport]:
    """Dispatch to a supported repair backend; fail closed otherwise."""
    container = detect_container(data)
    fmt, arch = container.format, container.arch

    if len(data) > MAX_INPUT_BYTES:
        return None, _unsupported(container, data, f"input exceeds {MAX_INPUT_BYTES} bytes")
    if backend != "auto" and backend != fmt:
        return None, _unsupported(
            container, data, f"requested backend {backend} does not match {fmt}"
        )
    if (fmt, arch) not in SUPPORTED_REPAIR:
        return None, _unsupported(container, data, f"no repair backend for {fmt}/{arch}")

    # The reviewed ELF x86-64 engine keeps its strict-template and immediate
    # strategies and its existing structured gate.
    if fmt == "elf" and arch == "x86_64":
        from app.services.binary_repair_engine import repair_elf

        patched, raw = repair_elf(data)
        report = _from_elf_legacy(container, data, patched, raw, verify=verify)
        if strategy != "auto" and report.strategy != strategy:
            return None, _unsupported(
                container, data,
                f"requested strategy {strategy} does not match selected {report.strategy}",
            )
        if patched is None:
            report.supported = False
            report.error = report.limitations[-1] if report.limitations else "unsupported"
            report.universal["reason"] = report.error
            return None, report
        if not report.candidate_available:
            report.error = "candidate is unchanged"
            return None, report
        return patched, report

    analysis = analyze(data)
    sinks = analysis.patchable()
    report = _base_report(data, container)
    if not sinks:
        report.limitations = list(analysis.limitations)
        report.error = report.limitations[-1] if report.limitations else "unsupported"
        report.universal["reason"] = report.error
        return None, report
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
        return None, report

    patched = result.patched
    report.actions = [dict(action) for action in result.actions]
    report.offsets = [
        int(action["offset"]) for action in result.actions
        if isinstance(action.get("offset"), int)
    ]
    report.patched_sha256 = _sha(patched)
    report.candidate_available = True
    report.status = "patched"
    report.supported = True
    has_guard = any(action["kind"] == "guard" for action in result.actions)
    report.strategy = "guard" if has_guard else "immediate"
    report.mode = report.strategy
    guard_sink = next((sink for sink in sinks if sink.kind == "unbounded_copy"), None)
    report.capacity = guard_sink.capacity if guard_sink is not None else sinks[0].capacity

    if strategy != "auto" and report.strategy != strategy:
        return None, _unsupported(
            container, data,
            f"requested strategy {strategy} does not match selected {report.strategy}",
        )

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
        return None, report

    if verify:
        from app.services.unified_verification import build as build_unified

        runtime = None
        if guard_sink is not None:
            runtime = _select_runtime(patched, patched_container, guard_sink)
        if runtime is not None:
            report.runtime = runtime.to_dict()
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
        )
        report.verification = {
            "packet": verification.packet,
            "gate": asdict(verification.gate),
            "tier": verification.packet["scope"]["runtime_tier"],
            "engine": runtime.engine if runtime is not None else "",
            "static_reparse": True,
        }
        if not verification.gate.success:
            report.supported = False
            report.candidate_available = False
            report.status = "not_verified"
            report.error = f"verification gate did not pass: {verification.gate.reason}"
            return None, report
    else:
        report.verification.setdefault("tier", "static_only")
        report.verification.setdefault("static_reparse", True)

    report.status = "patched"
    return patched, report
