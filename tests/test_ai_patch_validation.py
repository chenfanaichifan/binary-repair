"""AI path two: machine-code injection / in-place byte patch validation.

The validator must accept only structurally safe AI patches: fully decodable
allowlisted machine code whose branches stay inside the injected block, or
same-length in-place edits inside an executable section.  Everything else has
to fail closed with ``patched=None`` and a non-empty ``error``.
"""
from __future__ import annotations

import dataclasses
import functools
import io
import struct
from pathlib import Path

import pytest
from elftools.elf.elffile import ELFFile

import app.services.ai_patch_validation as ai_patch_validation
from app.services.ai_patch_validation import MAX_CODE_BYTES, apply_ai_patch
from app.services.containers import ContainerInfo, detect_container
from app.services.repair.analyzer import analyze
from app.services.repair.guards import abi_for, build_guard

ROOT = Path(__file__).resolve().parents[1]
PE_X64 = ROOT / "fixtures" / "pe" / "vuln-strcpy-x64.exe"
PE_X64_ARM64 = ROOT / "fixtures" / "pe" / "vuln-strcpy-arm64.exe"
ELF_MEMCPY = ROOT / "fixtures" / "elf" / "vuln-memcpy-x86.elf"
ELF_DYN = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86-dyn.elf"


@functools.lru_cache(maxsize=None)
def _case(path_str: str):
    """Load, analyze and cache one fixture (analysis is deterministic)."""
    path = Path(path_str)
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    analysis = analyze(data)
    return data, analysis.container, analysis.patchable()


def _pe_guard_setup():
    data, container, sinks = _case(str(PE_X64))
    assert (container.format, container.arch) == ("pe", "x86_64"), container.format
    assert len(sinks) == 1, [sink.kind for sink in sinks]
    sink = sinks[0]
    assert sink.kind == "unbounded_copy"
    assert (sink.callee, sink.capacity) == ("strcpy", 16)
    code = build_guard(abi_for("pe", "x86_64"), "strcpy", 16)
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": code.hex()},
    }
    return data, container, sinks, sink, code, payload


def test_pe_x64_guard_injection_redirects_and_reparses():
    data, container, sinks, sink, code, payload = _pe_guard_setup()
    result = apply_ai_patch(data, container, sinks, payload)

    assert result.ok, result.error
    assert result.error is None
    assert result.patched is not None and result.patched != data
    assert len(result.actions) == 1
    action = result.actions[0]
    assert action["kind"] == "ai-injected-guard"
    assert action["site"] == hex(sink.call_va)
    assert action["cave_va"] == hex(result.injected_va)
    assert action["method"] == "pe-section"
    assert action["code_bytes"] == len(code)
    assert result.method == "pe-section"

    check = detect_container(result.patched)
    assert (check.format, check.arch, check.bits) == ("pe", "x86_64", 64)
    assert check.limitations == []

    # The injected R-X section carries exactly the AI machine code.
    section = next(s for s in check.sections if s.name == ".brfix")
    assert section.executable
    assert section.va == result.injected_va
    assert result.patched[section.offset:section.offset + len(code)] == code

    # The original call site is now ``E8 rel32`` into the injected block.
    offset = sink.call_offset
    assert result.patched[offset] == 0xE8
    delta = struct.unpack_from("<i", result.patched, offset + 1)[0]
    assert sink.call_va + 5 + delta == result.injected_va


def test_elf32_dynamic_guard_injection_redirects_and_reparses():
    data, container, sinks = _case(str(ELF_DYN))
    assert (container.format, container.arch) == ("elf", "i386"), (
        container.format, container.arch)
    assert len(sinks) == 1, [sink.kind for sink in sinks]
    sink = sinks[0]
    assert sink.kind == "unbounded_copy"
    code = build_guard(abi_for("elf", "i386"), sink.callee, int(sink.capacity))
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": code.hex()},
    }

    result = apply_ai_patch(data, container, sinks, payload)
    assert result.ok, result.error
    assert result.patched is not None
    assert result.actions[0]["kind"] == "ai-injected-guard"
    assert result.actions[0]["method"] == "new-pt-load"

    check = detect_container(result.patched)
    assert (check.format, check.arch, check.bits) == ("elf", "i386", 32)
    assert check.limitations == []

    offset = sink.call_offset
    assert result.patched[offset] == 0xE8
    delta = struct.unpack_from("<i", result.patched, offset + 1)[0]
    assert sink.call_va + 5 + delta == result.injected_va

    elf = ELFFile(io.BytesIO(result.patched))
    loads = [
        segment for segment in elf.iter_segments()
        if segment["p_type"] == "PT_LOAD"
        and int(segment["p_vaddr"]) == result.injected_va
    ]
    assert loads, "injected block is not covered by a PT_LOAD"
    segment = loads[0]
    assert int(segment["p_flags"]) & 0x5 == 0x5  # R-X
    raw = result.patched[
        int(segment["p_offset"]):int(segment["p_offset"]) + int(segment["p_filesz"])
    ]
    assert raw[:len(code)] == code


def test_elf32_immediate_edit_clamps_length_and_reparses():
    data, container, sinks = _case(str(ELF_MEMCPY))
    assert (container.format, container.arch) == ("elf", "i386")
    assert len(sinks) == 1, [sink.kind for sink in sinks]
    sink = sinks[0]
    assert sink.kind == "memcpy_length"
    assert (sink.length, sink.capacity) == (64, 16)
    offset = sink.length_offset
    assert offset is not None and data[offset:offset + 4] == b"\x40\x00\x00\x00"
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "edits": [{
            "offset": offset,
            "before_hex": "40000000",
            "after_hex": "10000000",
        }],
    }

    result = apply_ai_patch(data, container, sinks, payload)
    assert result.ok, result.error
    assert result.patched is not None
    assert result.actions == [{
        "kind": "ai-edit",
        "offset": offset,
        "before_hex": "40000000",
        "after_hex": "10000000",
    }]
    assert result.patched[offset:offset + 4] == b"\x10\x00\x00\x00"
    assert result.patched[:offset] == data[:offset]
    assert result.patched[offset + 4:] == data[offset + 4:]

    check = detect_container(result.patched)
    assert (check.format, check.arch, check.bits) == ("elf", "i386", 32)
    assert check.limitations == []


def test_pe_x64_arm64_guard_injection_redirects_and_reparses():
    """Optional arm64 coverage: the same validator must accept the ABI guard."""
    data, container, sinks = _case(str(PE_X64_ARM64))
    assert (container.format, container.arch) == ("pe", "arm64")
    assert len(sinks) == 1, [sink.kind for sink in sinks]
    sink = sinks[0]
    code = build_guard(abi_for("pe", "arm64"), sink.callee, int(sink.capacity))
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": code.hex()},
    }
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.ok, result.error
    assert result.patched is not None
    assert result.actions[0]["kind"] == "ai-injected-guard"
    check = detect_container(result.patched)
    assert (check.format, check.arch, check.bits) == ("pe", "arm64", 64)
    assert check.limitations == []
    word = struct.unpack_from("<I", result.patched, sink.call_offset)[0]
    assert word & 0xFC000000 == 0x94000000  # BL
    delta = (word & 0x03FFFFFF) << 2
    if delta & (1 << 27):
        delta -= 1 << 28
    assert sink.call_va + delta == result.injected_va


# ---------------------------------------------------------------------------
# Fail-closed payload / sink validation
# ---------------------------------------------------------------------------

def test_rejects_wrong_schema_version():
    data, container, sinks, _, _, payload = _pe_guard_setup()
    bad = {**payload, "schema_version": 2}
    result = apply_ai_patch(data, container, sinks, bad)
    assert result.patched is None
    assert result.error and "schema_version" in result.error
    assert result.actions == []


def test_rejects_out_of_range_sink_index():
    data, container, sinks, _, _, payload = _pe_guard_setup()
    bad = {**payload, "sink_index": 5}
    result = apply_ai_patch(data, container, sinks, bad)
    assert result.patched is None
    assert result.error and "out of range" in result.error


def test_rejects_non_patchable_sink():
    data, container, sinks, sink, _, payload = _pe_guard_setup()
    bad_sinks = [dataclasses.replace(sink, patchable=False)]
    result = apply_ai_patch(data, container, bad_sinks, payload)
    assert result.patched is None
    assert result.error and "not patchable" in result.error


def test_rejects_guard_sink_with_edits():
    data, container, sinks, _, _, _ = _pe_guard_setup()
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": "c3"},
        "edits": [],
    }
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.patched is None
    assert result.error and "must not contain edits" in result.error


def test_rejects_immediate_sink_with_inject():
    data, container, sinks = _case(str(ELF_MEMCPY))
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": "c3"},
    }
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.patched is None
    assert result.error and "must not contain inject" in result.error


def test_rejects_guard_without_inject():
    data, container, sinks, _, _, _ = _pe_guard_setup()
    payload = {"schema_version": 1, "sink_index": 0}
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.patched is None
    assert result.error and "inject.code_hex" in result.error


# ---------------------------------------------------------------------------
# Fail-closed machine-code validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("code_hex", "needle"),
    [
        ("0f05", "syscall"),            # syscall
        ("cd80", "int"),                # int 0x80
        ("cc", "int"),                  # int3
        ("e800000000", "call"),         # direct call to a relative target
        ("ffe0", "indirect"),           # jmp rax
        ("eb7f", "outside"),            # short jmp outside the block
        ("e900000000", "outside"),      # near jmp to exactly the block end
        ("0f", "decode"),               # trailing byte never decodes
        ("f4", "hlt"),                  # privileged halt
        ("0f0b", "ud2"),                # undefined instruction
        ("fce8", "decode"),             # cld prefix then incomplete call
        ("90", "fall through"),         # whitelisted but no terminator
        ("31c0", "fall through"),       # xor eax,eax; falls out of the block
    ],
)
def test_rejected_guard_machine_code(code_hex, needle):
    data, container, sinks, _, _, _ = _pe_guard_setup()
    payload = {"schema_version": 1, "sink_index": 0,
               "inject": {"code_hex": code_hex}}
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.patched is None, f"{code_hex} unexpectedly accepted"
    assert result.error, f"{code_hex} rejected without an error"
    assert needle in result.error.lower(), result.error
    assert result.actions == []


def test_rejected_guard_code_over_limit():
    data, container, sinks, _, _, _ = _pe_guard_setup()
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "inject": {"code_hex": "90" * (MAX_CODE_BYTES + 1)},
    }
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.patched is None
    assert result.error and "limit" in result.error


def test_rejects_bad_call_site_shape():
    data, container, sinks, sink, _, payload = _pe_guard_setup()
    text = next(s for s in container.sections if s.name == ".text" and s.executable)
    bad = dataclasses.replace(
        sink, call_offset=text.offset, call_va=text.va, call_size=5
    )
    result = apply_ai_patch(data, container, [bad], payload)
    assert result.patched is None
    assert result.error and "direct call" in result.error


def test_rejects_injection_writeback_failure(monkeypatch):
    data, container, sinks, _, _, payload = _pe_guard_setup()

    def _fail(*_args, **_kwargs):
        return None, None, "PE writeback failed: simulated"

    monkeypatch.setattr(ai_patch_validation, "_inject_blob", _fail)
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.patched is None
    assert result.error and "code injection failed" in result.error
    assert "simulated" in result.error


def test_rejects_candidate_reparse_mismatch(monkeypatch):
    data, container, sinks, _, _, payload = _pe_guard_setup()

    def _wrong_container(_candidate):
        return ContainerInfo(format="elf", arch="arm64", bits=64)

    monkeypatch.setattr(ai_patch_validation, "detect_container", _wrong_container)
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.patched is None
    assert result.error and "reparse" in result.error


# ---------------------------------------------------------------------------
# Fail-closed in-place edit validation
# ---------------------------------------------------------------------------

def _edit_payload(offset: int, before_hex: str, after_hex: str) -> dict:
    return {
        "schema_version": 1,
        "sink_index": 0,
        "edits": [{
            "offset": offset,
            "before_hex": before_hex,
            "after_hex": after_hex,
        }],
    }


def test_rejects_edit_before_mismatch():
    data, container, sinks = _case(str(ELF_MEMCPY))
    offset = sinks[0].length_offset
    result = apply_ai_patch(
        data, container, sinks, _edit_payload(offset, "00000000", "10000000")
    )
    assert result.patched is None
    assert result.error and "does not match" in result.error


def test_rejects_edit_outside_executable_section():
    data, container, sinks = _case(str(ELF_MEMCPY))
    # The ELF header at offset 0 is not part of any executable section.
    result = apply_ai_patch(
        data, container, sinks, _edit_payload(0, data[:4].hex(), data[:4].hex())
    )
    assert result.patched is None
    assert result.error and "executable section" in result.error


def test_rejects_edit_length_change():
    data, container, sinks = _case(str(ELF_MEMCPY))
    offset = sinks[0].length_offset
    result = apply_ai_patch(
        data, container, sinks, _edit_payload(offset, "40000000", "10")
    )
    assert result.patched is None
    assert result.error and "changes length" in result.error


def test_rejects_edit_past_eof():
    data, container, sinks = _case(str(ELF_MEMCPY))
    last = data[-2:]
    result = apply_ai_patch(
        data, container, sinks,
        _edit_payload(len(data) - 1, last.hex(), last.hex()),
    )
    assert result.patched is None
    assert result.error and "past EOF" in result.error


def test_rejects_too_many_edits():
    data, container, sinks = _case(str(ELF_MEMCPY))
    offset = sinks[0].length_offset
    edit = {"offset": offset, "before_hex": "40", "after_hex": "10"}
    payload = {"schema_version": 1, "sink_index": 0, "edits": [edit] * 17}
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.patched is None
    assert result.error and "limit" in result.error


def test_rejects_edits_over_byte_budget():
    data, container, sinks = _case(str(ELF_MEMCPY))
    offset = sinks[0].length_offset
    edits = []
    for start in (offset, offset + 200):
        before = data[start:start + 200]
        after = before[:-1] + bytes([before[-1] ^ 0xFF])
        edits.append({
            "offset": start,
            "before_hex": before.hex(),
            "after_hex": after.hex(),
        })
    result = apply_ai_patch(
        data, container, sinks,
        {"schema_version": 1, "sink_index": 0, "edits": edits},
    )
    assert result.patched is None
    assert result.error and "limit" in result.error


def test_rejects_overlapping_edits():
    data, container, sinks = _case(str(ELF_MEMCPY))
    offset = sinks[0].length_offset
    payload = {
        "schema_version": 1,
        "sink_index": 0,
        "edits": [
            {"offset": offset, "before_hex": "4000", "after_hex": "1000"},
            {"offset": offset + 1, "before_hex": "0000", "after_hex": "0100"},
        ],
    }
    result = apply_ai_patch(data, container, sinks, payload)
    assert result.patched is None
    assert result.error and "overlap" in result.error


def test_rejects_noop_edits():
    data, container, sinks = _case(str(ELF_MEMCPY))
    offset = sinks[0].length_offset
    result = apply_ai_patch(
        data, container, sinks, _edit_payload(offset, "40000000", "40000000")
    )
    assert result.patched is None
    assert result.error and "modify" in result.error
