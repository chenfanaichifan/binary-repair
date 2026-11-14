"""LD_PRELOAD errno probe compilation/parsing (no target execution)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.poc_runner import (
    _compile_errno_dumper,
    _is_dynamic_elf,
    _read_errno_dump,
    parse_strace_errors,
)

ROOT = Path(__file__).resolve().parents[1]
CWE121 = ROOT / "fixtures" / "public" / "CWE121_src_char_declare_cpy_51b" / "original.elf"


def test_errno_dump_parser():
    assert _read_errno_dump(Path("/nonexistent")) is None


def test_cwe121_is_dynamic_elf():
    if not CWE121.is_file():
        pytest.skip("fixture missing")
    assert _is_dynamic_elf(CWE121.read_bytes()) is True


def test_dumper_compiles(tmp_path):
    dumper = _compile_errno_dumper(tmp_path / "errno_dumper.so")
    if dumper is None:
        pytest.skip("no host C compiler")
    assert dumper.is_file() and dumper.stat().st_size > 0
    (tmp_path / "errno.txt").write_text("BR_ERRNO=22\n")
    assert _read_errno_dump(tmp_path / "errno.txt") == 22


def test_strace_parser_still_available():
    assert parse_strace_errors("x = -1 ENOENT") == ["ENOENT"]
