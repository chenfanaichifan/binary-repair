"""Direct byte-level engine: no disassembly text is reassembled."""
from pathlib import Path

from app.services.binary_repair_engine import repair_elf
from app.services.x86_runtime import emulate_elf

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"


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
