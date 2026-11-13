"""Unified, fail-closed dispatch for direct binary repair.

The concrete byte-rewriting engines live in ``binary_repair_engine`` (ELF),
``arm64_repair`` (AArch64 ELF), ``pe_repair`` and ``macho_repair``.  This module
only chooses a backend, normalizes the result and records static verification.

It is deliberately not a universal decompiler/recompiler.  Any format,
architecture or pattern outside the declared matrix returns ``unsupported``
without writing a candidate.
"""
from __future__ import annotations

import hashlib
import io
import struct
from dataclasses import asdict, dataclass, field
from typing import Any

import lief
from elftools.elf.elffile import ELFFile

from app.services.arm64_repair import repair_arm64, scan_arm64
from app.services.binary_repair_engine import (
    BinaryRepairReport,
    repair_elf,
    scan_elf,
)
from app.services.format_scan import scan_macho as scan_macho_meta
from app.services.format_scan import scan_pe as scan_pe_meta
from app.services.macho_repair import repair_macho, scan_macho
from app.services.pe_repair import (
    repair_pe,
    repair_pe_memcpy,
    scan_pe_copy_calls,
    scan_pe_memcpy_calls,
)

MAX_INPUT_BYTES = 20 * 1024 * 1024

ELF_MACHINES = {
    3: "i386",
    8: "mips",
    20: "powerpc",
    40: "arm",
    62: "x86_64",
    183: "arm64",
    243: "riscv",
}

SUPPORTED_REPAIR = {
    ("elf", "x86_64"),
    ("elf", "arm64"),
    ("pe", "x86_64"),
    ("macho", "arm64"),
    ("macho", "x86_64"),
}


@dataclass
class UnifiedBinaryReport:
    """One report shape for ELF, PE and Mach-O."""

    schema_version: int = 2
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
    limitations: list[str] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    signature_invalidated: bool = False
    codesign_invalidated: bool = False
    candidate_available: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "findings": [dict(item) for item in self.findings],
        }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _elf_arch(data: bytes) -> tuple[str, str, int | None]:
    if data[:4] != b"\x7fELF" or len(data) < 20:
        return "unknown", "unknown", None
    bits = 64 if data[4] == 2 else 32 if data[4] == 1 else None
    endian = "<" if data[5] == 1 else ">" if data[5] == 2 else "<"
    try:
        machine = struct.unpack_from(endian + "H", data, 18)[0]
    except struct.error:
        return "elf", "unknown", bits
    return "elf", ELF_MACHINES.get(machine, f"em_{machine}"), bits


def detect_format(data: bytes) -> tuple[str, str, int | None]:
    """Return ``(format, arch, bits)`` without executing the file."""
    fmt, arch, bits = _elf_arch(data)
    if fmt == "elf":
        return fmt, arch, bits

    if data[:2] == b"MZ":
        try:
            pe = lief.PE.parse(list(data))
        except Exception:  # noqa: BLE001
            return "pe", "unknown", None
        if pe is None:
            return "pe", "unknown", None
        machine = str(getattr(pe.header, "machine", ""))
        arch = (
            "x86_64" if "AMD64" in machine else
            "arm64" if "ARM64" in machine else
            "i386" if "I386" in machine or "386" in machine else
            "unknown"
        )
        magic = int(getattr(pe.optional_header, "magic", 0) or 0)
        bits = 64 if magic == 0x20B else 32 if magic == 0x10B else None
        return "pe", arch, bits

    if data[:4] == b"\xca\xfe\xba\xbe":
        try:
            parsed = lief.MachO.parse(list(data))
            first = parsed.at(0) if parsed is not None else None
        except Exception:  # noqa: BLE001
            first = None
        if first is None:
            return "macho-fat", "unknown", None
        return "macho-fat", _macho_arch(first), 64

    if data[:4] in {
        b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",
        b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
    }:
        try:
            parsed = lief.MachO.parse(list(data))
            first = parsed.at(0) if parsed is not None else None
        except Exception:  # noqa: BLE001
            first = None
        if first is None:
            return "macho", "unknown", None
        return "macho", _macho_arch(first), 64 if data[:4] in {
            b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
        } else 32

    return "unknown", "unknown", None


def _macho_arch(binary: Any) -> str:
    cpu = str(getattr(getattr(binary, "header", None), "cpu_type", ""))
    if "ARM64" in cpu:
        return "arm64"
    if "X86_64" in cpu:
        return "x86_64"
    if "ARM" in cpu:
        return "arm"
    if "X86" in cpu or "I386" in cpu:
        return "i386"
    return "unknown"


def _limits_from(scan: dict[str, Any]) -> list[str]:
    limits = scan.get("limits") or scan.get("limitations") or []
    return [str(item) for item in limits]


def scan_binary(data: bytes) -> dict[str, Any]:
    """Scan any supported container; never writes or executes."""
    if len(data) > MAX_INPUT_BYTES:
        return {
            "schema_version": 2,
            "format": "unknown",
            "arch": "unknown",
            "backend": "none",
            "supported": False,
            "repair_supported": False,
            "findings": [],
            "limitations": [f"input exceeds {MAX_INPUT_BYTES} bytes"],
        }

    fmt, arch, bits = detect_format(data)
    result: dict[str, Any] = {
        "schema_version": 2,
        "format": fmt,
        "arch": arch,
        "bits": bits,
        "backend": fmt,
        "supported": fmt in {"elf", "pe", "macho", "macho-fat"},
        "repair_supported": (fmt, arch) in SUPPORTED_REPAIR,
        "findings": [],
        "limitations": [],
    }

    try:
        if fmt == "elf" and arch == "x86_64":
            scan = scan_elf(data)
            result["findings"] = scan.get("findings", [])
            result["limitations"] = _limits_from(scan)
        elif fmt == "elf" and arch == "arm64":
            scan = scan_arm64(data)
            result["findings"] = scan.get("findings", [])
            result["limitations"] = _limits_from(scan)
        elif fmt == "pe" and arch == "x86_64":
            meta = scan_pe_meta(data)
            copies = scan_pe_copy_calls(data).get("findings", [])
            memcpy = scan_pe_memcpy_calls(data).get("findings", [])
            result["findings"] = list(copies) + list(memcpy)
            result["limitations"] = [
                item for item in _limits_from(meta)
                if "not enabled" not in item.lower()
            ]
            result["sections"] = meta.get("sections", [])
            result["imports"] = meta.get("imports", [])
        elif fmt == "macho":
            scan = scan_macho(data)
            result["findings"] = scan.get("findings", [])
            result["limitations"] = [
                item for item in _limits_from(scan)
                if "not enabled" not in item.lower()
            ]
            meta = scan_macho_meta(data)
            result["sections"] = meta.get("sections", [])
        else:
            result["limitations"] = [
                f"{fmt}/{arch} is outside the repair scan matrix"
            ]
    except Exception as exc:  # noqa: BLE001
        result["supported"] = False
        result["limitations"] = [f"scan failed: {type(exc).__name__}: {exc}"]

    if not result["repair_supported"]:
        result["limitations"].append(
            f"no repair backend for {fmt}/{arch}; candidate will not be written"
        )
    return result


def _base_report(data: bytes, fmt: str, arch: str) -> UnifiedBinaryReport:
    return UnifiedBinaryReport(
        format=fmt,
        arch=arch,
        backend=fmt,
        original_sha256=_sha(data),
        patched_sha256=_sha(data),
    )


def _from_elf(
    data: bytes, patched: bytes | None, raw: BinaryRepairReport,
    *, verify: bool,
) -> UnifiedBinaryReport:
    report = _base_report(data, "elf", raw.arch or "unknown")
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
    return report


def _from_pe(data: bytes, patched: bytes | None, raw: Any) -> UnifiedBinaryReport:
    report = _base_report(data, "pe", detect_format(data)[1] or "x86_64")
    report.backend = raw.backend or "pe"
    report.strategy = raw.strategy or "none"
    report.status = raw.status or ("patched" if patched else "unsupported")
    report.supported = bool(patched is not None)
    report.mode = report.strategy
    report.findings = [dict(item) for item in raw.findings] if getattr(raw, "findings", None) else []
    report.offsets = list(getattr(raw, "offsets", []) or [])
    report.limitations = list(getattr(raw, "limitations", []) or [])
    report.signature_invalidated = bool(getattr(raw, "signature_invalidated", False))
    if patched is not None:
        report.patched_sha256 = _sha(patched)
        report.candidate_available = True
    return report


def _from_macho(data: bytes, patched: bytes | None, raw: Any) -> UnifiedBinaryReport:
    report = _base_report(data, "macho", detect_format(data)[1] or "arm64")
    report.backend = "macho"
    report.strategy = raw.strategy or "none"
    report.status = raw.status or ("patched" if patched else "unsupported")
    report.supported = bool(patched is not None)
    report.mode = report.strategy
    report.findings = [dict(item) for item in getattr(raw, "findings", []) or []]
    report.offsets = list(getattr(raw, "offsets", []) or [])
    report.limitations = list(getattr(raw, "limitations", []) or [])
    report.codesign_invalidated = bool(getattr(raw, "codesign_invalidated", False))
    if patched is not None:
        report.patched_sha256 = _sha(patched)
        report.candidate_available = True
    return report


def _unsupported(data: bytes, fmt: str, arch: str, reason: str) -> UnifiedBinaryReport:
    report = _base_report(data, fmt, arch)
    report.limitations = [reason]
    report.error = reason
    return report


def _reparse(data: bytes, fmt: str) -> bool:
    try:
        if fmt == "elf":
            ELFFile(io.BytesIO(data))
            return True
        if fmt == "pe":
            return lief.PE.parse(list(data)) is not None
        if fmt in {"macho", "macho-fat"}:
            return lief.MachO.parse(list(data)) is not None
    except Exception:  # noqa: BLE001
        return False
    return False


def repair_binary(
    data: bytes,
    *,
    backend: str = "auto",
    strategy: str = "auto",
    verify: bool = True,
) -> tuple[bytes | None, UnifiedBinaryReport]:
    """Dispatch to a supported byte-rewrite backend; fail closed otherwise."""
    fmt, arch, _bits = detect_format(data)
    base = _base_report(data, fmt, arch)

    if len(data) > MAX_INPUT_BYTES:
        return None, _unsupported(data, fmt, arch, f"input exceeds {MAX_INPUT_BYTES} bytes")
    if backend != "auto" and backend != fmt:
        return None, _unsupported(data, fmt, arch, f"requested backend {backend} does not match {fmt}")
    if (fmt, arch) not in SUPPORTED_REPAIR:
        return None, _unsupported(data, fmt, arch, f"no repair backend for {fmt}/{arch}")

    patched: bytes | None = None
    report: UnifiedBinaryReport = base

    try:
        if fmt == "elf" and arch == "x86_64":
            patched, raw = repair_elf(data)
            report = _from_elf(data, patched, raw, verify=verify)
        elif fmt == "elf" and arch == "arm64":
            patched, raw = repair_arm64(data)
            report = _from_elf(data, patched, raw, verify=False)
        elif fmt == "pe" and arch == "x86_64":
            patched, raw = repair_pe(data)
            if patched is None:
                patched, raw = repair_pe_memcpy(data)
            report = _from_pe(data, patched, raw)
        elif fmt == "macho":
            patched, raw = repair_macho(data)
            report = _from_macho(data, patched, raw)
        else:
            return None, _unsupported(data, fmt, arch, f"no repair backend for {fmt}/{arch}")
    except Exception as exc:  # noqa: BLE001
        return None, _unsupported(data, fmt, arch, f"repair failed: {type(exc).__name__}: {exc}")

    if strategy != "auto" and report.strategy != strategy:
        return None, _unsupported(
            data, fmt, arch,
            f"requested strategy {strategy} does not match selected {report.strategy}",
        )

    if patched is None:
        report.supported = False
        report.error = report.limitations[-1] if report.limitations else "unsupported"
        return None, report
    if patched == data:
        report.supported = False
        report.error = "candidate is unchanged"
        report.candidate_available = False
        return None, report
    if not _reparse(patched, fmt):
        report.supported = False
        report.candidate_available = False
        report.status = "rejected"
        report.error = "patched candidate failed static reparse"
        return None, report

    gate = report.verification.get("gate") if isinstance(report.verification, dict) else None
    if isinstance(gate, dict) and gate.get("success") is False:
        report.supported = False
        report.candidate_available = False
        report.status = "not_verified"
        report.error = f"verification gate did not pass: {gate.get('reason') or 'incomplete evidence'}"
        return None, report

    report.verification.setdefault("static_reparse", True)
    return patched, report
