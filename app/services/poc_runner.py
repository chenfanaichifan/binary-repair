"""Real PoC/regression execution evidence for a repaired candidate.

This module runs a *user/fixture supplied* PoC manifest against the original and
repaired binaries and returns typed evidence.  It is deliberately conservative:
- only formats with an available native/qemu runner are executed;
- PE and 32-bit Mach-O are reported unavailable instead of being faked;
- every command is timeout-bounded, runs in a temporary directory with a
  scrubbed environment, and never uses a shell.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_TIMEOUT = 5.0
MAX_STDOUT = 64 * 1024
MAX_STDERR = 16 * 1024


@dataclass
class CaseResult:
    case_id: str
    kind: str
    executable: str
    exit_code: int | None
    crashed: bool
    stdout: str
    stderr: str
    stdout_hex: str = ""
    timed_out: bool = False
    error: str | None = None
    expected_ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "kind": self.kind,
            "executable": self.executable,
            "exit_code": self.exit_code,
            "crashed": self.crashed,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_hex": self.stdout_hex,
            "timed_out": self.timed_out,
            "error": self.error,
            "expected_ok": self.expected_ok,
        }


@dataclass
class PocEvidence:
    status: str = "not_run"
    runner: str = ""
    cases: list[CaseResult] = field(default_factory=list)
    regression: list[CaseResult] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    original_sha256: str = ""
    candidate_sha256: str | None = None

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "runner": self.runner,
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "poc": [case.to_dict() for case in self.cases],
            "regression": [case.to_dict() for case in self.regression],
            "limitations": list(self.limitations),
        }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest(manifest: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(manifest, (str, Path)):
        raw = Path(manifest).read_text(encoding="utf-8")
        data = json.loads(raw)
    else:
        data = manifest
    if not isinstance(data, dict):
        raise ValueError("PoC manifest must be a JSON object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported PoC manifest schema_version")
    for key in ("fixture_sha256", "format", "arch", "target"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ValueError(f"PoC manifest requires string field {key!r}")
    if not isinstance(data.get("poc"), list) or not data["poc"]:
        raise ValueError("PoC manifest requires non-empty 'poc'")
    if not isinstance(data.get("regression"), list):
        raise ValueError("PoC manifest requires a 'regression' list (may be empty for no-input cases)")
    for group in ("poc", "regression"):
        for case in data[group]:
            if not isinstance(case, dict):
                raise ValueError("PoC case must be an object")
            if not isinstance(case.get("id"), str) or not case["id"]:
                raise ValueError("PoC case requires id")
            argv = case.get("argv")
            if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                raise ValueError("PoC case argv must be a list of strings")
    return data


def _runner_for(format_name: str, arch: str) -> tuple[str, str] | None:
    """Return (kind, executable) for a runnable target, or None."""
    if format_name == "elf":
        if sys.platform.startswith("linux") and arch == "x86_64":
            return ("native", "")
        try:
            from app.services.guest_runner import find_qemu

            qemu = find_qemu(arch)
        except Exception:  # noqa: BLE001
            qemu = None
        if qemu:
            return ("qemu", qemu)
        return None
    if format_name == "macho" and sys.platform == "darwin" and arch == platform.machine():
        return ("native", "")
    return None


def _execute(
    path: Path,
    *,
    runner_kind: str,
    runner: str,
    argv: list[str],
    stdin: bytes,
    timeout: float,
) -> tuple[int | None, bool, bytes, str, bool, str | None]:
    command = ([runner] if runner_kind == "qemu" else []) + [str(path), *argv]
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(path.parent),
        "TMPDIR": str(path.parent),
        "LC_ALL": "C",
    }
    try:
        proc = subprocess.run(
            command, input=stdin, capture_output=True, timeout=timeout,
            cwd=str(path.parent), env=env, check=False,
        )
    except subprocess.TimeoutExpired:
        return None, False, b"", "", True, "timeout"
    except OSError as exc:
        return None, False, b"", "", False, f"{type(exc).__name__}: {exc}"
    stdout_raw = proc.stdout[:MAX_STDOUT]
    stdout = stdout_raw.decode("utf-8", "replace")
    stderr = proc.stderr[:MAX_STDERR].decode("utf-8", "replace")
    crashed = proc.returncode is not None and proc.returncode < 0
    if not crashed and runner_kind == "qemu":
        crashed = "target signal" in stderr or "Segmentation fault" in stderr
    return proc.returncode, crashed, stdout_raw, stderr, False, None


def _expected_ok(actual_exit: int | None, crashed: bool, actual_stdout: str,
                 actual_stdout_hex: str, actual_stderr: str,
                 expected: dict[str, Any], *, is_poc: bool) -> bool:
    if "crashed" in expected:
        want = bool(expected["crashed"])
        if is_poc and want:
            return crashed or (actual_exit is not None and actual_exit != 0)
        if crashed != want:
            return False
    if "exit_code" in expected:
        want = expected["exit_code"]
        if want is None:
            if actual_exit != 0:
                return False
        elif actual_exit != int(want):
            return False
    if "stdout" in expected:
        if actual_stdout != str(expected["stdout"]):
            return False
    if "stdout_hex" in expected:
        if actual_stdout_hex.lower() != str(expected["stdout_hex"]).lower():
            return False
    if "stdout_contains" in expected:
        if str(expected["stdout_contains"]) not in actual_stdout:
            return False
    if "stderr" in expected:
        if actual_stderr != str(expected["stderr"]):
            return False
    if "stderr_contains" in expected:
        if str(expected["stderr_contains"]) not in actual_stderr:
            return False
    return True


def run_poc(
    original: bytes,
    candidate: bytes | None,
    manifest: dict[str, Any] | str | Path,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> PocEvidence:
    evidence = PocEvidence(original_sha256=_sha(original))
    try:
        spec = load_manifest(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        evidence.status = "fail"
        evidence.limitations.append(f"invalid PoC manifest: {type(exc).__name__}: {exc}")
        return evidence
    if spec["fixture_sha256"] != evidence.original_sha256:
        evidence.status = "fail"
        evidence.limitations.append("PoC fixture_sha256 does not match the uploaded original")
        return evidence
    if candidate is None:
        evidence.status = "fail"
        evidence.limitations.append("no candidate bytes to execute")
        return evidence
    evidence.candidate_sha256 = _sha(candidate)
    selected = _runner_for(str(spec["format"]), str(spec["arch"]))
    if selected is None:
        evidence.status = "unavailable"
        evidence.limitations.append(
            "no native/qemu runner for this format/arch on this host; PoC was not executed"
        )
        return evidence
    runner_kind, runner = selected
    evidence.runner = "native" if runner_kind == "native" else Path(runner).name
    with tempfile.TemporaryDirectory(prefix="br-poc-") as tmp:
        root = Path(tmp)
        original_path = root / "original"
        candidate_path = root / "candidate"
        original_path.write_bytes(original)
        candidate_path.write_bytes(candidate)
        original_path.chmod(0o700)
        candidate_path.chmod(0o700)

        def run_cases(
            data_path: Path, run_group: str, *, is_original: bool,
        ) -> list[CaseResult]:
            results: list[CaseResult] = []
            for case in spec[run_group]:
                stdin = b""
                if case.get("stdin_base64"):
                    stdin = base64.b64decode(case["stdin_base64"], validate=True)
                exit_code, crashed, stdout_bytes, stderr, timed_out, error = _execute(
                    data_path, runner_kind=runner_kind, runner=runner,
                    argv=list(case["argv"]), stdin=stdin, timeout=timeout,
                )
                expected = case.get("original" if is_original else "candidate") or {}
                stdout = stdout_bytes.decode("utf-8", "replace")
                ok = _expected_ok(
                    exit_code, crashed, stdout, stdout_bytes.hex(), stderr, expected,
                    is_poc=run_group == "poc",
                )
                results.append(CaseResult(
                    case_id=case["id"], kind=run_group, executable="original" if is_original else "candidate",
                    exit_code=exit_code, crashed=crashed, stdout=stdout, stderr=stderr,
                    stdout_hex=stdout_bytes.hex(), timed_out=timed_out, error=error,
                    expected_ok=ok,
                ))
            return results

        evidence.cases = run_cases(original_path, "poc", is_original=True)
        candidate_cases = run_cases(candidate_path, "poc", is_original=False)
        evidence.cases.extend(candidate_cases)
        evidence.regression = run_cases(original_path, "regression", is_original=True)
        candidate_regression = run_cases(candidate_path, "regression", is_original=False)
        evidence.regression.extend(candidate_regression)

    if any(case.error or case.timed_out for case in evidence.cases + evidence.regression):
        evidence.status = "fail"
        evidence.limitations.append("one or more PoC/regression executions failed to run")
        return evidence
    original_poc = evidence.cases[: len(spec["poc"])]
    candidate_poc = evidence.cases[len(spec["poc"]):]
    original_regression = evidence.regression[: len(spec["regression"])]
    candidate_regression = evidence.regression[len(spec["regression"]):]
    passed = (
        all(case.expected_ok for case in original_poc)
        and all(case.expected_ok for case in candidate_poc)
        and all(case.expected_ok for case in original_regression)
        and all(case.expected_ok for case in candidate_regression)
    )
    # Regression must compare candidate against original where the manifest does
    # not spell out an explicit expected value: use original's observed values.
    if passed:
        for orig, cand in zip(original_regression, candidate_regression):
            if not _regression_equal(orig, cand):
                passed = False
                cand.expected_ok = False
                evidence.limitations.append(
                    f"regression mismatch for {orig.case_id}: original exit="
                    f"{orig.exit_code} stdout={orig.stdout!r}, candidate exit="
                    f"{cand.exit_code} stdout={cand.stdout!r}"
                )
    evidence.status = "pass" if passed else "fail"
    return evidence


def _regression_equal(original: CaseResult, candidate: CaseResult) -> bool:
    return (
        original.exit_code == candidate.exit_code
        and not original.crashed
        and not candidate.crashed
        and original.stdout == candidate.stdout
        and original.stderr == candidate.stderr
    )


def poc_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "fields": {
            "fixture_sha256": "SHA-256 of the uploaded original",
            "format": "elf|pe|macho",
            "arch": "x86_64|arm64|i386",
            "target": "function name for reporting",
            "poc": "cases the original must fail; candidate must be safe",
            "regression": "valid-input cases compared original vs candidate",
        },
        "runner": "native on matching Linux/macOS hosts; qemu-user for ELF cross-arch; otherwise unavailable",
        "limits": {"timeout_seconds": DEFAULT_TIMEOUT, "stdout_bytes": MAX_STDOUT},
    }
