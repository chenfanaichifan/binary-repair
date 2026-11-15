"""Cross-process Lima guest coordinator tests (flock lease + attempt evidence)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import guest_coordinator, guest_runner, poc_runner
from app.services.guest_coordinator import (
    GuestLockTimeout,
    GuestLockUnavailable,
    acquire_lima_guest_lock,
    attempt_history,
    clear_attempt_history,
    lock_path,
)
from app.services.guest_runner import GuestRunner, find_guest_runner, run_path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"
MANIFEST = ROOT / "fixtures" / "poc" / "elf-x86_64-strcpy.json"
_RUNNER = find_guest_runner("x86_64")
LIMA = _RUNNER is not None and _RUNNER.kind == "lima"

_ATTEMPT_KEYS = {
    "run_id", "attempt", "operation", "purpose", "pid", "instance",
    "lock_path", "lock_wait_ms", "wait_ms", "lease_acquired", "acquired",
    "released", "timeout", "reentrant", "depth", "ttl_s", "limactl",
    "prior_lease_stale", "prior_lease_pid", "attempted_at_s",
}


@pytest.fixture(autouse=True)
def _isolated_lock(tmp_path: Path, monkeypatch):
    """A fresh lock path/state/history per test (never the real $HOME lock)."""

    monkeypatch.setattr(guest_coordinator, "_STATES", {})
    clear_attempt_history()
    monkeypatch.setenv(guest_coordinator.LOCK_ENV, str(tmp_path / "lima-guest.lock"))
    monkeypatch.setenv(guest_coordinator.TIMEOUT_ENV, "5")
    monkeypatch.delenv(guest_coordinator.TTL_ENV, raising=False)
    yield
    clear_attempt_history()


def _acquire(purpose: str = "test", **kwargs):  # noqa: ANN001, ANN003
    return acquire_lima_guest_lock(
        purpose=purpose, instance="binaryrepair",
        limactl="/opt/homebrew/bin/limactl", **kwargs,
    )


class _BackgroundHolder:
    """Hold the guest lock in a daemon thread (timeouts need a foreign thread)."""

    def __init__(self, purpose: str = "holder", **kwargs):  # noqa: ANN003
        self.purpose = purpose
        self.kwargs = kwargs
        self.ready = threading.Event()
        self._stop = threading.Event()
        self.lease = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        self.lease = _acquire(purpose=self.purpose, **self.kwargs)
        self.ready.set()
        self._stop.wait(60)
        self.lease.release()

    def __enter__(self) -> "_BackgroundHolder":
        self._thread.start()
        assert self.ready.wait(15), "background lock holder did not start"
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ANN201
        self._stop.set()
        self._thread.join(timeout=15)
        return False


def _try_foreign_acquire(timeout: float = 0.15) -> bool:
    """Try to acquire from another thread; return True when it timed out."""

    outcome: dict[str, bool] = {}

    def worker() -> None:
        try:
            lease = _acquire(purpose="foreign-thread", timeout=timeout)
            lease.release()
            outcome["acquired"] = True
        except GuestLockTimeout:
            outcome["timeout"] = True

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=5)
    return bool(outcome.get("timeout", False))


# ------------------------------------------------------------------ basic lease


def test_acquire_release_records_attempt_evidence(tmp_path: Path):
    lease = _acquire(purpose="unit-basic")
    assert lease.released is False
    assert lease.lock_file == tmp_path / "lima-guest.lock"
    assert lease.lock_file.is_file()
    lease_json = json.loads(lease.lock_file.read_text())
    assert lease_json["released"] is False
    assert lease_json["instance"] == "binaryrepair"
    assert lease_json["operation"] == "unit-basic"
    assert lease_json["pid"] == os.getpid()
    assert lease_json["run_id"] == lease.run_id
    assert isinstance(lease_json["acquired_at_s"], float)
    assert lease_json["ttl_s"] > 0

    attempts = lease.attempts
    assert len(attempts) == 1
    record = attempts[0]
    assert _ATTEMPT_KEYS <= set(record)
    assert record["purpose"] == "unit-basic"
    assert record["pid"] == os.getpid()
    assert record["instance"] == "binaryrepair"
    assert record["acquired"] is True and record["lease_acquired"] is True
    assert record["timeout"] is False
    assert record["released"] is False
    assert record["limactl"]["instance"] == "binaryrepair"
    assert record["limactl"]["tool"].endswith("limactl")

    lease.release()
    lease.release()  # idempotent
    assert lease.released is True
    assert lease.attempts[0]["released"] is True
    released_json = json.loads(lease.lock_file.read_text())
    assert released_json["released"] is True
    assert released_json["released_at_s"] is not None


def test_lock_path_env_override_and_default(tmp_path: Path, monkeypatch):
    assert lock_path("binaryrepair") == tmp_path / "lima-guest.lock"
    monkeypatch.delenv(guest_coordinator.LOCK_ENV)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert lock_path("binaryrepair") == (
        tmp_path / "home" / ".binaryrepair" / "locks" / "lima-binaryrepair.lock"
    )
    lease = _acquire(purpose="default-path")
    assert (tmp_path / "home" / ".binaryrepair" / "locks").is_dir()
    lease.release()


# --------------------------------------------------------------- reentrancy/threads


def test_nested_lock_is_reentrant_and_does_not_deadlock():
    with _acquire(purpose="outer") as outer:
        assert outer.reentrant is False and outer.depth == 1
        assert _try_foreign_acquire(0.15) is True  # another thread is blocked
        with _acquire(purpose="inner") as inner:
            assert inner.reentrant is True
            assert inner.depth == 2
            inner_record = inner.attempts[-1]
            assert inner_record["reentrant"] is True
            assert inner_record["purpose"] == "inner"
        # Inner release keeps the outer lease (flock still held).
        assert outer.released is False
        assert _try_foreign_acquire(0.15) is True
        assert [record["released"] for record in outer.attempts] == [False, True]
    assert outer.released is True
    assert [record["released"] for record in outer.attempts] == [True, True]
    # After the outermost release the lock is free again.
    lease = _acquire(purpose="after")
    lease.release()


def test_two_threads_serialize():
    state = {"active": 0, "peak": 0, "done": 0}
    guard = threading.Lock()
    start = threading.Barrier(3)

    def worker() -> None:
        start.wait(timeout=5)
        with _acquire(purpose="thread-worker"):
            with guard:
                state["active"] += 1
                state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.12)
            with guard:
                state["active"] -= 1
                state["done"] += 1

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    start.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=10)
    assert state["done"] == 2
    assert state["peak"] == 1  # never two holders at once
    acquired = [
        record for record in attempt_history()
        if record["purpose"] == "thread-worker" and record["acquired"]
    ]
    assert len(acquired) == 2
    assert any(record["lock_wait_ms"] > 0 for record in acquired)


def test_two_processes_serialize(tmp_path: Path):
    start_marker = tmp_path / "child-start"
    end_marker = tmp_path / "child-end"
    script = (
        "import os, time\n"
        "from pathlib import Path\n"
        "from app.services import guest_coordinator as gc\n"
        "lease = gc.acquire_lima_guest_lock(purpose='child-process', "
        "instance='binaryrepair', timeout=10)\n"
        "Path(os.environ['CHILD_START']).write_text(str(time.time()))\n"
        "time.sleep(float(os.environ.get('CHILD_HOLD', '0.4')))\n"
        "Path(os.environ['CHILD_END']).write_text(str(time.time()))\n"
        "lease.release()\n"
    )
    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(ROOT),
            "CHILD_START": str(start_marker),
            "CHILD_END": str(end_marker),
            "CHILD_HOLD": "0.4",
        }
    )
    child = subprocess.Popen(
        [sys.executable, "-c", script], cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while not start_marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert start_marker.exists(), child.stderr.read().decode(errors="replace")
        lock_json = json.loads(Path(env[guest_coordinator.LOCK_ENV]).read_text())
        assert lock_json["pid"] == child.pid
        assert lock_json["released"] is False

        started = time.monotonic()
        lease = _acquire(purpose="parent-process", timeout=10)
        acquired_at = time.time()
        child_end = float(end_marker.read_text())
        assert acquired_at >= child_end - 0.02
        wait_ms = (time.monotonic() - started) * 1000.0
        assert wait_ms > 100
        assert lease.attempts[0]["lock_wait_ms"] > 100
        lease.release()
    finally:
        child.wait(timeout=15)
    assert child.returncode == 0


# ---------------------------------------------------------------- timeout/errors


def test_timeout_raises_typed_blocked_error():
    with _BackgroundHolder():
        started = time.monotonic()
        with pytest.raises(GuestLockTimeout) as captured:
            _acquire(purpose="late", timeout=0.2)
        elapsed = time.monotonic() - started
    assert elapsed >= 0.15
    attempts = captured.value.attempts
    assert attempts, "timeout must carry attempt evidence"
    record = attempts[-1]
    assert record["timeout"] is True
    assert record["acquired"] is False
    assert record["purpose"] == "late"


def test_env_timeout_is_used(monkeypatch):
    monkeypatch.setenv(guest_coordinator.TIMEOUT_ENV, "0.15")
    with _BackgroundHolder():
        started = time.monotonic()
        with pytest.raises(GuestLockTimeout):
            _acquire(purpose="late-env")
        assert 0.12 <= time.monotonic() - started < 2.0


def test_missing_lock_parent_fails_closed(tmp_path: Path, monkeypatch):
    missing = tmp_path / "does" / "not" / "exist"
    monkeypatch.setenv(guest_coordinator.LOCK_ENV, str(missing / "lima.lock"))
    with pytest.raises(GuestLockUnavailable) as captured:
        _acquire(purpose="missing-parent")
    assert "does not exist" in str(captured.value)
    assert captured.value.attempts
    assert captured.value.attempts[0]["acquired"] is False
    assert captured.value.attempts[0]["timeout"] is False


def test_directory_lock_path_fails_closed(tmp_path: Path, monkeypatch):
    path = tmp_path / "lima.lock"
    path.mkdir()
    monkeypatch.setenv(guest_coordinator.LOCK_ENV, str(path))
    with pytest.raises(GuestLockUnavailable) as captured:
        _acquire(purpose="directory")
    assert "not a regular file" in str(captured.value)
    assert captured.value.attempts


def test_stale_lease_from_dead_pid_is_recorded(tmp_path: Path):
    lock_file = Path(os.environ[guest_coordinator.LOCK_ENV])
    lock_file.write_text(json.dumps({
        "schema_version": 1, "run_id": "old-run", "pid": 999_999,
        "instance": "binaryrepair", "operation": "crashed",
        "acquired_at_s": 0.0, "released": False,
    }))
    lease = _acquire(purpose="after-crash")
    record = lease.attempts[0]
    assert record["prior_lease_stale"] is True
    assert record["prior_lease_pid"] == 999_999
    lease.release()
    # Released leases are never reported as stale.
    lease2 = _acquire(purpose="after-release")
    assert lease2.attempts[0]["prior_lease_stale"] is False
    lease2.release()


def test_live_lease_with_old_ttl_is_stale(tmp_path: Path, monkeypatch):
    monkeypatch.setenv(guest_coordinator.TTL_ENV, "0.01")
    lock_file = Path(os.environ[guest_coordinator.LOCK_ENV])
    lock_file.write_text(json.dumps({
        "schema_version": 1, "run_id": "old-run", "pid": os.getpid(),
        "instance": "binaryrepair", "operation": "crashed",
        "acquired_at_s": time.time() - 60.0, "released": False,
    }))
    lease = _acquire(purpose="after-ttl", ttl=0.01)
    assert lease.attempts[0]["prior_lease_stale"] is True
    lease.release()


def test_attempt_history_is_bounded_and_clearable():
    lease = _acquire(purpose="history")
    lease.release()
    history = attempt_history()
    assert any(record["purpose"] == "history" for record in history)
    assert len(attempt_history(limit=1)) == 1
    clear_attempt_history()
    assert attempt_history() == []


# ------------------------------------------------------- guest_runner integration


def test_run_path_native_never_touches_the_guest_lock(tmp_path: Path):
    result = run_path(
        Path(sys.executable), ["-c", "print('ok')"],
        runner=GuestRunner(kind="native", tool="", tier="native_run"),
        cwd=tmp_path, timeout=60,
    )
    assert result.exit_code == 0
    assert result.lock_attempts == []
    assert result.lock_blocked is False
    assert not Path(os.environ[guest_coordinator.LOCK_ENV]).exists()


def test_run_path_lima_lock_timeout_is_blocked_not_executed(monkeypatch):
    staged = Path.home() / ".br-guest-lock-test-target"
    staged.write_bytes(b"x" * 16)
    executed: list[list[str]] = []

    def _must_not_execute(*args, **kwargs):  # noqa: ANN001
        executed.append(list(args[0]) if args else [])
        raise AssertionError("run_path must not execute on a lock timeout")

    monkeypatch.setattr(guest_runner, "_guest_visible", lambda path: True)
    monkeypatch.setattr(guest_runner.subprocess, "run", _must_not_execute)
    runner = GuestRunner(
        kind="lima", tool="/fake/limactl", tier="emulated_run", instance="binaryrepair",
    )
    try:
        with _BackgroundHolder():
            result = run_path(staged, [], runner=runner, lock_timeout=0.2)
    finally:
        staged.unlink(missing_ok=True)
    assert executed == []
    assert result.lock_blocked is True
    assert result.exit_code is None
    assert "guest lock timeout/blocked" in (result.error or "")
    assert result.lock_attempts
    assert any(record["timeout"] for record in result.lock_attempts)


def test_run_path_lima_lock_unavailable_is_blocked_not_executed(
    tmp_path: Path, monkeypatch,
):
    staged = Path.home() / ".br-guest-lock-test-target"
    staged.write_bytes(b"x" * 16)
    monkeypatch.setattr(guest_runner, "_guest_visible", lambda path: True)
    missing = tmp_path / "missing" / "dir" / "lima.lock"
    monkeypatch.setenv(guest_coordinator.LOCK_ENV, str(missing))
    executed: list[object] = []

    def _must_not_execute(*args, **kwargs):  # noqa: ANN001
        executed.append(args)
        raise AssertionError("run_path must not execute when the lock is unusable")

    monkeypatch.setattr(guest_runner.subprocess, "run", _must_not_execute)
    runner = GuestRunner(
        kind="lima", tool="/fake/limactl", tier="emulated_run", instance="binaryrepair",
    )
    try:
        result = run_path(staged, [], runner=runner)
    finally:
        staged.unlink(missing_ok=True)
    assert executed == []
    assert result.lock_blocked is True
    assert "guest lock unavailable/blocked" in (result.error or "")


def test_run_path_lima_holds_the_lock_during_execution(monkeypatch):
    staged = Path.home() / ".br-guest-lock-test-target"
    staged.write_bytes(b"x" * 16)
    observations: dict[str, object] = {}
    monkeypatch.setattr(guest_runner, "_guest_visible", lambda path: True)
    monkeypatch.setattr(
        guest_runner, "wait_for_lima_guest_view",
        lambda *args, **kwargs: None,
    )

    def fake_run(command, **kwargs):  # noqa: ANN001
        # While the guest command runs the flock must be held: a second writer
        # on the same lock file cannot take it.
        import fcntl

        fd = os.open(os.environ[guest_coordinator.LOCK_ENV], os.O_RDWR)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                observations["held_during_execution"] = False
                fcntl.flock(fd, fcntl.LOCK_UN)
            except BlockingIOError:
                observations["held_during_execution"] = True
        finally:
            os.close(fd)
        return SimpleNamespace(returncode=0, stdout=b"ok\n", stderr=b"")

    monkeypatch.setattr(guest_runner.subprocess, "run", fake_run)
    runner = GuestRunner(
        kind="lima", tool="/fake/limactl", tier="emulated_run", instance="binaryrepair",
    )
    try:
        result = run_path(
            staged, ["hi"], runner=runner, lock_purpose="execute-case",
        )
    finally:
        staged.unlink(missing_ok=True)
    assert result.error is None and result.exit_code == 0
    assert observations["held_during_execution"] is True
    assert result.lock_attempts
    lease_records = [
        record for record in result.lock_attempts
        if record["purpose"] == "execute-case"
    ]
    assert len(lease_records) == 1
    assert lease_records[0]["released"] is True


# ------------------------------------------------------- real Lima serialization


@pytest.mark.skipif(not LIMA, reason="running Lima guest runner is required")
def test_real_lima_poc_runs_are_serialized_with_attempt_evidence():
    original = FIXTURE.read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    results: list[object] = []
    barrier = threading.Barrier(2)

    def worker() -> None:
        barrier.wait(timeout=10)
        results.append(
            poc_runner.run_poc(
                original, original, manifest, timeout=90, lock_timeout=180,
            )
        )

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=180)
    assert len(results) == 2, "both concurrent PoC runs must finish (no deadlock)"
    assert {evidence.status for evidence in results} == {"fail"}
    for evidence in results:
        assert evidence.lock_blocked is False
        assert evidence.lock_attempts
        purposes = {record["purpose"] for record in evidence.lock_attempts}
        assert "poc_runner.run_poc" in purposes
        assert any(
            record["purpose"].startswith("poc_runner.run_path:")
            for record in evidence.lock_attempts
        )
        assert all(record["released"] for record in evidence.lock_attempts)

    # The two outer leases must not overlap: the serialized intervals are
    # ordered by acquire/release wall-clock evidence.
    outer = [
        record
        for evidence in results
        for record in evidence.lock_attempts
        if record["purpose"] == "poc_runner.run_poc" and not record["reentrant"]
    ]
    assert len(outer) == 2
    intervals = sorted(
        (record["attempted_at_s"], record["released_at_s"]) for record in outer
    )
    assert intervals[0][1] <= intervals[1][0]
    assert any(record["lock_wait_ms"] > 0 for record in outer)


def test_run_path_lima_holds_the_lock_during_guest_view_wait(monkeypatch):
    staged = Path.home() / ".br-guest-lock-test-target"
    staged.write_bytes(b"x" * 16)
    observations: dict[str, object] = {}
    monkeypatch.setattr(guest_runner, "_guest_visible", lambda path: True)

    def fake_wait(tool, instance, path, **kwargs):  # noqa: ANN001
        observations["lock_held_during_view_wait"] = _try_foreign_acquire(0.1)
        return None

    monkeypatch.setattr(guest_runner, "wait_for_lima_guest_view", fake_wait)
    monkeypatch.setattr(
        guest_runner.subprocess, "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=b"", stderr=b""),
    )
    runner = GuestRunner(
        kind="lima", tool="/fake/limactl", tier="emulated_run", instance="binaryrepair",
    )
    try:
        result = run_path(staged, [], runner=runner, lock_purpose="view-wait")
    finally:
        staged.unlink(missing_ok=True)
    assert result.error is None
    assert observations["lock_held_during_view_wait"] is True
