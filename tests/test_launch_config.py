"""Guard: every launcher must agree on one canonical data directory.

The external review (Improve.md item 6) found the Windows controller defaulting
to ``var\\controller`` while the worker defaulted to ``var``. Two people running
the documented commands therefore read different SQLite stores and see an empty
job list or a job that never progresses. These tests keep the launchers aligned.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR_VAR = "BINARYREPAIR_DATA_DIR"


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _env_names(text: str) -> set[str]:
    return set(re.findall(r"\$env:([A-Za-z_]+)", text))


def test_windows_launchers_share_the_var_default() -> None:
    controller = _read("start-controller.ps1")
    worker = _read("start-worker.ps1")

    assert 'Join-Path $project "var"' in controller
    assert 'Join-Path $root "var"' in worker
    assert DATA_DIR_VAR in _env_names(controller)
    assert DATA_DIR_VAR in _env_names(worker)


def test_controller_launcher_no_longer_forces_a_subdirectory() -> None:
    controller = _read("start-controller.ps1")
    assert "var\\controller" not in controller
    assert "var/controller" not in controller


def test_posix_worker_launcher_uses_the_same_default() -> None:
    worker = _read("start-worker.sh")
    assert "${BINARYREPAIR_DATA_DIR:-$ROOT/var}" in worker
