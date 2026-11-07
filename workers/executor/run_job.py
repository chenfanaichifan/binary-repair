#!/usr/bin/env python3
"""Guest executor for one staged job package (T6.2). GUEST ONLY.

The executor is the only part of this repository allowed to run a staged
candidate.  It refuses the host, refuses root, and refuses any account other
than the configured unprivileged executor account (uid 1003 by default).

It does not decide an outcome.  It verifies a package, runs a closed set of
frozen steps for the package's route, and writes:

    bundle.json          host ingest shape (route_b/route_a, gates, artifacts)
    result-bundle.json   legacy V0-V5 shape used by the worker adapter
    isolation.json       account/kernel/capability/netns attestation
    run.log              commands and exit codes
    SHA256SUMS           every output file except the manifest itself
    bundle-sha256.txt    sha256 of SHA256SUMS

A step failure leaves no "passed" gate.  A missing check stays not_run.

Package layout (all paths are package-relative):

    package.json
    original.elf
    contract.json
    tests/valid.json
    tests/invalid.json          # route_a only
    candidate.elf               # required unless route_b builds from c_source
    replacement.c               # optional route_b source
    edit-manifest.json          # optional route_a static evidence
    audit.json                  # optional route_a static evidence
    readelf-audit.txt           # optional route_a static evidence
    evidence/                   # optional route_a typed evidence
    SHA256SUMS                  # every other file, sorted

package.json:

    {
      "schema_version": 1,
      "job_id": "...",
      "route": "route_a" | "route_b",
      "purpose": "screening" | "repair",
      "func": "...",                     // route_b
      "mode": "roundtrip" | "fixed",     // route_b; default by purpose
      "input_mode": "argv" | "stdin" | "none",
      "run_manifest": true,              // optional; default true for repair
      "original": "original.elf",
      "contract": "contract.json",
      "tests": "tests",
      "candidate": "candidate.elf",
      "c_source": "replacement.c",
      "edit_manifest": "edit-manifest.json",
      "audit": "audit.json",
      "readelf": "readelf-audit.txt",
      "expected": {
        "original_sha256": "<64 hex>",
        "candidate_sha256": "<64 hex>",
        "contract_sha256": "<64 hex>"    // optional
      }
    }

Usage (in the guest, as the executor account):

    /opt/angr-venv/bin/python workers/executor/run_job.py \
      --package /var/lib/binrepair/jobs/<job>/staging/<attempt> \
      --out /var/lib/binrepair/jobs/<job>/runs/<run>/attempts/<attempt>.routeb \
      --guest-ack

Use ``--plan-only`` to verify the package and print the planned commands
without running anything.  That is the only safe mode on a non-guest host and
is what the self-test exercises.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_REFUSED = 2
EXIT_PACKAGE = 3
EXIT_STEP = 4
EXIT_OUTPUT = 5

DEFAULT_EXPECTED_UID = 1003
SCHEMA_VERSION = 1
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
SUM_RE = re.compile(r"^([0-9a-fA-F]{64})[ \t]+\*?(.+)$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ROUTES = {"route_a", "route_b"}
PURPOSES = {"screening", "repair"}
MODES = {"roundtrip", "fixed"}
INPUT_MODES = {"argv", "stdin", "none"}
STATUS_MAP = {
    "pass": "passed",
    "passed": "passed",
    "fail": "failed",
    "failed": "failed",
    "not_run": "not_run",
    "inconclusive": "unknown",
    "unsupported": "unknown",
    "unknown": "unknown",
    "timed_out": "timed_out",
}
LEGACY_STATUS = {
    "passed": "pass",
    "failed": "fail",
    "not_run": "not_run",
    "unknown": "inconclusive",
    "timed_out": "inconclusive",
}
GATES = ("V0", "V1", "V2", "V3", "V4", "V5")


class ExecutorError(Exception):
    """A deliberate refusal or a failed verification/step."""

    def __init__(self, reason: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.exit_code = exit_code


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExecutorError("package_invalid", f"cannot read JSON {path}: {exc}", EXIT_PACKAGE) from exc
    if not isinstance(data, dict):
        raise ExecutorError("package_invalid", f"{path} must contain a JSON object", EXIT_PACKAGE)
    return data


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _safe_rel(root: Path, raw: str, *, field: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ExecutorError("package_invalid", f"{field} must be a non-empty relative path", EXIT_PACKAGE)
    if raw.startswith(("/", "\\")) or (len(raw) > 1 and raw[1] == ":"):
        raise ExecutorError("package_invalid", f"{field} is absolute: {raw!r}", EXIT_PACKAGE)
    rel = Path(raw)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise ExecutorError("package_invalid", f"{field} is not a safe relative path: {raw!r}", EXIT_PACKAGE)
    candidate = root / rel
    if candidate.is_symlink():
        raise ExecutorError("package_invalid", f"{field} is a symlink: {raw!r}", EXIT_PACKAGE)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ExecutorError("package_invalid", f"{field} escapes the package: {raw!r}", EXIT_PACKAGE) from exc
    return candidate


def _check_no_symlinks(root: Path) -> None:
    """Reject symlinks anywhere below the package root."""
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        for name in list(dirs):
            path = current_path / name
            if path.is_symlink():
                raise ExecutorError(
                    "package_invalid",
                    f"package contains a symlinked directory: {path.relative_to(root).as_posix()}",
                    EXIT_PACKAGE,
                )
        for name in files:
            path = current_path / name
            if path.is_symlink():
                raise ExecutorError(
                    "package_invalid",
                    f"package contains a symlink: {path.relative_to(root).as_posix()}",
                    EXIT_PACKAGE,
                )


def _reject_writable_package(root: Path) -> None:
    """A staged package is input; group/world-writable files are not trusted."""
    if os.name != "posix":
        return
    root_mode = root.stat().st_mode
    if root_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ExecutorError("package_invalid", "package root is group/world writable", EXIT_PACKAGE)
    for current, dirs, files in os.walk(root):
        for name in dirs + files:
            path = Path(current) / name
            try:
                mode = path.stat().st_mode
            except OSError as exc:
                raise ExecutorError("package_invalid", f"cannot stat {path}: {exc}", EXIT_PACKAGE) from exc
            if mode & (stat.S_IWGRP | stat.S_IWOTH):
                raise ExecutorError(
                    "package_invalid",
                    f"package entry is group/world writable: {path.relative_to(root).as_posix()}",
                    EXIT_PACKAGE,
                )


def read_sums(root: Path) -> dict[str, str]:
    path = root / "SHA256SUMS"
    if not path.is_file() or path.is_symlink():
        raise ExecutorError("package_invalid", "SHA256SUMS is missing or is a symlink", EXIT_PACKAGE)
    entries: dict[str, str] = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        match = SUM_RE.match(line)
        if match is None:
            raise ExecutorError("package_invalid", f"SHA256SUMS:{lineno}: malformed line", EXIT_PACKAGE)
        digest, raw_name = match.group(1).lower(), match.group(2).strip()
        name = raw_name.replace("\\", "/")
        if name in entries:
            raise ExecutorError("package_invalid", f"SHA256SUMS:{lineno}: duplicate file {name}", EXIT_PACKAGE)
        entries[name] = digest
    if not entries:
        raise ExecutorError("package_invalid", "SHA256SUMS has no entries", EXIT_PACKAGE)
    return entries


def verify_package(package: Path, *, check_permissions: bool = True) -> dict[str, Any]:
    """Verify package structure, hashes and expected identities.

    Returns the parsed package map with resolved ``paths``.  Raises
    ``ExecutorError`` before any step runs on any mismatch.
    """
    package = package.resolve()
    if not package.is_dir() or package.is_symlink():
        raise ExecutorError("package_invalid", f"package is not a directory: {package}", EXIT_PACKAGE)
    if check_permissions:
        _reject_writable_package(package)
    _check_no_symlinks(package)

    manifest_path = package / "package.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ExecutorError("package_invalid", "package.json is missing or is a symlink", EXIT_PACKAGE)
    package_map = read_json(manifest_path)
    if package_map.get("schema_version") != SCHEMA_VERSION:
        raise ExecutorError("package_invalid", f"package schema_version must be {SCHEMA_VERSION}", EXIT_PACKAGE)
    route = package_map.get("route")
    if route not in ROUTES:
        raise ExecutorError("package_invalid", f"unknown route: {route!r}", EXIT_PACKAGE)
    purpose = package_map.get("purpose")
    if purpose not in PURPOSES:
        raise ExecutorError("package_invalid", f"unknown purpose: {purpose!r}", EXIT_PACKAGE)
    input_mode = package_map.get("input_mode", "argv")
    if input_mode not in INPUT_MODES:
        raise ExecutorError("package_invalid", f"unknown input_mode: {input_mode!r}", EXIT_PACKAGE)

    expected = package_map.get("expected")
    if not isinstance(expected, dict):
        raise ExecutorError("package_invalid", "expected must be an object", EXIT_PACKAGE)
    for key in ("original_sha256", "candidate_sha256", "contract_sha256"):
        if key in expected and not HEX64.match(str(expected[key])):
            raise ExecutorError("package_invalid", f"expected.{key} must be 64 lowercase hex", EXIT_PACKAGE)

    paths: dict[str, Path] = {}
    for field in ("original", "contract", "tests", "candidate", "c_source",
                  "edit_manifest", "audit", "readelf"):
        raw = package_map.get(field)
        if raw is None:
            continue
        path = _safe_rel(package, str(raw), field=field)
        if field not in ("candidate", "c_source") and not path.exists():
            raise ExecutorError("package_invalid", f"{field} does not exist: {raw}", EXIT_PACKAGE)
        paths[field] = path

    for required in ("original", "contract", "tests"):
        if required not in paths:
            raise ExecutorError("package_invalid", f"{required} is required", EXIT_PACKAGE)
    if not paths["tests"].is_dir():
        raise ExecutorError("package_invalid", "tests must be a directory", EXIT_PACKAGE)
    if not (paths["tests"] / "valid.json").is_file():
        raise ExecutorError("package_invalid", "tests/valid.json is missing", EXIT_PACKAGE)

    if route == "route_b":
        if not package_map.get("func"):
            raise ExecutorError("package_invalid", "route_b requires func", EXIT_PACKAGE)
        mode = package_map.get("mode", "fixed" if purpose == "repair" else "roundtrip")
        if mode not in MODES:
            raise ExecutorError("package_invalid", f"unknown mode: {mode!r}", EXIT_PACKAGE)
        if "candidate" not in paths and "c_source" not in paths:
            raise ExecutorError("package_invalid", "route_b requires candidate or c_source", EXIT_PACKAGE)
    else:
        if "candidate" not in paths:
            raise ExecutorError("package_invalid", "route_a requires candidate", EXIT_PACKAGE)
        invalid_path = paths["tests"] / "invalid.json"
        if input_mode == "none":
            # No-input fixtures have no invalid case. An existing non-empty
            # invalid.json is a sentinel and is rejected rather than ignored.
            if invalid_path.is_file():
                try:
                    invalid_obj = read_json(invalid_path)
                except Exception as exc:  # noqa: BLE001
                    raise ExecutorError(
                        "package_invalid", f"invalid.json is unreadable: {exc}", EXIT_PACKAGE
                    ) from exc
                cases = invalid_obj.get("tests") if isinstance(invalid_obj, dict) else None
                if not isinstance(cases, list) or cases:
                    raise ExecutorError(
                        "package_invalid",
                        "route_a input_mode=none must not carry non-empty tests/invalid.json",
                        EXIT_PACKAGE,
                    )
        else:
            if not invalid_path.is_file():
                raise ExecutorError(
                    "package_invalid", "route_a requires tests/invalid.json", EXIT_PACKAGE
                )

    if "candidate" in paths and "candidate_sha256" not in expected:
        raise ExecutorError("package_invalid", "candidate requires expected.candidate_sha256", EXIT_PACKAGE)
    if "original_sha256" not in expected:
        raise ExecutorError("package_invalid", "expected.original_sha256 is required", EXIT_PACKAGE)

    sums = read_sums(package)
    files = []
    total = 0
    for current, dirs, names in os.walk(package):
        current_path = Path(current)
        for name in names:
            path = current_path / name
            rel = path.relative_to(package).as_posix()
            if rel == "SHA256SUMS":
                continue
            if path.is_symlink() or not path.is_file():
                raise ExecutorError("package_invalid", f"not a regular file: {rel}", EXIT_PACKAGE)
            size = path.stat().st_size
            total += size
            if size > MAX_FILE_BYTES:
                raise ExecutorError("package_invalid", f"file too large: {rel}", EXIT_PACKAGE)
            if total > MAX_TOTAL_BYTES:
                raise ExecutorError("package_invalid", "package exceeds the total size limit", EXIT_PACKAGE)
            files.append(rel)
    files.sort()

    missing = sorted(set(files) - set(sums))
    extra = sorted(set(sums) - set(files))
    if missing:
        raise ExecutorError("package_invalid", "SHA256SUMS omits: " + ", ".join(missing), EXIT_PACKAGE)
    if extra:
        raise ExecutorError("package_invalid", "SHA256SUMS lists missing files: " + ", ".join(extra), EXIT_PACKAGE)

    for rel in files:
        path = package / rel
        actual = sha256_file(path)
        if actual != sums[rel]:
            raise ExecutorError("package_invalid", f"hash mismatch: {rel}", EXIT_PACKAGE)

    original_hash = sha256_file(paths["original"])
    if original_hash != expected["original_sha256"]:
        raise ExecutorError("package_invalid", "original.elf does not match expected.original_sha256", EXIT_PACKAGE)
    contract_hash = sha256_file(paths["contract"])
    if "contract_sha256" in expected and contract_hash != expected["contract_sha256"]:
        raise ExecutorError("package_invalid", "contract does not match expected.contract_sha256", EXIT_PACKAGE)
    candidate_hash = None
    if "candidate" in paths:
        candidate_hash = sha256_file(paths["candidate"])
        if candidate_hash != expected["candidate_sha256"]:
            raise ExecutorError("package_invalid", "candidate does not match expected.candidate_sha256", EXIT_PACKAGE)

    package_map = dict(package_map)
    package_map.update({
        "paths": paths,
        "input_mode": input_mode,
        "expected": expected,
        "package_root": package,
        "verified_files": len(files),
        "sha256sums_sha256": sha256_file(package / "SHA256SUMS"),
        "original_sha256": original_hash,
        "contract_sha256": contract_hash,
        "candidate_sha256": candidate_hash,
    })
    return package_map


def account_problem(*, ack: bool, system: str, euid: int | None,
                    expected_uid: int) -> str | None:
    """Return a refusal reason, or None when the account is acceptable."""
    if not ack:
        return "guest_ack_missing"
    if system != "Linux":
        return f"not_linux:{system}"
    if euid is None:
        return "uid_unavailable"
    if euid == 0:
        return "root_forbidden"
    if euid != expected_uid:
        return f"uid_mismatch:{euid}:{expected_uid}"
    return None


JOBWRAP_ATTEST_DIR = Path("/run/binrepair/executor")
JOBWRAP_PATH = "/usr/local/sbin/jobwrap-executor"


def jobwrap_attestation(expected_uid: int, package: Path, out: Path, repo: Path
                        ) -> tuple[dict[str, Any] | None, str | None]:
    """Read and validate the wrapper's root-owned attestation.

    The environment variable alone is not evidence: runner can set it too.  The
    fixed wrapper creates this file as root, in a root-owned directory, for this
    pid.  A missing, stale, forged-shape or mismatched file is a refusal, not a
    pass.  The file is created by root before the drop and written after it, so
    the measured fields describe the sandbox that is about to run this process.
    """
    raw = os.environ.get("BINARYREPAIR_JOBWRAP")
    if not raw:
        return None, ("no jobwrap attestation "
                      "(use the fixed jobwrap mode; --allow-unattested is for "
                      "synthetic smoke tests only)")
    path = Path(raw)
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None, f"jobwrap attestation missing: {raw}"
    if resolved.parent != JOBWRAP_ATTEST_DIR:
        return None, f"jobwrap attestation outside {JOBWRAP_ATTEST_DIR}: {resolved}"
    try:
        st = resolved.stat()
    except OSError as exc:
        return None, f"cannot stat jobwrap attestation: {exc}"
    if not stat.S_ISREG(st.st_mode):
        return None, "jobwrap attestation is not a regular file"
    if st.st_uid != 0:
        return None, f"jobwrap attestation is not root-owned (uid={st.st_uid})"
    if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return None, "jobwrap attestation is group/other-writable"
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"cannot read jobwrap attestation: {exc}"
    if not isinstance(data, dict):
        return None, "jobwrap attestation is not an object"
    if data.get("pid") != os.getpid():
        return None, "jobwrap attestation is for a different pid"
    if data.get("uid") != expected_uid or data.get("euid") != expected_uid:
        return None, "jobwrap attestation uid does not match the executor account"
    if data.get("gid") != expected_uid or data.get("egid") != expected_uid:
        return None, "jobwrap attestation gid does not match the executor account"
    try:
        cap_eff = int(str(data.get("cap_eff", "")).strip(), 16)
    except ValueError:
        return None, "jobwrap attestation has an unreadable CapEff"
    if cap_eff != 0:
        return None, f"jobwrap attestation shows non-zero capabilities ({data.get('cap_eff')})"
    if data.get("no_new_privs") != 1:
        return None, "jobwrap attestation does not show NoNewPrivs=1"
    if data.get("seccomp") != 2:
        return None, "jobwrap attestation does not show a seccomp filter"
    netns = data.get("netns")
    host_netns = data.get("host_netns")
    if not netns or not host_netns:
        return None, "jobwrap attestation is missing netns identity"
    if netns == host_netns:
        return None, "jobwrap attestation does not show a separate netns"
    try:
        pid1_netns = os.readlink("/proc/1/ns/net")
    except OSError:
        pid1_netns = None
    if pid1_netns is not None and pid1_netns != host_netns:
        return None, "jobwrap host netns does not match PID 1's netns"
    if data.get("default_route"):
        return None, "jobwrap attestation shows a default route"
    if data.get("jobwrap") != JOBWRAP_PATH:
        return None, f"jobwrap attestation names unexpected wrapper: {data.get('jobwrap')}"
    if data.get("repo") != str(repo.resolve()):
        return None, "jobwrap attestation repo does not match --repo-root"
    if data.get("package") != str(package.resolve()):
        return None, "jobwrap attestation package does not match --package"
    if data.get("out") != str(out.resolve()):
        return None, "jobwrap attestation out does not match --out"
    return data, None


def _proc_status() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = Path("/proc/self/status").read_text(encoding="utf-8")
    except OSError:
        return values
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    return values


def isolation_attestation(expected_uid: int,
                          jobwrap: dict[str, Any] | None = None) -> dict[str, Any]:
    status = _proc_status()
    netns = None
    try:
        netns = os.readlink("/proc/self/ns/net")
    except OSError:
        netns = None
    if jobwrap is not None:
        claimed = ("wrapper-enforced uid 1003, no-egress netns, CapEff=0, "
                   "NoNewPrivs=1 and seccomp filter; values measured here")
        jobwrap_field = str(JOBWRAP_ATTEST_DIR / f"attest-{os.getpid()}.json")
    else:
        claimed = ("account only; capabilities/netns are recorded, not enforced "
                   "by this script")
        jobwrap_field = os.environ.get("BINARYREPAIR_JOBWRAP", "not_attested")
    return {
        "schema_version": 1,
        "account_guard": "passed",
        "expected_uid": expected_uid,
        "uid": os.getuid(),
        "euid": os.geteuid(),
        "gid": os.getgid(),
        "egid": os.getegid(),
        "groups": sorted(os.getgroups()),
        "platform": platform.system(),
        "kernel": platform.release(),
        "cap_eff": status.get("CapEff"),
        "no_new_privs": status.get("NoNewPrivs"),
        "seccomp": status.get("Seccomp"),
        "netns": netns,
        "jobwrap": jobwrap_field,
        "jobwrap_attested": jobwrap is not None,
        "jobwrap_pid": jobwrap.get("pid") if jobwrap else None,
        "jobwrap_path": jobwrap.get("jobwrap") if jobwrap else None,
        "claimed_scope": claimed,
    }


def _sanitized_env(out: Path) -> dict[str, str]:
    keep = ("PATH", "LANG", "LC_ALL", "PYTHONPATH", "PYTHONHOME", "JAVA_HOME", "GHIDRA_HOME")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.setdefault("PATH", "/usr/local/bin:/usr/bin:/bin")
    env["HOME"] = str(out / "home")
    env["TMPDIR"] = str(out / "tmp")
    return env


def _append_log(log: Path, text: str) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def _run(cmd: list[str], *, repo: Path, out: Path, log: Path,
         label: str) -> subprocess.CompletedProcess[bytes]:
    _append_log(log, f"$ {' '.join(cmd)}")
    (out / "logs").mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo),
            env=_sanitized_env(out),
            capture_output=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired as exc:
        _append_log(log, f"{label}: timed out after 900s")
        raise ExecutorError("step_timeout", f"{label} timed out", EXIT_STEP) from exc
    except OSError as exc:
        _append_log(log, f"{label}: {type(exc).__name__}: {exc}")
        raise ExecutorError("step_error", f"{label} could not start: {exc}", EXIT_STEP) from exc
    (out / "logs" / f"{label}.stdout").write_bytes(proc.stdout or b"")
    (out / "logs" / f"{label}.stderr").write_bytes(proc.stderr or b"")
    _append_log(log, f"{label}: rc={proc.returncode}")
    return proc


def _route_b_command(pkg: dict[str, Any], out: Path) -> list[str]:
    purpose = pkg["purpose"]
    mode = pkg.get("mode") or ("fixed" if purpose == "repair" else "roundtrip")
    run_manifest = pkg.get("run_manifest")
    if run_manifest is None:
        run_manifest = purpose == "repair"
    cmd = [
        sys.executable, "-m", "routeb.executor",
        "--original", str(pkg["paths"]["original"]),
        "--func", str(pkg["func"]),
        "--mode", mode,
        "--tests", str(pkg["paths"]["tests"]),
        "--out-dir", str(out),
        "--input-mode", pkg["input_mode"],
        "--contract", str(pkg["paths"]["contract"]),
    ]
    if "candidate" in pkg["paths"]:
        cmd += ["--candidate", str(pkg["paths"]["candidate"])]
    else:
        cmd += ["--c-source", str(pkg["paths"]["c_source"])]
    if run_manifest:
        cmd.append("--run-manifest")
    return cmd


def _route_a_prepare(pkg: dict[str, Any], out: Path) -> Path:
    """Stage canonical job files at the output root for the Route A scripts.

    ``workers/route_a/result_bundle.py`` writes evidence paths relative to the
    job or work directory.  Using the same root for both keeps every relative
    path inside ``out`` and therefore inside the final SHA256SUMS.
    """
    job = out
    shutil.copyfile(pkg["paths"]["original"], job / "original.elf")
    shutil.copyfile(pkg["paths"]["contract"], job / "contract.json")
    shutil.copytree(pkg["paths"]["tests"], job / "tests", dirs_exist_ok=True)
    if (pkg["package_root"] / "evidence").is_dir():
        shutil.copytree(pkg["package_root"] / "evidence", out / "evidence", dirs_exist_ok=True)
    return job


def _route_a_commands(pkg: dict[str, Any], out: Path, job: Path) -> list[list[str]]:
    route_out = out / "route_a"
    worker = [
        sys.executable, str(Path(__file__).resolve().parents[2] / "workers/route_a/worker.py"),
        "--job-dir", str(job),
        "--original", str(job / "original.elf"),
        "--contract", str(job / "contract.json"),
        "--tests-dir", str(job / "tests"),
        "--out", str(route_out),
        "--candidate", str(pkg["paths"]["candidate"]),
        "--expected-candidate", str(pkg["expected"]["candidate_sha256"]),
        "--job-id", str(pkg.get("job_id", "")),
    ]
    # Route A compares the canonical SecurityContract hash, not the file hash.
    # A package may pin that separately; the file hash was already checked.
    if "contract_canonical_sha256" in pkg["expected"]:
        worker += ["--expected-contract", str(pkg["expected"]["contract_canonical_sha256"])]
    # The worker accepts static evidence from the package, if present.
    for field, flag in (("edit_manifest", "--edit-manifest"),
                        ("audit", "--audit"),
                        ("readelf", "--readelf")):
        if field in pkg["paths"]:
            worker += [flag, str(pkg["paths"][field])]
    collector = [
        sys.executable, str(Path(__file__).resolve().parents[2] / "workers/route_a/result_bundle.py"),
        "--job-dir", str(job),
        "--work-dir", str(out),
        "--out", str(out / "result-bundle.json"),
        "--isolation", str(out / "isolation.json"),
        "--job-id", str(pkg.get("job_id", "")),
    ]
    return [worker, collector]


def _read_optional(out: Path, name: str) -> dict[str, Any] | None:
    path = out / name
    return read_json(path) if path.is_file() else None


def derive_route_b_gates(pkg: dict[str, Any], out: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Derive V0-V5 from Route B outputs without inventing a check."""
    manifest = _read_optional(out, "edit-manifest.json") or {}
    audit = _read_optional(out, "audit.json") or {}
    candidate = out / "candidate.elf"
    candidate_hash = sha256_file(candidate) if candidate.is_file() else None
    original_hash = sha256_file(out / "original.elf") if (out / "original.elf").is_file() else None

    v0_ok = (
        candidate_hash is not None
        and original_hash == pkg["expected"]["original_sha256"]
        and manifest.get("candidate_sha256") == candidate_hash
        and manifest.get("original_sha256") == original_hash
    )
    gates: dict[str, dict[str, Any]] = {
        "V0": {"status": "passed" if v0_ok else "failed",
               "artifacts": [name for name in ("original.elf", "candidate.elf") if (out / name).is_file()],
               "detail": "bundle hashes match the package" if v0_ok else "bundle identity mismatch"},
        "V1": {"status": "not_run", "artifacts": [], "detail": "static audit missing"},
        "V2": {"status": "not_run", "artifacts": [], "detail": "V2 has no guest-side gate; producer measurement stays an observation"},
        "V3": {"status": "not_run", "artifacts": [], "detail": "no runtime manifest"},
        "V4": {"status": "not_run", "artifacts": [], "detail": "V4 belongs to the independent verifier"},
        "V5": {"status": "not_run", "artifacts": [], "detail": "build-twice not measured"},
    }
    if (out / "audit.json").is_file():
        passed = audit.get("pass") is True
        gates["V1"] = {"status": "passed" if passed else "failed",
                       "artifacts": ["audit.json"], "detail": "static ELF audit"}
    if (out / "manifest-repaired.json").is_file():
        payload = _read_optional(out, "manifest-repaired.json") or {}
        passed = payload.get("repaired_pass") is True
        gates["V3"] = {"status": "passed" if passed else "failed",
                       "artifacts": ["manifest-repaired.json"],
                       "detail": f"repaired manifest {payload.get('passed')}/{payload.get('total')}"}
    elif (out / "manifest-compare.json").is_file():
        gates["V3"] = {"status": "not_run", "artifacts": ["manifest-compare.json"],
                       "detail": "round-trip comparison only; not repair V3"}
    if (out / "reproducibility.json").is_file():
        payload = _read_optional(out, "reproducibility.json") or {}
        if payload.get("state") == "measured":
            gates["V5"] = {"status": "passed" if payload.get("pass") is True else "failed",
                           "artifacts": ["reproducibility.json"], "detail": "build-twice"}
        else:
            gates["V5"] = {"status": "not_run", "artifacts": ["reproducibility.json"],
                           "detail": "build-twice not measured"}

    evidence: list[dict[str, Any]] = []
    for gate in GATES:
        for name in gates[gate]["artifacts"]:
            path = out / name
            if path.is_file():
                evidence.append({
                    "role": f"{gate.lower()}_evidence",
                    "relative_path": name,
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                })
    identity = {
        "original_sha256": original_hash,
        "original_size": (out / "original.elf").stat().st_size if (out / "original.elf").is_file() else None,
        "contract_sha256": pkg.get("contract_sha256"),
        "candidate_sha256": candidate_hash,
        "candidate_size": candidate.stat().st_size if candidate.is_file() else None,
    }
    return gates, evidence, identity


def _route_a_gates(out: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    bundle = _read_optional(out, "result-bundle.json")
    if bundle is None:
        raise ExecutorError("step_error", "Route A collector did not write result-bundle.json", EXIT_STEP)
    gates: dict[str, dict[str, Any]] = {}
    evidence: list[dict[str, Any]] = []
    for gate in GATES:
        raw = (bundle.get("gates") or {}).get(gate) or {}
        status = STATUS_MAP.get(str(raw.get("status", "not_run")), "unknown")
        artifacts = []
        for item in raw.get("evidence") or []:
            if isinstance(item, dict) and isinstance(item.get("relative_path"), str):
                rel = item["relative_path"]
                if (out / rel).is_file():
                    artifacts.append(rel)
        gates[gate] = {"status": status, "artifacts": sorted(set(artifacts)),
                       "detail": str((raw.get("details") or {}).get("note", ""))}
    for name in sorted({name for gate in gates.values() for name in gate["artifacts"]}):
        path = out / name
        evidence.append({
            "role": "route_a_evidence",
            "relative_path": name,
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        })
    return gates, evidence, bundle.get("identity") or {}


def _bundle_json(route: str, identity: dict[str, Any], gates: dict[str, Any],
                 out: Path) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "route": route,
        "candidate_sha256": identity.get("candidate_sha256"),
        "gates": {gate: {"status": gates[gate]["status"], "artifacts": gates[gate]["artifacts"]}
                  for gate in GATES},
    }
    comparison = out / "manifest-compare.json"
    if comparison.is_file():
        payload["comparison"] = "manifest-compare.json"
    return payload


def _legacy_result(route: str, pkg: dict[str, Any], identity: dict[str, Any],
                   gates: dict[str, Any], evidence: list[dict[str, Any]],
                   isolation: dict[str, Any]) -> dict[str, Any]:
    environment: dict[str, Any] = {"isolation": isolation, "purpose": pkg["purpose"]}
    env_path = pkg["package_root"] / "environment.json"
    if env_path.is_file():
        try:
            environment["tool_versions"] = read_json(env_path).get("tools", {})
        except ExecutorError:
            environment["tool_versions"] = "unreadable"
    return {
        "schema_version": 1,
        "job_id": pkg.get("job_id", ""),
        "route": "B" if route == "route_b" else "A",
        "purpose": pkg["purpose"],
        "generated_at": utc_now(),
        "identity": identity,
        "environment": environment,
        "gates": {gate: {"status": LEGACY_STATUS.get(gates[gate]["status"], "inconclusive"),
                         "details": {"note": gates[gate].get("detail", "")},
                         "evidence": [e for e in evidence
                                      if e["relative_path"] in gates[gate]["artifacts"]],
                         "missing": [] if gates[gate]["status"] != "not_run" else ["check not run"]}
                  for gate in GATES},
        "evidence": evidence,
        "limitations": [
            "No outcome is computed here; the acceptance engine owns the six labels.",
            "A missing or unmeasured check is not_run, never pass.",
            "V2 and V4 are never promoted by this executor.",
        ],
    }


def write_sums(out: Path) -> str:
    rows = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        rel = path.relative_to(out).as_posix()
        if rel in ("SHA256SUMS", "bundle-sha256.txt"):
            continue
        rows.append(f"{sha256_file(path)}  {rel}")
    text = "\n".join(rows) + "\n"
    (out / "SHA256SUMS").write_text(text, encoding="utf-8", newline="\n")
    digest = sha256_bytes(text.encode("utf-8"))
    (out / "bundle-sha256.txt").write_text(digest + "\n", encoding="utf-8", newline="\n")
    return digest


def write_error(out: Path, error: ExecutorError, *, package: Path | None = None) -> None:
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "run-error.json", {
        "schema_version": 1,
        "generated_at": utc_now(),
        "reason": error.reason,
        "message": error.message,
        "exit_code": error.exit_code,
        "package": str(package) if package else None,
    })


def run(package: Path, out: Path, *, expected_uid: int, repo: Path,
        jobwrap: dict[str, Any] | None = None) -> dict[str, Any]:
    pkg = verify_package(package)
    out = out.resolve()
    if out.exists() and not out.is_dir():
        raise ExecutorError("output_not_empty", f"output path is not a directory: {out}", EXIT_OUTPUT)
    if out.exists() and any(out.iterdir()):
        raise ExecutorError("output_not_empty", f"output directory is not empty: {out}", EXIT_OUTPUT)
    out.mkdir(parents=True, exist_ok=True)
    (out / "logs").mkdir(parents=True, exist_ok=True)
    (out / "home").mkdir(parents=True, exist_ok=True)
    (out / "tmp").mkdir(parents=True, exist_ok=True)
    log = out / "run.log"
    _append_log(log, f"guest executor {utc_now()}")
    _append_log(log, f"package: {pkg['package_root']}")
    _append_log(log, f"route: {pkg['route']} purpose: {pkg['purpose']}")

    isolation = isolation_attestation(expected_uid, jobwrap)
    write_json(out / "isolation.json", isolation)

    route = pkg["route"]
    if route == "route_b":
        cmd = _route_b_command(pkg, out)
        proc = _run(cmd, repo=repo, out=out, log=log, label="routeb-executor")
        if proc.returncode != 0:
            raise ExecutorError(
                "step_failed",
                f"routeb executor exited {proc.returncode}; see logs/routeb-executor.stderr",
                EXIT_STEP,
            )
        gates, evidence, identity = derive_route_b_gates(pkg, out)
    else:
        job = _route_a_prepare(pkg, out)
        commands = _route_a_commands(pkg, out, job)
        for index, cmd in enumerate(commands, 1):
            proc = _run(cmd, repo=repo, out=out, log=log, label=f"routea-step-{index}")
            if proc.returncode != 0:
                raise ExecutorError(
                    "step_failed",
                    f"route A step {index} exited {proc.returncode}; see logs/routea-step-{index}.stderr",
                    EXIT_STEP,
                )
        gates, evidence, identity = _route_a_gates(out)

    bundle = _bundle_json(route, identity, gates, out)
    result = _legacy_result(route, pkg, identity, gates, evidence, isolation)
    write_json(out / "bundle.json", bundle)
    write_json(out / "result-bundle.json", result)
    _append_log(log, "wrote bundle.json and result-bundle.json")
    # Keep run.log byte-stable: writing the digest into it after SHA256SUMS
    # would invalidate the manifest that covers it.
    digest = write_sums(out)
    return {
        "ok": True,
        "route": route,
        "purpose": pkg["purpose"],
        "out": str(out),
        "bundle_sha256": digest,
        "gates": {gate: gates[gate]["status"] for gate in GATES},
        "verified_files": pkg["verified_files"],
        "isolation": isolation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guest executor for one staged package")
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--guest-ack", action="store_true",
                        help="confirm this runs inside the disposable Linux guest")
    parser.add_argument("--plan-only", action="store_true",
                        help="verify the package and print the plan; run nothing")
    parser.add_argument("--allow-unattested", action="store_true",
                        help="synthetic smoke tests only; never use for a real candidate")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)

    euid = os.geteuid() if hasattr(os, "geteuid") else None
    problem = account_problem(ack=args.guest_ack, system=platform.system(),
                              euid=euid, expected_uid=DEFAULT_EXPECTED_UID)
    if problem is not None:
        print(f"guest_executor: refusing: {problem}", file=sys.stderr)
        return EXIT_REFUSED
    jobwrap = None
    if not args.plan_only and not args.allow_unattested:
        jobwrap, problem = jobwrap_attestation(
            DEFAULT_EXPECTED_UID, args.package, args.out, args.repo_root)
        if problem is not None:
            print(f"guest_executor: refusing: {problem}", file=sys.stderr)
            return EXIT_REFUSED
    if not args.plan_only and args.allow_unattested:
        # The bypass may not execute a manifest. It exists for synthetic
        # route-A materialisation and static screening, not for a real repair.
        try:
            probe = read_json(args.package / "package.json")
        except ExecutorError:
            probe = {}
        wants_manifest = bool(probe.get("run_manifest",
                                        probe.get("purpose") == "repair"))
        if probe.get("route") == "route_b" and wants_manifest:
            print("guest_executor: refusing: --allow-unattested may not execute a "
                  "route_b manifest; use the fixed jobwrap mode",
                  file=sys.stderr)
            return EXIT_REFUSED

    try:
        if args.plan_only:
            pkg = verify_package(args.package)
            plan = {
                "ok": True,
                "plan_only": True,
                "route": pkg["route"],
                "purpose": pkg["purpose"],
                "verified_files": pkg["verified_files"],
                "sha256sums_sha256": pkg["sha256sums_sha256"],
                "steps": ([_route_b_command(pkg, args.out)] if pkg["route"] == "route_b"
                          else ["route_a worker.py", "route_a result_bundle.py"]),
            }
            print(json.dumps(plan, indent=2))
            return EXIT_OK
        result = run(args.package, args.out, expected_uid=DEFAULT_EXPECTED_UID,
                     repo=args.repo_root.resolve(), jobwrap=jobwrap)
        print(json.dumps(result, indent=2))
        return EXIT_OK
    except ExecutorError as exc:
        try:
            write_error(args.out, exc, package=args.package)
        except OSError:
            pass
        print(json.dumps({"ok": False, "reason": exc.reason, "message": exc.message},
                         indent=2), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
