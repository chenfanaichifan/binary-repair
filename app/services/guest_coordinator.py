"""Cross-process Lima guest serialization (flock lease + attempt evidence).

The Lima VM is a single shared guest.  Benchmark runners, the release gate,
the verifier oracle and the PoC runner can otherwise interleave ``limactl``
invocations, overwrite another run's staged files, or observe a stale
virtiofs/sshfs view while a sibling process is still writing the workspace.
This module is the single advisory lock for that guest.

Design (Phase-8C C09/C11 plan, ``artifacts/phase8c-baseline-2026-11-16/
phase8c-lima-coordination-plan.md``):

- lock file: ``$BINARYREPAIR_GUEST_LOCK`` when set, otherwise
  ``$HOME/.binaryrepair/locks/lima-<instance>.lock``;
- mechanism: ``fcntl.flock(LOCK_EX)`` on the lock file, with a JSON lease
  written while held (run id, pid, instance, operation, attempt, ttl) so an
  abandoned lease can be recognised as stale;
- reentrancy: an in-process ``threading.RLock`` (serialises threads) plus a
  depth counter.  Nested acquisitions on the same thread reuse the outer lease
  instead of deadlocking on the process' own flock;
- bounded wait: ``BINARYREPAIR_GUEST_LOCK_TIMEOUT`` (seconds, default 300) or
  an explicit ``timeout=``; an expired wait raises a typed
  :class:`GuestLockTimeout` and never continues unsynchronised;
- fail closed: a missing/unusable lock path (missing parent for an env
  override, directory/special file, open/write failure) raises
  :class:`GuestLockUnavailable`; nothing is executed;
- attempt evidence: every acquisition attempt is recorded with ``purpose``,
  ``pid``, ``instance``, ``wait_ms``, ``acquired``/``released``, ``timeout``
  and the ``limactl`` identity.  Records are exposed through
  :attr:`GuestLease.attempts` (front-ends attach them to their evidence) and a
  bounded process history is available via :func:`attempt_history`.

Only the Lima tier is serialised.  Native and qemu-user execution never touch
this module or its lock file.
"""
from __future__ import annotations

import fcntl
import json
import os
import shutil
import stat
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_INSTANCE",
    "DEFAULT_LOCK_TIMEOUT",
    "DEFAULT_LOCK_TTL",
    "GuestLease",
    "GuestLockError",
    "GuestLockTimeout",
    "GuestLockUnavailable",
    "LOCK_ENV",
    "TIMEOUT_ENV",
    "TTL_ENV",
    "acquire_lima_guest_lock",
    "attempt_history",
    "clear_attempt_history",
    "lima_guest_lock",
    "lock_path",
    "lock_timeout",
    "lock_ttl",
]

LOCK_ENV = "BINARYREPAIR_GUEST_LOCK"
TIMEOUT_ENV = "BINARYREPAIR_GUEST_LOCK_TIMEOUT"
TTL_ENV = "BINARYREPAIR_GUEST_LOCK_TTL"
INSTANCE_ENV = "BINARYREPAIR_LIMA_INSTANCE"
DEFAULT_INSTANCE = "binaryrepair"
DEFAULT_LOCK_TIMEOUT = 300.0
DEFAULT_LOCK_TTL = 900.0
LOCK_DIR = Path(".binaryrepair") / "locks"
HISTORY_LIMIT = 1000
_POLL_MIN = 0.01
_POLL_MAX = 0.05


class GuestLockError(RuntimeError):
    """Base class: the guest lock could not be used (nothing was executed)."""

    def __init__(self, message: str, attempts: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.attempts: list[dict[str, Any]] = list(attempts or [])


class GuestLockTimeout(GuestLockError):
    """The bounded wait for the guest lock expired (blocked, not executed)."""


class GuestLockUnavailable(GuestLockError):
    """The guest lock path/mechanism is unusable on this host (fail closed)."""


@dataclass
class _LockState:
    path: Path
    rlock: threading.RLock = field(default_factory=threading.RLock)
    depth: int = 0
    fd: int | None = None
    records: list[dict[str, Any]] = field(default_factory=list)
    attempt_seq: int = 0


_STATES: dict[str, _LockState] = {}
_STATES_GUARD = threading.Lock()
_HISTORY: deque[dict[str, Any]] = deque(maxlen=HISTORY_LIMIT)
_HISTORY_GUARD = threading.Lock()


def _state_for(path: Path) -> _LockState:
    key = str(path)
    with _STATES_GUARD:
        state = _STATES.get(key)
        if state is None:
            state = _LockState(path=path)
            _STATES[key] = state
        return state


def _history_append(record: dict[str, Any]) -> None:
    with _HISTORY_GUARD:
        _HISTORY.append(record)


def attempt_history(limit: int | None = None) -> list[dict[str, Any]]:
    """Bounded process-local history of guest-lock attempts (newest last)."""

    with _HISTORY_GUARD:
        records = list(_HISTORY)
    if limit is not None and limit >= 0:
        return records[-int(limit):]
    return records


def clear_attempt_history() -> None:
    """Drop the process-local attempt history (tests/diagnostics only)."""

    with _HISTORY_GUARD:
        _HISTORY.clear()


def _default_instance() -> str:
    return (os.environ.get(INSTANCE_ENV) or DEFAULT_INSTANCE).strip() or DEFAULT_INSTANCE


def lock_path(instance: str | None = None) -> Path:
    """Advisory lock path: env override, else ``$HOME/.binaryrepair/locks/...``."""

    override = (os.environ.get(LOCK_ENV) or "").strip()
    if override:
        return Path(override).expanduser()
    name = (str(instance or "").strip() or _default_instance())
    return Path.home() / LOCK_DIR / f"lima-{name}.lock"


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def lock_timeout(override: float | None = None) -> float:
    """Acquire timeout in seconds: explicit override, env, or default."""

    if override is not None:
        try:
            return max(0.0, float(override))
        except (TypeError, ValueError):
            return DEFAULT_LOCK_TIMEOUT
    return max(0.0, _env_float(TIMEOUT_ENV, DEFAULT_LOCK_TIMEOUT))


def lock_ttl(override: float | None = None) -> float:
    """Lease TTL in seconds for stale-lease detection."""

    if override is not None:
        try:
            return max(0.0, float(override))
        except (TypeError, ValueError):
            return DEFAULT_LOCK_TTL
    return max(0.0, _env_float(TTL_ENV, DEFAULT_LOCK_TTL))


def _limactl_identity(limactl: str | None, instance: str) -> dict[str, str]:
    """Identity of the guest runtime the attempt is competing for."""

    tool = str(limactl or "").strip() or (shutil.which("limactl") or "")
    return {"tool": tool, "instance": instance, "basename": Path(tool).name if tool else ""}


def _attempt_record(
    *,
    run_id: str,
    purpose: str,
    instance: str,
    limactl: str | None,
    attempt: int,
    wait_ms: float,
    acquired: bool,
    released: bool,
    timeout: bool,
    depth: int,
    reentrant: bool,
    ttl_s: float,
    lock: Path,
    prior_lease_stale: bool = False,
    prior_lease_pid: int | None = None,
) -> dict[str, Any]:
    now = time.time()
    record: dict[str, Any] = {
        "run_id": run_id,
        "attempt": attempt,
        "operation": purpose,
        "purpose": purpose,
        "pid": os.getpid(),
        "instance": instance,
        "lock_path": str(lock),
        "lock_wait_ms": round(float(wait_ms), 3),
        "wait_ms": round(float(wait_ms), 3),
        "lease_acquired": bool(acquired),
        "acquired": bool(acquired),
        "released": bool(released),
        "timeout": bool(timeout),
        "reentrant": bool(reentrant),
        "depth": int(depth),
        "ttl_s": float(ttl_s),
        "limactl": _limactl_identity(limactl, instance),
        "prior_lease_stale": bool(prior_lease_stale),
        "prior_lease_pid": prior_lease_pid,
        "attempted_at_s": now,
    }
    return record


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _read_lease(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _lease_is_stale(payload: dict[str, Any] | None, ttl_s: float) -> tuple[bool, int | None]:
    """Whether a leftover lease is abandoned (crash/TTL), never an active one."""

    if not isinstance(payload, dict) or payload.get("released") is True:
        return False, None
    pid = payload.get("pid")
    if not isinstance(pid, int) or isinstance(pid, bool):
        return True, None
    if not _pid_alive(pid):
        return True, pid
    acquired_at = payload.get("acquired_at_s")
    if isinstance(acquired_at, (int, float)) and not isinstance(acquired_at, bool):
        if ttl_s > 0 and (time.time() - float(acquired_at)) > ttl_s:
            return True, pid
    return False, pid


def _prepare_lock_path(path: Path) -> None:
    """Validate/create the lock path; raise :class:`GuestLockUnavailable`."""

    override = bool((os.environ.get(LOCK_ENV) or "").strip())
    parent = path.parent
    if override:
        # An explicit operator-provided lock path must already be usable: a
        # missing parent is a configuration error and fails closed.
        if not parent.is_dir():
            raise GuestLockUnavailable(
                f"guest lock path parent does not exist for {LOCK_ENV} "
                f"override: {parent} (refusing to create it)"
            )
    else:
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise GuestLockUnavailable(
                f"cannot create guest lock directory {parent}: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
    try:
        info = path.stat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise GuestLockUnavailable(
            f"cannot stat guest lock path {path}: {type(exc).__name__}: {exc}"
        ) from exc
    if not stat.S_ISREG(info.st_mode):
        raise GuestLockUnavailable(
            f"guest lock path is not a regular file: {path} "
            f"(mode={stat.filemode(info.st_mode)})"
        )


def _write_fd_json(fd: int, payload: dict[str, Any]) -> None:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    os.write(fd, data)


def _lease_payload(
    *,
    run_id: str,
    purpose: str,
    instance: str,
    attempt: int,
    ttl_s: float,
    limactl: str | None,
    released: bool = False,
) -> dict[str, Any]:
    now = time.time()
    payload: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "pid": os.getpid(),
        "instance": instance,
        "operation": purpose,
        "attempt": attempt,
        "acquired_at_s": now,
        "released_at_s": now if released else None,
        "ttl_s": float(ttl_s),
        "limactl": _limactl_identity(limactl, instance),
        "released": bool(released),
    }
    return payload


def _acquire_flock(path: Path, *, deadline: float) -> int:
    """Acquire the cross-process flock before *deadline*; typed errors."""

    try:
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        raise GuestLockUnavailable(
            f"cannot open guest lock file {path}: {type(exc).__name__}: {exc}"
        ) from exc
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except BlockingIOError:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise GuestLockTimeout(
                        f"timed out waiting for the cross-process Lima guest "
                        f"lock {path}"
                    )
                time.sleep(min(_POLL_MAX, max(_POLL_MIN, remaining)))
            except OSError as exc:
                raise GuestLockUnavailable(
                    f"flock failed on guest lock file {path}: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


class GuestLease:
    """An acquired Lima guest lease; use as a context manager or call release()."""

    def __init__(
        self,
        *,
        state: _LockState,
        records: list[dict[str, Any]],
        start_index: int,
        record: dict[str, Any],
        run_id: str,
        depth: int,
        reentrant: bool,
        ttl_s: float,
    ):
        self._state = state
        self._records = records
        self._start_index = start_index
        self._record = record
        self._run_id = run_id
        self._depth = depth
        self._reentrant = reentrant
        self._ttl_s = ttl_s
        self._released = False

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def reentrant(self) -> bool:
        return self._reentrant

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def lock_file(self) -> Path:
        return self._state.path

    @property
    def released(self) -> bool:
        return self._released

    @property
    def attempts(self) -> list[dict[str, Any]]:
        """Attempt evidence recorded during this lease (nested leases included)."""

        return list(self._records[self._start_index:])

    def release(self) -> None:
        """Release the lease (idempotent); flushes final attempt evidence."""

        if self._released:
            return
        state = self._state
        record = self._record
        record["released"] = True
        record["released_at_s"] = time.time()
        state.depth = max(0, state.depth - 1)
        record["release_depth"] = state.depth
        if state.depth == 0:
            fd = state.fd
            if fd is not None:
                try:
                    _write_fd_json(
                        fd,
                        _lease_payload(
                            run_id=self._run_id,
                            purpose=str(record.get("operation") or "lima_guest"),
                            instance=str(record.get("instance") or ""),
                            attempt=int(record.get("attempt") or 0),
                            ttl_s=self._ttl_s,
                            limactl=(record.get("limactl") or {}).get("tool"),
                            released=True,
                        ),
                    )
                except OSError:
                    pass  # evidence is retained in memory; never mask the release
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                try:
                    os.close(fd)
                except OSError:
                    pass
                state.fd = None
            state.records = []
        state.rlock.release()
        self._released = True

    def __enter__(self) -> "GuestLease":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001, ANN201
        self.release()
        return False


def acquire_lima_guest_lock(
    *,
    purpose: str = "lima_guest",
    instance: str | None = None,
    limactl: str | None = None,
    timeout: float | None = None,
    run_id: str | None = None,
    ttl: float | None = None,
) -> GuestLease:
    """Acquire the exclusive Lima guest lease.

    Nested calls on the same thread reuse the outer lease (reentrant, no
    deadlock).  Raises :class:`GuestLockTimeout` when the bounded wait expires
    and :class:`GuestLockUnavailable` when the lock path/mechanism is unusable;
    both carry the attempt evidence and mean *nothing was executed*.
    """

    name = (str(instance or "").strip() or _default_instance())
    purpose_text = str(purpose or "lima_guest").strip() or "lima_guest"
    tool = str(limactl or "").strip() or (shutil.which("limactl") or "")
    timeout_s = lock_timeout(timeout)
    ttl_s = lock_ttl(ttl)
    path = lock_path(name)
    state = _state_for(path)
    run_id_text = str(run_id or uuid.uuid4().hex)
    started = time.monotonic()
    deadline = started + timeout_s

    acquired_rlock = state.rlock.acquire(timeout=timeout_s)
    if not acquired_rlock:
        wait_ms = (time.monotonic() - started) * 1000.0
        record = _attempt_record(
            run_id=run_id_text, purpose=purpose_text, instance=name,
            limactl=tool, attempt=0, wait_ms=wait_ms, acquired=False,
            released=False, timeout=True, depth=0, reentrant=False,
            ttl_s=ttl_s, lock=path,
        )
        _history_append(record)
        raise GuestLockTimeout(
            f"timed out after {timeout_s:.3f}s waiting for the in-process Lima "
            f"guest lock on thread (lock={path})",
            attempts=[record],
        )
    success = False
    try:
        if state.depth > 0:
            # Reentrant: same thread already owns the lease.
            state.depth += 1
            state.attempt_seq += 1
            record = _attempt_record(
                run_id=run_id_text, purpose=purpose_text, instance=name,
                limactl=tool, attempt=state.attempt_seq,
                wait_ms=(time.monotonic() - started) * 1000.0,
                acquired=True, released=False, timeout=False,
                depth=state.depth, reentrant=True, ttl_s=ttl_s, lock=path,
            )
            state.records.append(record)
            _history_append(record)
            success = True
            return GuestLease(
                state=state, records=state.records,
                start_index=len(state.records) - 1, record=record,
                run_id=run_id_text, depth=state.depth, reentrant=True,
                ttl_s=ttl_s,
            )
        _prepare_lock_path(path)
        fd = _acquire_flock(path, deadline=deadline)
        # Read the lease only once the flock is ours: any other holder either
        # released it (not stale) or crashed (dead pid / expired TTL = stale).
        prior = _read_lease(path)
        prior_stale, prior_pid = _lease_is_stale(prior, ttl_s)
        state.fd = fd
        state.depth = 1
        state.records = []
        state.attempt_seq = 1
        record = _attempt_record(
            run_id=run_id_text, purpose=purpose_text, instance=name,
            limactl=tool, attempt=1,
            wait_ms=(time.monotonic() - started) * 1000.0,
            acquired=True, released=False, timeout=False, depth=1,
            reentrant=False, ttl_s=ttl_s, lock=path,
            prior_lease_stale=prior_stale, prior_lease_pid=prior_pid,
        )
        state.records.append(record)
        _history_append(record)
        try:
            _write_fd_json(
                fd,
                _lease_payload(
                    run_id=run_id_text, purpose=purpose_text, instance=name,
                    attempt=1, ttl_s=ttl_s, limactl=tool,
                ),
            )
        except OSError:
            pass  # the flock is authoritative; the lease file is evidence only
        success = True
        return GuestLease(
            state=state, records=state.records, start_index=0, record=record,
            run_id=run_id_text, depth=1, reentrant=False, ttl_s=ttl_s,
        )
    except GuestLockError as exc:
        wait_ms = (time.monotonic() - started) * 1000.0
        record = _attempt_record(
            run_id=run_id_text, purpose=purpose_text, instance=name,
            limactl=tool, attempt=0, wait_ms=wait_ms, acquired=False,
            released=False, timeout=isinstance(exc, GuestLockTimeout),
            depth=state.depth, reentrant=False, ttl_s=ttl_s, lock=path,
        )
        _history_append(record)
        if not exc.attempts:
            exc.attempts = [record]
        raise
    finally:
        if not success:
            # Any failure path: release the flock/fd if one was taken and drop
            # exactly the RLock recursion level acquired above.
            state.depth = 0
            if state.fd is not None:
                try:
                    fcntl.flock(state.fd, fcntl.LOCK_UN)
                except OSError:
                    pass
                try:
                    os.close(state.fd)
                except OSError:
                    pass
                state.fd = None
            state.records = []
            state.rlock.release()


def lima_guest_lock(
    *,
    purpose: str = "lima_guest",
    instance: str | None = None,
    limactl: str | None = None,
    timeout: float | None = None,
    run_id: str | None = None,
    ttl: float | None = None,
) -> GuestLease:
    """Context-manager entry point: ``with lima_guest_lock(...) as lease: ...``."""

    return acquire_lima_guest_lock(
        purpose=purpose,
        instance=instance,
        limactl=limactl,
        timeout=timeout,
        run_id=run_id,
        ttl=ttl,
    )
