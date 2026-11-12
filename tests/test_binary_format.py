"""Header-only format/arch detection used by the dataset adapters."""
import struct

from app.services.binary_datasets import detect_binary_format


def _write(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _elf(bits: int, machine: int, endian: str = "<") -> bytes:
    ident = b"\x7fELF" + bytes([2 if bits == 64 else 1, 1 if endian == "<" else 2, 1]) + b"\x00" * 9
    return ident + struct.pack(endian + "H", 2) + struct.pack(endian + "H", machine) + b"\x00" * 44


def _macho(bits: int, cputype: int) -> bytes:
    magic = b"\xcf\xfa\xed\xfe" if bits == 64 else b"\xce\xfa\xed\xfe"
    return magic + struct.pack("<I", cputype) + b"\x00" * 24


def test_detects_elf_x86_64_as_repair_supported(tmp_path):
    fmt = detect_binary_format(_write(tmp_path, "a.out", _elf(64, 62)))
    assert (fmt.format, fmt.arch, fmt.bits) == ("elf", "x86_64", 64)
    assert fmt.repair_supported is True


def test_detects_elf_i386_as_unsupported(tmp_path):
    fmt = detect_binary_format(_write(tmp_path, "a.out", _elf(32, 3)))
    assert (fmt.format, fmt.arch, fmt.bits) == ("elf", "i386", 32)
    assert fmt.repair_supported is False


def test_detects_macho_arm64_as_unsupported(tmp_path):
    fmt = detect_binary_format(_write(tmp_path, "a.out", _macho(64, 0x0100000C)))
    assert (fmt.format, fmt.arch, fmt.bits) == ("macho", "arm64", 64)
    assert fmt.repair_supported is False


def test_detects_pe(tmp_path):
    fmt = detect_binary_format(_write(tmp_path, "a.exe", b"MZ" + b"\x00" * 62))
    assert fmt.format == "pe"
    assert fmt.arch is None
    assert fmt.repair_supported is False


def test_unknown_and_empty_are_not_guessed(tmp_path):
    assert detect_binary_format(_write(tmp_path, "x", b"hello")).format == "unknown"
    assert detect_binary_format(tmp_path / "missing").format == "unknown"
