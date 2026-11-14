"""Guest runtime selection and crash classification (native/qemu/Lima)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import guest_runner
from app.services.guest_runner import (
    GuestRunner,
    crash_detected,
    find_guest_runner,
    find_lima_runner,
    find_qemu,
    run_elf,
    run_path,
)

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts/vuln-elf/vuln.elf"
STRCPY = ROOT / "fixtures/elf/vuln-strcpy-x86_64.elf"
_RUNNER = find_guest_runner("x86_64")
LIMA = _RUNNER is not None and _RUNNER.kind == "lima"
NATIVE = GuestRunner(kind="native", tool="", tier="native_run")


def test_guest_runner_is_explicit_when_qemu_missing():
    result = run_elf(VULN, arch="x86_64", stdin=b"abc")
    if find_qemu("x86_64") is None:
        assert result.available is False
        assert "qemu" in (result.error or "").lower()


def test_find_guest_runner_shape():
    runner = find_guest_runner("x86_64")
    if runner is None:
        return
    assert runner.kind in {"native", "qemu", "lima"}
    if runner.kind == "native":
        assert runner.tier == "native_run"
        assert runner.tool == ""
    else:
        assert runner.tier == "emulated_run"
        assert runner.tool and Path(runner.tool).is_file()
    if runner.kind == "lima":
        assert runner.instance
    assert find_guest_runner("amd64").kind == runner.kind


def _patch_platform(monkeypatch, *, platform_name: str, machine: str) -> None:
    monkeypatch.setattr(guest_runner.sys, "platform", platform_name)
    monkeypatch.setattr(guest_runner.platform, "machine", lambda: machine)


def test_find_guest_runner_prefers_native_on_matching_linux_host(monkeypatch):
    _patch_platform(monkeypatch, platform_name="linux", machine="x86_64")
    monkeypatch.setattr(guest_runner.shutil, "which", lambda name: None)
    assert find_guest_runner("x86_64") == GuestRunner(
        kind="native", tool="", tier="native_run",
    )
    assert find_guest_runner("amd64") == GuestRunner(
        kind="native", tool="", tier="native_run",
    )
    # a foreign architecture is never reported as native
    assert find_guest_runner("arm64") is None


def test_find_guest_runner_uses_qemu_when_installed(monkeypatch):
    _patch_platform(monkeypatch, platform_name="linux", machine="aarch64")
    monkeypatch.setattr(
        guest_runner.shutil, "which",
        lambda name: "/usr/bin/qemu-x86_64" if name == "qemu-x86_64" else None,
    )

    def _must_not_query_lima(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("limactl must not be queried when qemu-user is available")

    monkeypatch.setattr(guest_runner.subprocess, "run", _must_not_query_lima)
    runner = find_guest_runner("x86_64")
    assert runner == GuestRunner(
        kind="qemu", tool="/usr/bin/qemu-x86_64", tier="emulated_run",
    )


def test_find_guest_runner_uses_lima_when_no_native_or_qemu(monkeypatch):
    _patch_platform(monkeypatch, platform_name="darwin", machine="arm64")
    monkeypatch.setenv("BINARYREPAIR_LIMA_INSTANCE", "binaryrepair")
    monkeypatch.setattr(
        guest_runner.shutil, "which",
        lambda name: "/opt/homebrew/bin/limactl" if name == "limactl" else None,
    )
    monkeypatch.setattr(
        guest_runner.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(  # noqa: ANN001
            returncode=0,
            stdout=b'{"name":"binaryrepair","status":"Running"}\n',
            stderr=b"",
        ),
    )
    assert find_guest_runner("x86_64") == GuestRunner(
        kind="lima", tool="/opt/homebrew/bin/limactl", tier="emulated_run",
        instance="binaryrepair",
    )


def test_find_guest_runner_none_when_nothing_is_available(monkeypatch):
    _patch_platform(monkeypatch, platform_name="darwin", machine="arm64")
    monkeypatch.setattr(guest_runner.shutil, "which", lambda name: None)
    assert find_guest_runner("x86_64") is None


@pytest.mark.parametrize(
    ("exit_code", "stderr", "expected"),
    [
        (-11, b"", True),  # killed by SIGSEGV
        (-9, b"", True),  # killed by SIGKILL
        (132, b"", True),  # 128 + SIGILL
        (137, b"", True),  # 128 + SIGKILL
        (139, b"", True),  # 128 + SIGSEGV
        (255, b"qemu: uncaught target signal 11 (Segmentation fault) - core dumped", True),
        (0, b"", False),
        (1, b"", False),
        (0, b"Segmentation fault (core dumped)", True),
        (1, "qemu: uncaught target signal 11", True),
        (255, b"", False),
        (0, b"rendered ok", False),
    ],
)
def test_crash_detection_matrix(exit_code, stderr, expected):
    assert crash_detected(exit_code, stderr) is expected


def test_run_path_unavailable_without_runner(monkeypatch):
    monkeypatch.setattr(guest_runner, "find_guest_runner", lambda arch: None)
    result = run_path("/nonexistent/binary", [], arch="x86_64")
    assert result.available is False
    assert result.exit_code is None
    assert result.crashed is False
    assert result.runner == "" and result.tier == ""
    assert "runner" in (result.error or "").lower()


def test_run_path_native_execution_scrubs_env(tmp_path: Path):
    code = (
        "import os, sys; "
        "sys.stdout.write(os.environ.get('LC_ALL','') + '|' + os.environ.get('HOME',''))"
    )
    result = run_path(
        Path(sys.executable), ["-c", code], runner=NATIVE, cwd=tmp_path, timeout=60,
    )
    assert result.available is True
    assert result.error is None and result.timed_out is False
    assert result.exit_code == 0
    assert result.stdout.decode() == f"C|{tmp_path}"
    assert result.runner == "native" and result.tier == "native_run"


def test_run_path_native_detects_signal_crash(tmp_path: Path):
    result = run_path(
        Path(sys.executable),
        ["-c", "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"],
        runner=NATIVE,
        cwd=tmp_path,
        timeout=60,
    )
    assert result.available is True and result.error is None
    assert result.crashed is True
    assert result.exit_code is not None and result.exit_code < 0


def test_run_path_native_reports_timeout(tmp_path: Path):
    result = run_path(
        Path(sys.executable),
        ["-c", "import time; time.sleep(30)"],
        runner=NATIVE,
        cwd=tmp_path,
        timeout=0.5,
    )
    assert result.available is True
    assert result.timed_out is True
    assert result.error == "timeout"
    assert result.crashed is False
    assert result.exit_code is None


def test_run_path_lima_requires_home_visible_paths():
    runner = GuestRunner(kind="lima", tool="/fake/limactl", tier="emulated_run", instance="vm")
    result = run_path("/tmp/br-outside-home", [], runner=runner)
    assert result.available is True
    assert result.exit_code is None
    assert "home directory" in (result.error or "")


def _fake_limactl(monkeypatch, outputs):
    """Install a fake limactl executable + command responder."""

    monkeypatch.setattr(
        guest_runner.shutil, "which",
        lambda name: "/fake/limactl" if name == "limactl" else None,
    )
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):  # noqa: ANN001, ANN003
        calls.append(list(command))
        return outputs(command)

    monkeypatch.setattr(guest_runner.subprocess, "run", fake_run)
    return calls


def test_find_lima_runner_parses_json_status(monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_LIMA_INSTANCE", "test-vm")
    calls = _fake_limactl(
        monkeypatch,
        lambda command: SimpleNamespace(
            returncode=0,
            stdout=b'{"name":"other","status":"Running"}\n'
                   b'{"name":"test-vm","status":"Running"}\n',
            stderr=b"",
        ),
    )
    runner = find_lima_runner()
    assert runner is not None
    assert (runner.kind, runner.tier, runner.instance) == ("lima", "emulated_run", "test-vm")
    assert calls and calls[0] == ["/fake/limactl", "list", "--json"]


def test_find_lima_runner_none_when_stopped_or_missing(monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_LIMA_INSTANCE", "test-vm")
    _fake_limactl(
        monkeypatch,
        lambda command: SimpleNamespace(
            returncode=0,
            stdout=b'{"name":"test-vm","status":"Stopped"}\n',
            stderr=b"",
        ),
    )
    assert find_lima_runner() is None

    _fake_limactl(
        monkeypatch,
        lambda command: SimpleNamespace(
            returncode=0,
            stdout=b'{"name":"different-vm","status":"Running"}\n',
            stderr=b"",
        ),
    )
    assert find_lima_runner() is None


def test_find_lima_runner_falls_back_to_plain_list(monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_LIMA_INSTANCE", "test-vm")

    def responder(command):
        if command[1:] == ["list", "--json"]:
            return SimpleNamespace(returncode=1, stdout=b"", stderr=b"unknown flag")
        return SimpleNamespace(
            returncode=0,
            stdout=(
                b"NAME            STATUS     SSH              VMTYPE    ARCH\n"
                b"other           Running    127.0.0.1:1000   vz        aarch64\n"
                b"test-vm         Running    127.0.0.1:1001   vz        aarch64\n"
            ),
            stderr=b"",
        )

    _fake_limactl(monkeypatch, responder)
    runner = find_lima_runner()
    assert runner is not None and runner.kind == "lima"
    assert runner.instance == "test-vm"


def test_find_lima_runner_unavailable_without_limactl(monkeypatch):
    monkeypatch.setattr(guest_runner.shutil, "which", lambda name: None)
    assert find_lima_runner() is None


@pytest.mark.skipif(not LIMA, reason="running Lima guest runner is required")
def test_lima_run_path_executes_static_x86_64_elf():
    result = run_path(STRCPY, ["hi"], arch="x86_64", timeout=60)
    assert result.available is True
    assert result.timed_out is False and result.error is None
    assert result.exit_code == 0
    assert result.stdout == b"hi\n"
    assert result.runner == Path(_RUNNER.tool).name
    assert result.tier == "emulated_run"


@pytest.mark.skipif(not LIMA, reason="running Lima guest runner is required")
def test_lima_run_path_detects_guest_signal_crash():
    result = run_path(STRCPY, ["A" * 100], arch="x86_64", timeout=60)
    assert result.available is True
    assert result.crashed is True
    assert b"Segmentation fault" in result.stderr or b"target signal" in result.stderr


# ---------------------------------------------------------------------------
# Lima guest-view freshness (virtiofs stale size must never fabricate a crash)
# ---------------------------------------------------------------------------

def _stat_command_size(command: list[str]) -> bool:
    return "stat" in command and "-c" in command and "%s" in command


def test_wait_for_lima_guest_view_retries_until_fresh(monkeypatch, tmp_path: Path):
    staged = tmp_path / "target"
    staged.write_bytes(b"x" * 64)
    sizes = iter([32, 32, 64])
    calls = {"n": 0}

    def fake_size(tool, instance, path):  # noqa: ANN001
        calls["n"] += 1
        return next(sizes)

    monkeypatch.setattr(guest_runner, "_lima_guest_size", fake_size)
    monkeypatch.setattr(guest_runner.time, "sleep", lambda _s: None)
    error = guest_runner.wait_for_lima_guest_view(
        "/fake/limactl", "vm", staged, attempts=6, interval=0.0,
    )
    assert error is None
    assert calls["n"] == 3


def test_wait_for_lima_guest_view_fails_closed_when_never_fresh(
    monkeypatch, tmp_path: Path,
):
    staged = tmp_path / "target"
    staged.write_bytes(b"x" * 64)
    monkeypatch.setattr(
        guest_runner, "_lima_guest_size", lambda tool, instance, path: 32,
    )
    monkeypatch.setattr(guest_runner.time, "sleep", lambda _s: None)
    error = guest_runner.wait_for_lima_guest_view(
        "/fake/limactl", "vm", staged, attempts=3, interval=0.0,
    )
    assert error is not None
    assert "stale guest view" in error
    assert "host size=64" in error and "guest size=32" in error


def test_run_path_lima_stale_view_is_reported_not_executed(monkeypatch):
    staged = Path.home() / ".br-guest-view-test-target"
    staged.write_bytes(b"x" * 64)
    try:
        monkeypatch.setattr(guest_runner, "_guest_visible", lambda path: True)
        monkeypatch.setattr(guest_runner, "LIMA_VIEW_POLL_ATTEMPTS", 3)
        monkeypatch.setattr(guest_runner, "LIMA_VIEW_POLL_INTERVAL", 0.0)
        monkeypatch.setattr(guest_runner.time, "sleep", lambda _s: None)
        executed: list[list[str]] = []

        def responder(command):
            if _stat_command_size(command):
                return SimpleNamespace(returncode=0, stdout=b"32\n", stderr=b"")
            executed.append(list(command))
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

        _fake_limactl(monkeypatch, responder)
        runner = GuestRunner(
            kind="lima", tool="/fake/limactl", tier="emulated_run", instance="vm",
        )
        result = run_path(staged, [], runner=runner)
        assert result.available is True
        assert result.exit_code is None
        assert "stale guest view" in (result.error or "")
        assert executed == []
    finally:
        staged.unlink(missing_ok=True)


def test_run_path_lima_waits_for_fresh_view_then_executes(monkeypatch):
    staged = Path.home() / ".br-guest-view-test-target"
    staged.write_bytes(b"x" * 64)
    try:
        monkeypatch.setattr(guest_runner, "_guest_visible", lambda path: True)
        monkeypatch.setattr(guest_runner, "LIMA_VIEW_POLL_ATTEMPTS", 5)
        monkeypatch.setattr(guest_runner, "LIMA_VIEW_POLL_INTERVAL", 0.0)
        monkeypatch.setattr(guest_runner.time, "sleep", lambda _s: None)
        stat_sizes = iter([32, 64])
        executed: list[list[str]] = []

        def responder(command):
            if _stat_command_size(command):
                return SimpleNamespace(
                    returncode=0, stdout=f"{next(stat_sizes)}\n".encode(), stderr=b"",
                )
            executed.append(list(command))
            return SimpleNamespace(returncode=0, stdout=b"ok\n", stderr=b"")

        _fake_limactl(monkeypatch, responder)
        runner = GuestRunner(
            kind="lima", tool="/fake/limactl", tier="emulated_run", instance="vm",
        )
        result = run_path(staged, ["hi"], runner=runner)
        assert result.available is True
        assert result.error is None
        assert result.exit_code == 0
        assert result.stdout == b"ok\n"
        assert len(executed) == 1
        assert executed[0][-2:] == [str(staged), "hi"]
    finally:
        staged.unlink(missing_ok=True)
