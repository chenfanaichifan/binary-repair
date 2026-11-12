"""Isolated Linux guest runner via qemu-user (or explicit unavailability).

No host execution is used as a substitute.  If qemu-user is absent the result is
`available=False`; callers must report `not_verified`, never `patched`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GuestResult:
    available: bool
    stdout: bytes = b""
    stderr: bytes = b""
    exit_code: int | None = None
    timed_out: bool = False
    error: str | None = None
    tool: str | None = None


def find_qemu(arch: str) -> str | None:
    names = {"x86_64": ("qemu-x86_64",), "arm64": ("qemu-aarch64",)}.get(arch, ())
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    # UTM ships QEMU inside the app; search only well-known paths.
    roots = [Path("/Applications/UTM.app/Contents"), Path.home() / "Applications/UTM.app/Contents"]
    for root in roots:
        for name in names:
            for candidate in root.rglob(name):
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return str(candidate)
    return None


def run_elf(path: Path | str, *, arch: str = "x86_64", stdin: bytes = b"",
            timeout: float = 10.0) -> GuestResult:
    tool = find_qemu(arch)
    if tool is None:
        return GuestResult(False, error="qemu-user not available")
    try:
        with tempfile.TemporaryDirectory(prefix="guest-run-") as tmp:
            proc = subprocess.run(
                [tool, str(path)], input=stdin, capture_output=True,
                timeout=timeout, cwd=tmp, env={
                    "PATH": "/usr/bin:/bin",
                    "HOME": tmp,
                    "TMPDIR": tmp,
                }, check=False,
            )
        return GuestResult(True, proc.stdout, proc.stderr, proc.returncode,
                           tool=Path(tool).name)
    except subprocess.TimeoutExpired as exc:
        return GuestResult(True, exc.stdout or b"", exc.stderr or b"",
                           timed_out=True, tool=Path(tool).name)
    except Exception as exc:  # noqa: BLE001
        return GuestResult(True, error=f"{type(exc).__name__}: {exc}",
                           tool=Path(tool).name)
