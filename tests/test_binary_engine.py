"""Direct byte-level engine: no disassembly text is reassembled."""
from pathlib import Path

from app.services.binary_repair_engine import repair_elf, scan_elf
from app.services.x86_runtime import emulate_elf

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"


def _indirect_read_elf():
    import struct
    base = 0x400000
    entry = base + 0x1000
    code = bytearray()
    code += b"\x48\x83\xec\x10"       # sub rsp,16
    code += b"\xb8\x00\x01\x00\x00"   # mov eax,256
    code += b"\x89\xc2"                 # mov edx,eax
    code += b"\x31\xc0"                 # xor eax,eax (read)
    code += b"\x31\xff"
    code += b"\x48\x89\xe6"
    code += b"\x0f\x05"
    code += b"\xb8\x01\x00\x00\x00"   # write(1,rsp,16)
    code += b"\xbf\x01\x00\x00\x00"
    code += b"\x48\x89\xe6"
    code += b"\xba\x10\x00\x00\x00"
    code += b"\x0f\x05"
    code += b"\xb8\x3c\x00\x00\x00"
    code += b"\x31\xff"
    code += b"\x0f\x05"
    shstr = b"\x00.text\x00.shstrtab\x00"
    off = 0x1000
    shstr_off = off + len(code)
    shoff = (shstr_off + len(shstr) + 7) & ~7
    data = bytearray(shoff)
    eh = bytearray(64); eh[:4] = b"\x7fELF"; eh[4] = 2; eh[5] = 1; eh[6] = 1
    struct.pack_into("<HHIQQQIHHHHHH", eh, 16, 2, 62, 1, entry, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    ph = bytearray(56); struct.pack_into("<IIQQQQQQ", ph, 0, 1, 5, 0, base, base, 0x1000 + len(code), 0x1000 + len(code), 0x1000)
    sh = bytearray(3 * 64)
    struct.pack_into("<IIQQQQIIQQ", sh, 64, 1, 1, 6, entry, off, len(code), 0, 0, 16, 0)
    struct.pack_into("<IIQQQQIIQQ", sh, 128, 7, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)
    eh[0x28:0x30] = struct.pack("<Q", shoff); eh[0x3A:0x3C] = struct.pack("<H", 64)
    eh[0x3C:0x3E] = struct.pack("<H", 3); eh[0x3E:0x40] = struct.pack("<H", 2)
    data[:64] = eh; data[64:120] = ph
    data[off:off + len(code)] = code
    data[shstr_off:shstr_off + len(shstr)] = shstr
    data[shoff:shoff + 3 * 64] = sh
    return bytes(data)



def test_known_fixture_gets_reviewed_strict_repair():
    patched, report = repair_elf(VULN.read_bytes())
    assert patched is not None
    assert report.mode == "strict"
    assert report.strict is True
    assert report.capacity == 16


def test_generic_immediate_patch_does_not_reassemble_text():
    # Append a byte so the exact-template digest does not match; .text is intact.
    original = VULN.read_bytes() + b"X"
    patched, report = repair_elf(original)
    assert patched is not None
    assert report.mode == "bounds-only"
    assert report.supported is True
    assert report.capacity == 16
    assert len(report.findings) == 2
    assert sum(a != b for a, b in zip(original, patched)) == 4  # two imm32 patches (2 bytes each)
    # The engine patched only the two immediates; it did not rewrite/append .text.
    assert patched[:0x1000] == original[:0x1000]
    assert len(patched) == len(original)


def test_non_elf_and_unsupported_arch_fail_closed():
    patched, report = repair_elf(b"MZ" + b"\x00" * 100)
    assert patched is None
    assert report.supported is False


def test_generic_patch_runtime_still_has_no_overflow():
    patched, report = repair_elf(VULN.read_bytes() + b"X")
    assert patched is not None
    for size in (3, 16, 32):
        result = emulate_elf(patched, b"A" * size)
        assert result.exit_code == 0
        assert result.stack_tail == b"Z" * 16


def test_generic_capacity_is_not_hardcoded_to_16():
    data = bytearray(VULN.read_bytes())
    # sub rsp, 16 -> sub rsp, 32; this also invalidates the strict-template digest.
    assert data[0x1018:0x101C] == bytes.fromhex("4883ec10")
    data[0x101B] = 0x20
    patched, report = repair_elf(bytes(data))
    assert patched is not None
    assert report.mode == "bounds-only"
    assert report.capacity == 32
    assert all(item.after == 32 for item in report.findings)


def test_scan_reports_patchable_lengths_and_formats():
    scan = scan_elf(VULN.read_bytes())
    assert scan["format"] == "elf64-little"
    assert scan["arch"] == "x86_64"
    assert len(scan["findings"]) == 2
    assert all(item["patchable"] for item in scan["findings"])
    pe = scan_elf(b"MZ" + b"\x00" * 100)
    assert pe["format"] == "pe"
    assert pe["supported"] is False
    macho = scan_elf(b"\xcf\xfa\xed\xfe" + b"\x00" * 100)
    assert macho["format"] == "macho"


def test_indirect_register_length_is_propagated_and_patched():
    data = _indirect_read_elf()
    patched, report = repair_elf(data)
    assert patched is not None
    assert report.mode == "bounds-only"
    assert report.capacity == 16
    assert report.findings
    result = emulate_elf(patched, b"A" * 32)
    assert result.exit_code == 0
    assert result.stack_tail == b"Z" * 16
