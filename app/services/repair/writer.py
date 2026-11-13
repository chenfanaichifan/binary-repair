"""Write repaired bytes for the container-neutral repair pipeline.

The writer applies two kinds of actions collected by the analyzer:

* ``immediate``: rewrite an immediate length operand in place;
* ``guard``: inject a new executable section/segment containing a bounded-copy
  guard and redirect the offending call into it.

Everything is fail-closed: if the container cannot be re-parsed after the
write, or a call site is out of range, ``patched`` is ``None`` and no partial
candidate is returned.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Any

from app.services.containers import ContainerInfo, detect_container
from app.services.repair.analyzer import Sink
from app.services.repair.guards import abi_for, build_guard

MAX_GUARD_BYTES = 256 * 1024


@dataclass
class WriteResult:
    patched: bytes | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    signature_invalidated: bool = False
    codesign_invalidated: bool = False
    injected_va: int | None = None

    @property
    def ok(self) -> bool:
        return self.patched is not None


def _patch_immediate(data: bytes, sink: Sink, value: int) -> bytes | None:
    if sink.length_offset is None:
        return None
    out = bytearray(data)
    loc = sink.length_offset
    if sink.arch == "x86_64":
        if loc < 0 or loc + 4 > len(out):
            return None
        out[loc:loc + 4] = struct.pack("<I", value & 0xFFFFFFFF)
        return bytes(out)
    if sink.arch == "arm64":
        if loc < 0 or loc + 4 > len(out):
            return None
        word = struct.unpack_from("<I", out, loc)[0]
        if (word & 0x7F800000) not in {0x52800000, 0xD2800000}:
            return None
        if value > 0xFFFF:
            return None
        word = (word & ~(0xFFFF << 5)) | ((value & 0xFFFF) << 5)
        struct.pack_into("<I", out, loc, word)
        return bytes(out)
    return None


def _inject_blob(container: ContainerInfo, data: bytes, blob: bytes) -> tuple[bytes | None, int | None, str]:
    """Add one executable block; return (bytes, va_of_block, method)."""
    if container.format == "pe":
        from app.services.pe_repair import add_rx_section

        patched, report = add_rx_section(data, blob)
        if patched is None:
            return None, None, report.limitations[-1] if report.limitations else "PE injection failed"
        va = int(container.image_base) + int(report.section_va)
        return patched, va, "pe-section"
    if container.format == "macho":
        from app.services.macho_repair import add_macho_rx_section

        patched, report = add_macho_rx_section(data, blob)
        if patched is None:
            return None, None, report.limitations[-1] if report.limitations else "Mach-O injection failed"
        return patched, int(report.section_va), "macho-section"
    if container.format == "elf":
        from app.services.code_cave import CaveError, add_rx_segment

        try:
            cave = add_rx_segment(data, blob)
        except (CaveError, ValueError, IndexError) as exc:
            return None, None, f"ELF segment injection failed: {exc}"
        return cave.data, int(cave.cave_vaddr), cave.method
    return None, None, f"no injection adapter for {container.format}"


def _redirect_call(data: bytes, sink: Sink, target_va: int) -> bytes | None:
    if sink.call_offset is None:
        return None
    out = bytearray(data)
    off = sink.call_offset
    if sink.arch == "x86_64":
        if off < 0 or off + 5 > len(out):
            return None
        original = bytes(out[off:off + sink.call_size])
        if not original or original[0] not in (0xE8, 0xFF):
            return None
        delta = target_va - (sink.call_va + 5) if sink.call_va is not None else None
        if delta is None or not -(1 << 31) <= delta < (1 << 31):
            return None
        out[off:off + 5] = b"\xE8" + struct.pack("<i", delta)
        if sink.call_size == 6:
            out[off + 5] = 0x90
        return bytes(out)
    if sink.arch == "arm64":
        if off < 0 or off + 4 > len(out):
            return None
        word = struct.unpack_from("<I", out, off)[0]
        if (word & 0xFC000000) != 0x94000000:
            return None
        if sink.call_va is None:
            return None
        delta = target_va - sink.call_va
        if delta % 4 or not -(1 << 27) <= delta < (1 << 27):
            return None
        struct.pack_into("<I", out, off, 0x94000000 | ((delta >> 2) & 0x03FFFFFF))
        return bytes(out)
    return None


def _guard_blob(container: ContainerInfo, sinks: list[Sink]) -> tuple[bytes | None, list[int], list[str]]:
    abi = abi_for(container.format, container.arch)
    blob = bytearray()
    offsets: list[int] = []
    limitations: list[str] = []
    for sink in sinks:
        capacity = int(sink.capacity or 0)
        if capacity <= 0:
            limitations.append("guard skipped: non-positive capacity")
            offsets.append(-1)
            continue
        try:
            code = build_guard(abi, sink.callee, capacity)
        except ValueError as exc:
            limitations.append(f"guard skipped: {exc}")
            offsets.append(-1)
            continue
        offsets.append(len(blob))
        blob += code
        if len(blob) > MAX_GUARD_BYTES:
            return None, [], limitations + ["guard blob exceeds the size limit"]
    if not offsets or all(offset < 0 for offset in offsets):
        return None, [], limitations or ["no guard could be built"]
    return bytes(blob), offsets, limitations


def repair_with_sinks(data: bytes, container: ContainerInfo, sinks: list[Sink]) -> WriteResult:
    """Apply analyzer sinks to the original bytes."""
    result = WriteResult()
    guard_sinks = [sink for sink in sinks if sink.kind == "unbounded_copy" and sink.patchable]
    immediate_sinks = [
        sink for sink in sinks
        if sink.kind in {"immediate_length", "memcpy_length", "syscall_length", "checked_copy"}
        and sink.patchable
    ]

    current = data
    for sink in immediate_sinks:
        capacity = int(sink.capacity or 0)
        if capacity <= 0:
            result.limitations.append("immediate patch skipped: non-positive capacity")
            continue
        patched = _patch_immediate(current, sink, capacity)
        if patched is None:
            result.limitations.append(
                f"immediate patch failed at {hex(sink.length_offset or 0)}"
            )
            continue
        current = patched
        result.actions.append({
            "kind": "immediate",
            "site": hex(sink.call_va or 0),
            "offset": sink.length_offset,
            "before": sink.length,
            "after": capacity,
            "callee": sink.callee,
        })

    if guard_sinks:
        blob, offsets, notes = _guard_blob(container, guard_sinks)
        result.limitations.extend(notes)
        if blob is None:
            return result
        injected, block_va, method = _inject_blob(container, current, blob)
        if injected is None or block_va is None:
            result.limitations.append(method)
            return result
        result.injected_va = block_va
        result.signature_invalidated = container.format == "pe"
        result.codesign_invalidated = container.format == "macho"
        for sink, offset in zip(guard_sinks, offsets):
            if offset < 0:
                result.limitations.append(
                    f"guard for {sink.callee} at {hex(sink.call_va or 0)} was not built"
                )
                continue
            target = block_va + offset
            patched = _redirect_call(injected, sink, target)
            if patched is None:
                result.limitations.append(
                    f"call redirection failed at {hex(sink.call_va or 0)} ({method})"
                )
                return result
            injected = patched
            result.actions.append({
                "kind": "guard",
                "site": hex(sink.call_va or 0),
                "callee": sink.callee,
                "capacity": sink.capacity,
                "cave_va": hex(target),
                "method": method,
            })
        current = injected

    if current == data or not result.actions:
        result.limitations.append("no repair action produced different bytes")
        return result

    check = detect_container(current)
    if check.format != container.format or check.arch != container.arch:
        result.limitations.append("patched candidate failed container reparse")
        return result
    if check.limitations:
        result.limitations.append(
            "patched candidate reparse limitations: " + "; ".join(check.limitations[:2])
        )
    result.patched = current
    return result
