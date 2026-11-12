"""Emulated runtime proof for the strict fixed ELF.

Unicorn executes the ELF's own x86-64 instructions; read/write/exit are
emulated syscalls.  This is not host execution and not a sandbox.
"""
from pathlib import Path

from app.services.x86_runtime import emulate_elf

ROOT = Path(__file__).resolve().parents[1]
STRICT = ROOT / "artifacts" / "vuln-elf" / "vuln-strict-fixed.elf"
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PROMPT = b"input> "
ERROR = b"input too long (max 16 bytes)\n"


def run(path, data):
    return emulate_elf(path.read_bytes(), data)


def test_strict_accepts_zero_short_and_boundary_inputs_without_leak():
    for data in (b"", b"abc", b"A" * 16):
        result = run(STRICT, data)
        assert result.exit_code == 0, (data, result.error)
        assert result.stdout == PROMPT + data
        assert result.stderr == b""
        assert result.stack_tail == b"Z" * 16


def test_strict_rejects_over_limit_without_touching_stack():
    for data in (b"A" * 17, b"A" * 32, b"A" * 256):
        result = run(STRICT, data)
        assert result.exit_code == 1, (data, result.error)
        assert result.stdout == PROMPT
        assert result.stderr == ERROR
        assert result.stack_tail == b"Z" * 16


def test_original_binary_really_overwrites_stack_sentinel():
    result = run(VULN, b"A" * 32)
    assert result.exit_code == 0
    assert result.stack_tail != b"Z" * 16
