"""Isolated Linux/ELF guest runtime selection and execution.

Supported execution tiers, in preference order:

``native``
    The host is Linux and its architecture matches the requested one, so the
    target runs directly.
``qemu``
    A qemu-user binary for the requested architecture is installed on the host.
``lima``
    A running Lima VM (``limactl``) is available.  The guest is a Linux VM and
    the host home directory is mounted at the same absolute path (read-only),
    which is why callers must stage files under ``$HOME`` for this tier.

No host execution is used as a substitute.  If no runner is available the
result is ``available=False``; callers must report ``unavailable``/
``not_verified``, never a fabricated success.

Crash classification (``GuestResult.crashed``) accepts negative return codes,
shell-style ``128 + signal`` codes 132..139, and ``target signal`` /
``Segmentation fault`` in stderr.  Through the Lima tier a guest process killed
by a signal surfaces as exit code 255; for x86-64 targets the guest's
qemu-user-powered binfmt wrapper prints the ``target signal`` marker, which is
what classifies those runs as crashes.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

LIMA_INSTANCE_ENV = "BINARYREPAIR_LIMA_INSTANCE"
DEFAULT_LIMA_INSTANCE = "binaryrepair"
LIMA_LIST_TIMEOUT = 15.0
#: Lima shares the host home directory read-only through virtiofs/sshfs.  A
#: freshly written file can be served with a stale size to the guest for a
#: short window; a target that maps a segment at a file offset beyond that stale
#: size dies with an internal qemu SIGBUS.  The runner therefore polls the
#: guest-visible size (bounded) before executing and fails closed instead of
#: running a stale binary.
LIMA_VIEW_POLL_ATTEMPTS = 12
LIMA_VIEW_POLL_INTERVAL = 0.1
LIMA_STAT_TIMEOUT = 10.0

#: Exit codes conventionally produced by shells when a child died from a
#: signal (128 + signum); 139 is the usual SIGSEGV value.
CRASH_EXIT_CODES = frozenset({132, 133, 134, 135, 136, 137, 138, 139})
_CRASH_MARKERS = ("target signal", "segmentation fault")

_ARCH_ALIASES = {
    "x86_64": "x86_64",
    "x86-64": "x86_64",
    "amd64": "x86_64",
    "x64": "x86_64",
    "arm64": "arm64",
    "aarch64": "arm64",
}


@dataclass(frozen=True)
class GuestRunner:
    """A selected way to execute a foreign-architecture Linux binary."""

    kind: str  #: "native" | "qemu" | "lima"
    tool: str  #: executable used to launch the target ("" for native)
    tier: str  #: "native_run" | "emulated_run"
    instance: str = ""  #: Lima instance name (lima only)


@dataclass
class GuestResult:
    available: bool
    stdout: bytes = b""
    stderr: bytes = b""
    exit_code: int | None = None
    timed_out: bool = False
    error: str | None = None
    tool: str | None = None
    crashed: bool = False
    runner: str = ""
    tier: str = ""


def _normalize_arch(arch: str) -> str:
    value = str(arch or "").strip().lower()
    return _ARCH_ALIASES.get(value, value)


def _host_arch() -> str:
    return _normalize_arch(platform.machine())


def find_qemu(arch: str) -> str | None:
    """Return a qemu-user executable for *arch*, or ``None``."""

    names = {"x86_64": ("qemu-x86_64",), "arm64": ("qemu-aarch64",)}.get(
        _normalize_arch(arch), ()
    )
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


def _native_runner(arch: str) -> GuestRunner | None:
    if not sys.platform.startswith("linux"):
        return None
    supported = {
        "x86_64": {"x86_64", "amd64"},
        "arm64": {"aarch64", "arm64"},
    }.get(arch)
    if supported and _host_arch() in supported:
        return GuestRunner(kind="native", tool="", tier="native_run")
    return None


def lima_instance_name() -> str:
    """Lima instance selected by ``BINARYREPAIR_LIMA_INSTANCE``."""

    return (os.environ.get(LIMA_INSTANCE_ENV) or DEFAULT_LIMA_INSTANCE).strip()


def _lima_json_status(limactl: str, instance: str, timeout: float) -> bool | None:
    """Query instance status through ``limactl list --json``.

    Returns ``None`` when the JSON listing is unsupported/unusable so callers
    can fall back to the plain-text listing.
    """

    try:
        proc = subprocess.run(
            [limactl, "list", "--json"],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    usable = False
    for line in (proc.stdout or b"").decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        usable = True
        if entry.get("name") == instance:
            return str(entry.get("status", "")).strip().lower() == "running"
    # A usable JSON listing that simply does not contain the instance means the
    # instance does not exist.
    return False if usable else None


def _lima_plain_status(limactl: str, instance: str, timeout: float) -> bool:
    try:
        proc = subprocess.run(
            [limactl, "list"],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    for line in (proc.stdout or b"").decode("utf-8", "replace").splitlines():
        fields = line.split()
        if fields and fields[0] == instance:
            return any(field.lower() == "running" for field in fields[1:])
    return False


def lima_instance_running(
    limactl: str | None = None,
    instance: str | None = None,
    *,
    timeout: float = LIMA_LIST_TIMEOUT,
) -> bool:
    """Whether the selected Lima instance is currently running."""

    tool = limactl or shutil.which("limactl")
    if not tool:
        return False
    name = (instance or lima_instance_name()).strip()
    if not name:
        return False
    status = _lima_json_status(tool, name, timeout)
    if status is not None:
        return status
    return _lima_plain_status(tool, name, timeout)


def find_lima_runner(instance: str | None = None) -> GuestRunner | None:
    """Return a Lima-backed guest runner when ``limactl`` has a running VM."""

    limactl = shutil.which("limactl")
    if not limactl:
        return None
    name = (instance or lima_instance_name()).strip()
    if not name or not lima_instance_running(limactl, name):
        return None
    return GuestRunner(kind="lima", tool=limactl, tier="emulated_run", instance=name)


def find_guest_runner(arch: str) -> GuestRunner | None:
    """Select a runner for a Linux ELF of *arch*, or ``None`` when none exists."""

    normalized = _normalize_arch(arch)
    native = _native_runner(normalized)
    if native is not None:
        return native
    qemu = find_qemu(normalized)
    if qemu is not None:
        return GuestRunner(kind="qemu", tool=qemu, tier="emulated_run")
    return find_lima_runner()


def crash_detected(exit_code: int | None, stderr: bytes | str) -> bool:
    """Classify a process result as a crash (signal-style termination)."""

    if exit_code is not None and (exit_code < 0 or exit_code in CRASH_EXIT_CODES):
        return True
    if isinstance(stderr, bytes):
        text = stderr.decode("utf-8", "replace")
    else:
        text = str(stderr)
    lowered = text.lower()
    return any(marker in lowered for marker in _CRASH_MARKERS)


def _runner_name(selected: GuestRunner) -> str:
    if selected.kind == "native":
        return "native"
    return Path(selected.tool).name


def _guest_visible(path: Path) -> bool:
    """Whether a host path lives under the home directory mounted in the VM."""

    try:
        home = Path.home().resolve()
        resolved = Path(path).resolve()
    except OSError:
        return False
    return resolved == home or home in resolved.parents


def _lima_launch_failed(returncode: int, stderr: bytes) -> bool:
    """Distinguish a limactl/SSH launch failure from a guest program result."""

    text = stderr.decode("utf-8", "replace")
    if "level=fatal" in text or "level=error" in text:
        return True
    return "ssh:" in text and "connect" in text and returncode == 255


def _lima_guest_size(tool: str, instance: str, path: Path) -> int | None:
    """Guest-visible size of *path*, or ``None`` when it cannot be read."""

    try:
        proc = subprocess.run(
            [
                tool, "shell", "--tty=false", instance, "--",
                "stat", "-c", "%s", str(path),
            ],
            capture_output=True,
            timeout=LIMA_STAT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    text = (proc.stdout or b"").decode("utf-8", "replace").strip()
    try:
        return int(text.splitlines()[0].strip())
    except (IndexError, ValueError):
        return None


def wait_for_lima_guest_view(
    tool: str,
    instance: str,
    path: Path | str,
    *,
    attempts: int | None = None,
    interval: float | None = None,
) -> str | None:
    """Wait until the guest sees the current file size of *path*.

    Returns ``None`` when the guest view converged, or an explicit error string
    ("stale guest view") when it never did.  Callers must not execute the target
    on a non-``None`` result: a stale view can make qemu map a segment beyond
    the stale file size and die with an internal SIGBUS, which would fabricate a
    crash instead of a real execution result.
    """

    guest_path = Path(path)
    try:
        host_size = os.stat(guest_path).st_size
    except OSError as exc:
        return f"{type(exc).__name__}: {exc}"
    poll_attempts = LIMA_VIEW_POLL_ATTEMPTS if attempts is None else int(attempts)
    poll_interval = LIMA_VIEW_POLL_INTERVAL if interval is None else float(interval)
    last_size: int | None = None
    for attempt in range(max(1, poll_attempts)):
        last_size = _lima_guest_size(tool, instance, guest_path)
        if last_size == host_size:
            return None
        if attempt + 1 < max(1, poll_attempts):
            time.sleep(max(0.0, poll_interval))
    return (
        f"stale guest view for {guest_path}: host size={host_size} "
        f"guest size={last_size if last_size is not None else 'unknown'} "
        f"after {max(1, poll_attempts)} polls; refusing to execute a stale binary"
    )


def run_path(
    path: Path | str,
    argv: list[str] | None = None,
    *,
    arch: str = "x86_64",
    stdin: bytes = b"",
    timeout: float = 10.0,
    runner: GuestRunner | None = None,
    cwd: Path | str | None = None,
) -> GuestResult:
    """Execute *path* with *argv* in a native/qemu/Lima environment.

    ``argv`` are the arguments passed to the target (not including the target
    path itself).  When no runner can be selected, ``available`` is ``False``
    and nothing is executed.
    """

    selected = runner if runner is not None else find_guest_runner(arch)
    if selected is None:
        return GuestResult(
            False,
            error=f"no native/qemu/lima guest runner for arch {arch!r}",
            runner="",
            tier="",
        )
    exec_path = Path(path)
    run_cwd = Path(cwd) if cwd is not None else exec_path.parent
    name = _runner_name(selected)
    common = {"runner": name, "tier": selected.tier, "tool": name}
    args = [str(arg) for arg in (argv or [])]

    if selected.kind == "lima":
        instance = (selected.instance or lima_instance_name()).strip()
        if not instance:
            return GuestResult(True, error="Lima instance name is empty", **common)
        if not (_guest_visible(exec_path) and _guest_visible(run_cwd)):
            return GuestResult(
                True,
                error=(
                    "lima execution requires the executable and working directory "
                    "to be staged under the host home directory "
                    f"({Path.home()}); got path={exec_path} cwd={run_cwd}"
                ),
                **common,
            )
        stale_error = wait_for_lima_guest_view(
            selected.tool, instance, Path(exec_path).absolute(),
        )
        if stale_error is not None:
            # Do not execute a stale binary: evidence must stay unavailable
            # rather than a fabricated qemu SIGBUS crash.
            return GuestResult(True, error=stale_error, **common)
        command = [
            selected.tool,
            "shell",
            "--tty=false",
            "--workdir",
            str(run_cwd),
            instance,
            "--",
            str(exec_path),
            *args,
        ]
        env = None
    else:
        if selected.kind == "qemu":
            command = [selected.tool, str(exec_path), *args]
        else:
            command = [str(exec_path), *args]
        # Scrubbed environment: only what the target needs to run.
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(run_cwd),
            "TMPDIR": str(run_cwd),
            "LC_ALL": "C",
        }

    try:
        proc = subprocess.run(
            command,
            input=stdin,
            capture_output=True,
            timeout=timeout,
            cwd=str(run_cwd),
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return GuestResult(True, timed_out=True, error="timeout", **common)
    except OSError as exc:
        return GuestResult(True, error=f"{type(exc).__name__}: {exc}", **common)
    except subprocess.SubprocessError as exc:  # pragma: no cover - defensive
        return GuestResult(True, error=f"{type(exc).__name__}: {exc}", **common)

    stdout = proc.stdout or b""
    stderr = proc.stderr or b""
    if selected.kind == "lima" and _lima_launch_failed(proc.returncode, stderr):
        detail = stderr.decode("utf-8", "replace").strip().splitlines()
        message = detail[-1] if detail else "unknown limactl failure"
        return GuestResult(
            True,
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            error=f"limactl failed to launch the target: {message[:300]}",
            **common,
        )
    return GuestResult(
        True,
        stdout=stdout,
        stderr=stderr,
        exit_code=proc.returncode,
        crashed=crash_detected(proc.returncode, stderr),
        **common,
    )


def run_elf(path: Path | str, *, arch: str = "x86_64", stdin: bytes = b"",
            timeout: float = 10.0) -> GuestResult:
    """Legacy qemu-only helper kept for existing callers.

    Unlike :func:`run_path` this never falls back to Lima; it reports
    ``available=False`` when qemu-user is absent.
    """

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
        stderr = proc.stderr or b""
        return GuestResult(True, proc.stdout or b"", stderr, proc.returncode,
                           tool=Path(tool).name,
                           crashed=crash_detected(proc.returncode, stderr),
                           runner=Path(tool).name,
                           tier="emulated_run")
    except subprocess.TimeoutExpired as exc:
        return GuestResult(True, exc.stdout or b"", exc.stderr or b"",
                           timed_out=True, error="timeout",
                           tool=Path(tool).name,
                           runner=Path(tool).name,
                           tier="emulated_run")
    except Exception as exc:  # noqa: BLE001
        return GuestResult(True, error=f"{type(exc).__name__}: {exc}",
                           tool=Path(tool).name,
                           runner=Path(tool).name,
                           tier="emulated_run")
