"""Native Mach-O execution evidence for repaired candidates.

Only used on macOS hosts where the candidate can actually run.  Modified Mach-O
files are ad-hoc re-signed (``codesign -s -``) purely so the local kernel will
load them; this is not a forgery of the original developer signature and the
report records ``codesign_invalidated``.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from app.services.runtime.evidence import RuntimeCase, RuntimeEvidence, judge

TIMEOUT_SECONDS = 10.0
ENV = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C"}


def _host_arch() -> str:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine in {"x86_64", "amd64"}:
        return "x86_64"
    return machine


def available() -> bool:
    return sys.platform == "darwin" and shutil.which("codesign") is not None


def _resign(path: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["/usr/bin/codesign", "--force", "--sign", "-", str(path)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=20, env={**os.environ, **ENV},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{type(exc).__name__}: {exc}"
    if proc.returncode != 0:
        return f"codesign failed ({proc.returncode}): {proc.stdout.strip()[:200]}"
    return None


def _command(path: Path, arch: str) -> list[str]:
    if arch == "x86_64" and _host_arch() == "arm64":
        return ["/usr/bin/arch", "-x86_64", str(path)]
    return [str(path)]


def run(
    data: bytes,
    *,
    arch: str,
    capacity: int,
    lengths: list[int] | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> RuntimeEvidence:
    evidence = RuntimeEvidence(tier="native_run", engine="macho-native")
    if not available():
        evidence.tier = "unavailable"
        evidence.verdict = "unavailable"
        evidence.limitations.append("native Mach-O execution requires a macOS host with codesign")
        return evidence
    if capacity <= 0:
        evidence.tier = "unavailable"
        evidence.verdict = "unavailable"
        evidence.limitations.append("capacity is not positive")
        return evidence

    probe = [0, 1, capacity - 1, capacity, capacity + 1, capacity * 4]
    selected = sorted({value for value in (lengths or probe) if value >= 0})
    with tempfile.TemporaryDirectory(prefix="binaryrepair-native-") as tmp:
        path = Path(tmp) / "candidate"
        path.write_bytes(data)
        path.chmod(0o755)
        error = _resign(path)
        if error:
            evidence.tier = "unavailable"
            evidence.verdict = "unavailable"
            evidence.limitations.append(f"ad-hoc codesign failed: {error}")
            return evidence
        for length in selected:
            argument = "A" * length
            case = None
            for attempt in range(2):
                try:
                    proc = subprocess.run(
                        [*_command(path, arch), argument],
                        cwd=tmp, env={**os.environ, **ENV}, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        timeout=timeout,
                    )
                    stdout = proc.stdout or ""
                    case = RuntimeCase(
                        input_len=length,
                        exit_code=proc.returncode,
                        stdout_len=len(stdout.rstrip("\n")),
                        stderr_len=len(proc.stderr or ""),
                        output_len=len(stdout.rstrip("\n")),
                    )
                    break
                except subprocess.TimeoutExpired:
                    case = RuntimeCase(input_len=length, timed_out=True, error="timeout")
                    break
                except OSError as exc:
                    case = RuntimeCase(input_len=length,
                                       error=f"{type(exc).__name__}: {exc}")
                    if attempt == 0:
                        time.sleep(0.2)
            if case is not None:
                evidence.cases.append(case)
    evidence.verdict = judge(evidence.cases, capacity)
    evidence.limitations.extend([
        "Native run is a local macOS execution, not a hardened guest.",
        "The candidate was ad-hoc re-signed for loading; the original signature is not preserved.",
    ])
    return evidence
