"""Native Linux x86-64 execution of the generated fixtures.

This is a real Linux run, but it is not a sandboxed guest.  The CI job is the
supported environment; other platforms skip.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts/vuln-elf/vuln.elf"
STRICT = ROOT / "artifacts/vuln-elf/vuln-strict-fixed.elf"


def _run(path: Path, data: bytes) -> subprocess.CompletedProcess[bytes]:
    os.chmod(path, 0o755)
    return subprocess.run([str(path)], input=data, capture_output=True, timeout=5)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux x86-64 execution")
def test_vulnerable_fixture_native_linux():
    short = _run(VULN, b"hi")
    assert short.returncode == 0
    assert short.stdout.startswith(b"input> ")
    assert b"hi" in short.stdout
    # The deliberately vulnerable fixture does not reject long input; it
    # overflows and still exits 0.  The strict-fixed fixture is the one that
    # returns 1.  This test proves native Linux execution, not rejection.
    long = _run(VULN, b"A" * 32)
    assert long.returncode == 0


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux x86-64 execution")
def test_strict_fixture_native_linux_blocks_long_input():
    short = _run(STRICT, b"hi")
    assert short.returncode == 0
    long = _run(STRICT, b"A" * 32)
    assert long.returncode == 1
    assert b"input too long" in long.stderr
