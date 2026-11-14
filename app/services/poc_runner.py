"""Real PoC/regression execution evidence for a repaired candidate.

This module runs a *user/fixture supplied* PoC manifest against the original and
repaired binaries and returns typed evidence.  It is deliberately conservative:

- only formats with an available native/qemu/Lima runner are executed;
- PE and 32-bit Mach-O are reported unavailable instead of being faked;
- every command is timeout-bounded, runs in a staged directory with a scrubbed
  environment, and never uses a shell;
- per-case ``files`` (base64) are staged into that directory and ``{tmp}`` in
  ``argv`` is replaced by its absolute path, so file-based PoCs (archives,
  inputs) need no host/guest path juggling;
- for the Lima tier the staging directory lives under ``$HOME`` (the guest
  mounts the host home read-only at the same path) and is removed afterwards.
"""
from __future__ import annotations

import base64
import binascii
import contextlib
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from app.services.guest_runner import GuestRunner, find_guest_runner, run_path

SCHEMA_VERSION = 1
DEFAULT_TIMEOUT = 5.0
MAX_STDOUT = 64 * 1024
MAX_STDERR = 16 * 1024
MAX_STAGED_FILE = 8 * 1024 * 1024
MAX_STAGED_TOTAL = 32 * 1024 * 1024
STAGE_ENV = "BINARYREPAIR_GUEST_STAGE"
DEFAULT_STAGE_DIR = ".br-guest-stage"
TMP_PLACEHOLDER = "{tmp}"
_CASE_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


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
    tier: str = ""
    stdout_signature: str = "not_run"
    no_input: bool = False
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
            "tier": self.tier,
            "stdout_signature": self.stdout_signature,
            "no_input": self.no_input,
            "original_sha256": self.original_sha256,
            "candidate_sha256": self.candidate_sha256,
            "poc": [case.to_dict() for case in self.cases],
            "regression": [case.to_dict() for case in self.regression],
            "limitations": list(self.limitations),
        }


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_arch(arch: str) -> str:
    return {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "x86-64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(str(arch or "").strip().lower(), str(arch or "").strip().lower())


def _host_arch() -> str:
    return _normalize_arch(platform.machine())


def _validate_case_files(case: dict[str, Any], *, where: str) -> None:
    files = case.get("files")
    if files is None:
        return
    if not isinstance(files, list):
        raise ValueError(f"PoC case {where} field 'files' must be a list")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError(f"PoC case {where} entry in 'files' must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"PoC case {where} staged file requires a string name")
        if not _CASE_FILE_NAME.match(name) or name in {".", ".."}:
            raise ValueError(
                f"PoC case {where} staged file name must be a plain file name, got {name!r}"
            )
        if name in seen:
            raise ValueError(f"PoC case {where} has duplicate staged file name {name!r}")
        seen.add(name)
        encoded = item.get("base64")
        if not isinstance(encoded, str):
            raise ValueError(f"PoC case {where} staged file {name!r} requires string base64")
        if len(encoded) > (MAX_STAGED_FILE * 4) // 3 + 16:
            raise ValueError(f"PoC case {where} staged file {name!r} is too large")
        try:
            base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                f"PoC case {where} staged file {name!r} has invalid base64: {exc}"
            ) from exc


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
    if "no_input" in data and not isinstance(data["no_input"], bool):
        raise ValueError("PoC manifest field 'no_input' must be a boolean")
    for group in ("poc", "regression"):
        for index, case in enumerate(data[group]):
            where = f"{group}[{index}]"
            if not isinstance(case, dict):
                raise ValueError("PoC case must be an object")
            if not isinstance(case.get("id"), str) or not case["id"]:
                raise ValueError("PoC case requires id")
            argv = case.get("argv")
            if not isinstance(argv, list) or not all(isinstance(x, str) for x in argv):
                raise ValueError("PoC case argv must be a list of strings")
            if "stdin_base64" in case:
                stdin_encoded = case["stdin_base64"]
                if not isinstance(stdin_encoded, str):
                    raise ValueError(f"PoC case {where} stdin_base64 must be a string")
                try:
                    base64.b64decode(stdin_encoded, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise ValueError(f"PoC case {where} stdin_base64 is invalid: {exc}") from exc
            _validate_case_files(case, where=where)
    return data


def _select_runner(format_name: str, arch: str) -> GuestRunner | None:
    """Return the guest runner for a runnable target, or None.

    Linux ELF targets use the native/qemu/Lima guest runner.  Native Mach-O
    execution on a matching macOS host is kept for backwards compatibility; PE
    and 32-bit Mach-O remain explicitly unavailable (never faked).
    """

    if format_name == "elf":
        return find_guest_runner(arch)
    if format_name == "macho" and sys.platform == "darwin" and _normalize_arch(arch) == _host_arch():
        return GuestRunner(kind="native", tool="", tier="native_run")
    return None


def _staging_base() -> Path:
    """Host directory that also hosts Lima staging (override via env)."""

    override = (os.environ.get(STAGE_ENV) or "").strip()
    base = Path(override).expanduser() if override else Path.home() / DEFAULT_STAGE_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


@contextlib.contextmanager
def _staging_root(runner: GuestRunner) -> Iterator[Path]:
    """Create the execution root and remove it afterwards.

    Lima guests see the host home directory read-only at the same path, so the
    staging tree must live under ``$HOME`` for that tier.  Native/qemu runs use
    an ordinary temporary directory.
    """

    if runner.kind == "lima":
        base = _staging_base()
        root = Path(tempfile.mkdtemp(prefix="br-poc-", dir=str(base)))
        try:
            yield root
        finally:
            shutil.rmtree(root, ignore_errors=True)
    else:
        with tempfile.TemporaryDirectory(prefix="br-poc-") as tmp:
            yield Path(tmp)


def _case_files(case: dict[str, Any]) -> list[tuple[str, bytes]]:
    """Decode the staged files of one case (validated in :func:`load_manifest`)."""

    decoded: list[tuple[str, bytes]] = []
    total = 0
    for item in case.get("files") or []:
        name = item["name"]
        if not _CASE_FILE_NAME.match(name):
            raise ValueError(f"unsafe staged file name {name!r}")
        try:
            data = base64.b64decode(item["base64"], validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"invalid base64 in staged file {name!r}: {exc}") from exc
        if len(data) > MAX_STAGED_FILE:
            raise ValueError(f"staged file {name!r} exceeds {MAX_STAGED_FILE} bytes")
        total += len(data)
        if total > MAX_STAGED_TOTAL:
            raise ValueError(f"staged files exceed {MAX_STAGED_TOTAL} bytes in total for one case")
        decoded.append((name, data))
    return decoded


def _preflight(spec: dict[str, Any]) -> None:
    """Decode/validate every case's staged files before any execution."""

    total = 0
    for group in ("poc", "regression"):
        for case in spec[group]:
            for _name, data in _case_files(case):
                total += len(data)
    if total > MAX_STAGED_TOTAL:
        raise ValueError(f"PoC staged payload exceeds {MAX_STAGED_TOTAL} bytes")


def _prepare_case_dir(root: Path, group: str, index: int, case: dict[str, Any]) -> Path:
    """(Re)create the staged directory for one case and write its files."""

    case_dir = root / f"case-{group}-{index:02d}"
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True)
    for name, data in _case_files(case):
        target = case_dir / name
        target.write_bytes(data)
        target.chmod(0o600)
    return case_dir


def _substitute_argv(argv: list[str], case_dir: Path) -> list[str]:
    marker = str(case_dir)
    return [str(arg).replace(TMP_PLACEHOLDER, marker) for arg in argv]


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


def _run_case(
    *,
    binary_bytes: bytes,
    case: dict[str, Any],
    group: str,
    index: int,
    is_original: bool,
    arch: str,
    runner: GuestRunner,
    root: Path,
    stdin: bytes,
    timeout: float,
) -> CaseResult:
    case_dir = _prepare_case_dir(root, group, index, case)
    # Both sides of the differential are executed from the *same* staged path so
    # that argv[0]-dependent output (e.g. ``--help`` printing its program path)
    # stays comparable between the original and the candidate.
    binary_path = case_dir / "target"
    binary_path.write_bytes(binary_bytes)
    binary_path.chmod(0o700)
    argv = _substitute_argv(case["argv"], case_dir)
    result = run_path(
        binary_path,
        argv,
        arch=arch,
        stdin=stdin,
        timeout=timeout,
        runner=runner,
        cwd=case_dir,
    )
    stdout_bytes = (result.stdout or b"")[:MAX_STDOUT]
    stdout = stdout_bytes.decode("utf-8", "replace")
    stderr = (result.stderr or b"")[:MAX_STDERR].decode("utf-8", "replace")
    expected = case.get("original" if is_original else "candidate") or {}
    ok = _expected_ok(
        result.exit_code, result.crashed, stdout, stdout_bytes.hex(), stderr, expected,
        is_poc=group == "poc",
    )
    return CaseResult(
        case_id=case["id"],
        kind=group,
        executable="original" if is_original else "candidate",
        exit_code=result.exit_code,
        crashed=result.crashed,
        stdout=stdout,
        stderr=stderr,
        stdout_hex=stdout_bytes.hex(),
        timed_out=result.timed_out,
        error=result.error,
        expected_ok=ok,
    )


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
    evidence.no_input = bool(spec.get("no_input", False))
    if spec["fixture_sha256"] != evidence.original_sha256:
        evidence.status = "fail"
        evidence.limitations.append("PoC fixture_sha256 does not match the uploaded original")
        return evidence
    if candidate is None:
        evidence.status = "fail"
        evidence.limitations.append("no candidate bytes to execute")
        return evidence
    evidence.candidate_sha256 = _sha(candidate)
    selected = _select_runner(str(spec["format"]), str(spec["arch"]))
    if selected is None:
        evidence.status = "unavailable"
        evidence.limitations.append(
            "no native/qemu/lima runner for this format/arch on this host; "
            "PoC was not executed"
        )
        return evidence
    try:
        _preflight(spec)
    except ValueError as exc:
        evidence.status = "fail"
        evidence.limitations.append(f"invalid PoC staged files: {exc}")
        return evidence
    evidence.runner = "native" if selected.kind == "native" else Path(selected.tool).name
    evidence.tier = selected.tier
    arch = str(spec["arch"])

    try:
        with _staging_root(selected) as root:

            def run_group(group: str) -> tuple[list[CaseResult], list[CaseResult]]:
                originals: list[CaseResult] = []
                candidates: list[CaseResult] = []
                for index, case in enumerate(spec[group]):
                    stdin = b""
                    if case.get("stdin_base64"):
                        stdin = base64.b64decode(case["stdin_base64"], validate=True)
                    for is_original in (True, False):
                        result = _run_case(
                            binary_bytes=original if is_original else candidate,
                            case=case,
                            group=group,
                            index=index,
                            is_original=is_original,
                            arch=arch,
                            runner=selected,
                            root=root,
                            stdin=stdin,
                            timeout=timeout,
                        )
                        (originals if is_original else candidates).append(result)
                return originals, candidates

            original_poc, candidate_poc = run_group("poc")
            original_regression, candidate_regression = run_group("regression")
    except OSError as exc:
        evidence.status = "fail"
        evidence.limitations.append(
            f"PoC staging failed: {type(exc).__name__}: {exc}"
        )
        return evidence
    except ValueError as exc:
        evidence.status = "fail"
        evidence.limitations.append(f"invalid PoC case data: {exc}")
        return evidence

    # Preserve the historical evidence layout: all original cases first, then
    # the candidate cases of the same group.
    evidence.cases = original_poc + candidate_poc
    evidence.regression = original_regression + candidate_regression

    if any(case.error or case.timed_out for case in evidence.cases + evidence.regression):
        evidence.status = "fail"
        evidence.limitations.append("one or more PoC/regression executions failed to run")
        return evidence
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
    if evidence.no_input:
        evidence.stdout_signature = "not_applicable"
    elif original_regression and candidate_regression:
        evidence.stdout_signature = (
            "matched"
            if all(a.stdout_hex == b.stdout_hex for a, b in zip(original_regression, candidate_regression))
            else "mismatch"
        )
    else:
        evidence.stdout_signature = "not_applicable"
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
            "files": (
                "optional per-case list of {name, base64} staged in the execution "
                "directory; argv may reference {tmp}/name"
            ),
        },
        "runner": (
            "native on matching Linux hosts; qemu-user for ELF cross-arch; Lima VM "
            "when a running instance is available; otherwise unavailable"
        ),
        "limits": {
            "timeout_seconds": DEFAULT_TIMEOUT,
            "stdout_bytes": MAX_STDOUT,
            "staged_file_bytes": MAX_STAGED_FILE,
        },
    }
