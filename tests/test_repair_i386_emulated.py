"""Unicorn runtime evidence for 32-bit x86 (i386) candidates.

The i386 path uses ``UC_ARCH_X86`` + ``UC_MODE_32``: ELF32/PE32 images are mapped
from their ``PT_LOAD``/section metadata, the source pointer is passed as the
cdecl stack argument at ``[esp+4]``, a 4-byte synthetic return address is
checked for corruption, and imports are intercepted at their thunk/PLT address.

Coverage split:

* synthetic ELF32 images exercise mapping, register setup, the cdecl stack frame
  and the overflow canary without depending on generated fixtures;
* the engine's ELF32/PE32 fixtures run the patched-vs-original acceptance set
  (0/1/15/16/17/64).
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from app.services.containers import ContainerInfo, SectionInfo, detect_container
from app.services.repair.analyzer import analyze
from app.services.repair.writer import repair_with_sinks
from app.services.runtime import emulated as emulated_module
from app.services.runtime.emulated import (
    _elf_mappings, _i386_hook_targets, _short_name, emulate,
)

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "elf-x86": ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf",
    "pe-x86": ROOT / "fixtures" / "pe" / "vuln-strcpy-x86.exe",
}
ABI = "cdecl_x86"
PROBE = [0, 1, 15, 16, 17, 64]
CAPACITY = 15  # safe output ceiling for a 16-byte destination

# ---------------------------------------------------------------------------
# Synthetic ELF32 images (no dependency on the fixture build script).
# ---------------------------------------------------------------------------
TEXT_VA = 0x08048000
_STRCPY_OFFSET = 0x40
_CODE_OFFSET = 0x100


def _synthetic_elf32(code: bytes, *, text_va: int = TEXT_VA) -> bytes:
    """Build a minimal ET_EXEC ELF32/EM_386 image with .text/.symtab/.strtab."""
    strcpy_va = text_va + _STRCPY_OFFSET
    image = bytearray(max(_STRCPY_OFFSET + 4, len(code)))
    image[:len(code)] = code
    image[_STRCPY_OFFSET] = 0xC3  # ret: hooked before it can execute

    strtab = b"\x00vuln_copy\x00strcpy\x00"
    symtab = b"".join([
        struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0),
        struct.pack("<IIIBBH", 1, text_va, len(code), 0x12, 0, 1),
        struct.pack("<IIIBBH", 11, strcpy_va, 1, 0x12, 0, 1),
    ])
    shstrtab = b"\x00.text\x00.symtab\x00.strtab\x00.shstrtab\x00"
    symtab_off = _CODE_OFFSET + len(image)
    strtab_off = symtab_off + len(symtab)
    shstrtab_off = strtab_off + len(strtab)
    shoff = (shstrtab_off + len(shstrtab) + 3) & ~3

    ehdr = struct.pack(
        "<16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x01\x01" + b"\x00" * 9,
        2, 3, 1, text_va, 52, shoff, 0, 52, 32, 1, 40, 5, 4,
    )
    phdr = struct.pack(
        "<IIIIIIII", 1, _CODE_OFFSET, text_va, text_va,
        len(image), len(image), 5, 0x1000,
    )

    def section(name, kind, flags, addr, offset, size, link=0, info=0,
                align=1, entsize=0):
        return struct.pack("<IIIIIIIIII", name, kind, flags, addr, offset,
                           size, link, info, align, entsize)

    shdrs = b"".join([
        section(0, 0, 0, 0, 0, 0),
        section(1, 1, 6, text_va, _CODE_OFFSET, len(image), align=4),
        section(7, 2, 0, 0, symtab_off, len(symtab), link=3, info=1,
                align=4, entsize=16),
        section(15, 3, 0, 0, strtab_off, len(strtab)),
        section(23, 3, 0, 0, shstrtab_off, len(shstrtab)),
    ])
    out = bytearray(ehdr + phdr)
    out += b"\x00" * (_CODE_OFFSET - len(out))
    out += image + symtab + strtab + shstrtab
    out += b"\x00" * (shoff - len(out))
    out += shdrs
    return bytes(out)


def _synthetic_vulnerable_code(text_va: int = TEXT_VA) -> bytes:
    """push ebp; mov ebp,esp; sub esp,0x20; strcpy(ebp-0x10, [ebp+8])."""
    strcpy_va = text_va + _STRCPY_OFFSET
    code = bytearray(b"\x55\x89\xE5\x83\xEC\x20")  # push ebp / mov ebp,esp / sub
    code += b"\x8B\x45\x08"                        # mov eax,[ebp+8]  (src)
    code += b"\x8D\x55\xF0"                        # lea edx,[ebp-0x10] (dst)
    code += b"\x50\x52"                            # push eax; push edx
    call_at = len(code)
    code += b"\xE8" + struct.pack("<i", strcpy_va - (text_va + call_at + 5))
    code += b"\x83\xC4\x08\xC9\xC3"                # add esp,8; leave; ret
    return bytes(code)


def _synthetic_bounded_code() -> bytes:
    """Same frame, but only NUL-terminates the destination (safe stand-in)."""
    return bytes.fromhex("5589e583ec208b4508c60000c9c3")


def test_synthetic_elf32_mapping_and_metadata():
    data = _synthetic_elf32(_synthetic_vulnerable_code())
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) == ("elf", "i386", 32)
    assert container.symbols == {
        TEXT_VA: "vuln_copy",
        TEXT_VA + _STRCPY_OFFSET: "strcpy",
    }
    (mapping,) = _elf_mappings(data)
    assert mapping.va == TEXT_VA
    assert mapping.offset == _CODE_OFFSET
    assert mapping.size >= len(_synthetic_vulnerable_code())


def test_synthetic_elf32_detects_unbounded_overflow():
    data = _synthetic_elf32(_synthetic_vulnerable_code())
    container = detect_container(data)
    patched = emulate(data, container, function_va=TEXT_VA, dest_rel=-0x14,
                     capacity=16, abi=ABI)
    assert patched.tier == "emulated_run"
    assert patched.engine == "unicorn-i386"
    assert patched.verdict == "fail"
    by_len = {case.input_len: case for case in patched.cases}
    assert [case.input_len for case in patched.cases] == PROBE
    for length in (0, 1, 15):
        assert by_len[length].canary_intact is True
        assert by_len[length].output_len == length
    for length in (16, 17, 64):
        assert by_len[length].canary_intact is False


def test_synthetic_elf32_bounded_function_passes():
    data = _synthetic_elf32(_synthetic_bounded_code())
    container = detect_container(data)
    evidence = emulate(data, container, function_va=TEXT_VA, dest_rel=-0x14,
                       capacity=16, abi=ABI)
    assert evidence.verdict == "pass", evidence.to_dict()
    assert all(case.canary_intact is True for case in evidence.cases)
    assert all(case.output_len == 0 for case in evidence.cases)


def test_short_name_normalisation():
    assert _short_name("c.string.strcpy") == "strcpy"
    assert _short_name("_strcpy") == "strcpy"
    assert _short_name("strcpy@GLIBC_2.0") == "strcpy"
    assert _short_name("c.string.stpcpy") == "stpcpy"


def test_i386_pe_import_thunks_are_resolved():
    path = CASES["pe-x86"]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    copy_targets, puts_targets, _copy_calls, _puts_calls = _i386_hook_targets(
        data, container,
    )
    assert copy_targets, "PE32 strcpy thunk was not resolved"
    assert puts_targets, "PE32 puts thunk was not resolved"

    text = next(section for section in container.sections if section.name == ".text")
    raw = data[text.offset:text.offset + text.size]
    for target in copy_targets + puts_targets:
        section = container.section_at(target)
        assert section is not None and section.executable
        offset = target - text.va
        # MinGW thunk: ff 25 <abs32> == jmp dword ptr [IAT]
        assert raw[offset] == 0xFF and raw[offset + 1] == 0x25


def test_i386_direct_iat_call_site_is_hooked(monkeypatch):
    """``call dword ptr [IAT]`` (ff 15) sites are modeled at the call itself."""
    # push ebp; mov ebp,esp; sub esp,0x20; mov eax,[ebp+8]; lea edx,[ebp-0x10];
    # push eax; push edx; call dword ptr [0x403000]; add esp,8; leave; ret
    code = bytes.fromhex(
        "5589e583ec208b45088d55f05052"
        "ff1500304000"
        "83c408c9c3"
    )
    data = code + b"\x00" * 16
    container = ContainerInfo(
        format="pe", arch="i386", bits=32, image_base=0x400000,
        sections=[SectionInfo(name=".text", segment="", va=0x401000,
                              size=len(data), offset=0, executable=True)],
        imports={0x403000: "strcpy"},
    )
    _thunks, calls = emulated_module._i386_import_edges(data, container)
    assert calls == {0x40100E: ("strcpy", 6)}

    monkeypatch.setattr(
        emulated_module, "_pe_mappings",
        lambda _data: [emulated_module._Mapping(0x401000, 0x1000, 0)],
    )
    evidence = emulate(data, container, function_va=0x401000, dest_rel=-0x14,
                       capacity=16, abi=ABI, lengths=[0, 1, 15, 16, 17, 64])
    assert evidence.verdict == "fail"
    by_len = {case.input_len: case for case in evidence.cases}
    for length in (0, 1, 15):
        assert by_len[length].canary_intact is True
    for length in (16, 17, 64):
        assert by_len[length].canary_intact is False


def test_i386_guard_abi_contract():
    from app.services.repair.guards import abi_for

    assert abi_for("elf", "i386") == ABI
    assert abi_for("pe", "i386") == ABI


@pytest.mark.parametrize("name", sorted(CASES))
def test_emulated_run_accepts_patched_and_rejects_original(name):
    path = CASES[name]
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    data = path.read_bytes()
    container = detect_container(data)
    assert (container.format, container.arch, container.bits) in {
        ("elf", "i386", 32), ("pe", "i386", 32),
    }

    analysis = analyze(data)
    sinks = analysis.patchable()
    assert sinks, analysis.limitations
    sink = sinks[0]
    assert sink.arch == "i386"
    assert sink.capacity == 16
    assert sink.dest_rel is not None and sink.dest_rel < 0
    assert sink.function_va

    written = repair_with_sinks(data, container, [sink])
    assert written.ok, written.limitations
    patched = written.patched
    assert patched is not None and patched != data
    patched_container = detect_container(patched)
    assert (patched_container.format, patched_container.arch) == (
        container.format, "i386",
    )

    good = emulate(
        patched, patched_container,
        function_va=sink.function_va, dest_rel=sink.dest_rel,
        capacity=sink.capacity, abi=ABI, lengths=PROBE,
    )
    assert good.tier == "emulated_run"
    assert good.engine == "unicorn-i386"
    assert good.verdict == "pass", good.to_dict()
    assert [case.input_len for case in good.cases] == PROBE
    assert all(case.canary_intact is True for case in good.cases), good.to_dict()
    for case in good.cases:
        assert case.output_len is not None
        assert case.output_len <= min(case.input_len, CAPACITY)

    # The original function overflows at and above its capacity.
    baseline = emulate(
        data, container,
        function_va=sink.function_va, dest_rel=sink.dest_rel,
        capacity=sink.capacity, abi=ABI, lengths=[16, 17, 64],
    )
    assert baseline.verdict == "fail", baseline.to_dict()
    assert all(case.canary_intact is False for case in baseline.cases)

    # Short inputs are clean even on the vulnerable build.
    small = emulate(
        data, container,
        function_va=sink.function_va, dest_rel=sink.dest_rel,
        capacity=sink.capacity, abi=ABI, lengths=[0, 1, 15],
    )
    assert small.verdict == "pass", small.to_dict()
    assert all(case.canary_intact is True for case in small.cases)
