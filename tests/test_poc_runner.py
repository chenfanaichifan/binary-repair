"""Native/guest PoC and regression execution evidence."""
from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import platform
import sys
import threading
from pathlib import Path

import pytest

from app.services import guest_coordinator, poc_runner
from app.services.binary_pipeline import repair_any
from app.services.guest_runner import GuestResult, GuestRunner, find_guest_runner
from app.services.poc_runner import load_manifest, parse_strace_errors, run_poc
from app.services.runtime import capabilities

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"
MANIFEST = ROOT / "fixtures" / "poc" / "elf-x86_64-strcpy.json"
LINUX_X64 = sys.platform.startswith("linux") and platform.machine() in {"x86_64", "amd64"}
_RUNNER = find_guest_runner("x86_64")
LIMA = _RUNNER is not None and _RUNNER.kind == "lima"


@pytest.fixture(autouse=True)
def _isolate_capability_cache():
    """Keep the measured capability cache out of other tests' monkeypatching."""

    capabilities.clear_cache()
    yield
    capabilities.clear_cache()


@pytest.fixture(autouse=True)
def _isolate_guest_lock(tmp_path: Path, monkeypatch):
    """Hermetic Lima guest lock for every test (no writes to the real $HOME)."""

    monkeypatch.setattr(guest_coordinator, "_STATES", {})
    guest_coordinator.clear_attempt_history()
    monkeypatch.setenv(guest_coordinator.LOCK_ENV, str(tmp_path / "lima-guest.lock"))
    monkeypatch.setenv(guest_coordinator.TIMEOUT_ENV, "60")
    yield
    guest_coordinator.clear_attempt_history()


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _files_manifest(original: bytes) -> dict:
    """A schema_version 1 manifest using per-case staged files and {tmp}."""

    return {
        "schema_version": 1,
        "fixture_sha256": hashlib.sha256(original).hexdigest(),
        "format": "elf",
        "arch": "x86_64",
        "target": "fixture",
        "poc": [
            {
                "id": "poc-file",
                "argv": ["{tmp}/poc.marc"],
                "files": [{"name": "poc.marc", "base64": _b64(b"archive-bytes")}],
                "original": {"crashed": True},
                "candidate": {
                    "crashed": False,
                    "exit_code": 1,
                    "stderr_contains": "rejected",
                },
            }
        ],
        "regression": [
            {
                "id": "reg-file",
                "argv": ["{tmp}/input.txt"],
                "files": [{"name": "input.txt", "base64": _b64(b"input-bytes")}],
                "original": {"exit_code": 0, "stdout": "ok\n"},
                "candidate": {"exit_code": 0, "stdout": "ok\n"},
            }
        ],
    }


def _plain_manifest(original: bytes) -> dict:
    """A v1 manifest without staged files (historical layout)."""

    return {
        "schema_version": 1,
        "fixture_sha256": hashlib.sha256(original).hexdigest(),
        "format": "elf",
        "arch": "x86_64",
        "target": "fixture",
        "poc": [
            {
                "id": "poc-plain",
                "argv": ["crash"],
                "original": {"crashed": True},
                "candidate": {"crashed": False, "exit_code": 1},
            }
        ],
        "regression": [
            {
                "id": "reg-plain",
                "argv": ["ok"],
                "original": {"exit_code": 0, "stdout": "ok\n"},
                "candidate": {"exit_code": 0, "stdout": "ok\n"},
            }
        ],
    }


def _install_fake_runner(
    monkeypatch, runner: GuestRunner, calls: list[dict], *, original: bytes, candidate: bytes,
) -> str:
    """Replace runner selection/execution with an in-process recorder."""

    name = "native" if runner.kind == "native" else Path(runner.tool).name
    monkeypatch.setattr(poc_runner, "find_guest_runner", lambda arch: runner)

    def fake_run_path(path, argv, *, arch="x86_64", stdin=b"", timeout=10.0,
                      runner=None, cwd=None, lock_timeout=None,
                      lock_purpose=None):  # noqa: ANN001
        binary = Path(path)
        binary_bytes = binary.read_bytes()
        calls.append(
            {
                "binary": binary.name,
                "binary_path": binary,
                "binary_bytes": binary_bytes,
                "binary_mode": binary.stat().st_mode & 0o777,
                "argv": list(argv),
                "arch": arch,
                "stdin": stdin,
                "cwd": Path(cwd),
                "cwd_files": {
                    item.name: item.read_bytes()
                    for item in Path(cwd).iterdir()
                    if item.is_file()
                },
            }
        )
        is_original = binary_bytes == original
        first = argv[0] if argv else ""
        if first == "crash" or first.endswith("poc.marc"):
            if is_original:
                return GuestResult(
                    True, exit_code=139,
                    stderr=b"qemu: uncaught target signal 11 (Segmentation fault)",
                    crashed=True, runner=name, tier=runner.tier,
                )
            return GuestResult(
                True, exit_code=1, stderr=b"rejected", crashed=False,
                runner=name, tier=runner.tier,
            )
        return GuestResult(True, exit_code=0, stdout=b"ok\n", crashed=False,
                           runner=name, tier=runner.tier)

    monkeypatch.setattr(poc_runner, "run_path", fake_run_path)
    return name


def test_manifest_validation_and_hash_binding():
    data = load_manifest(MANIFEST)
    assert data["format"] == "elf"
    assert data["arch"] == "x86_64"
    assert data["poc"] and data["regression"]
    with pytest.raises(ValueError):
        load_manifest({"schema_version": 1})


def test_poc_runner_is_explicit_when_unavailable_or_wrong_hash(tmp_path: Path):
    manifest = json.loads(MANIFEST.read_text())
    original = b"not the fixture"
    evidence = run_poc(original, original, manifest)
    assert evidence.status == "fail"
    assert any("fixture_sha256" in item for item in evidence.limitations)


def test_manifest_files_staged_and_tmp_substituted(monkeypatch):
    calls: list[dict] = []
    original, candidate = b"ORIGINAL-BINARY", b"CANDIDATE-BINARY"
    _install_fake_runner(
        monkeypatch, GuestRunner("native", "", "native_run"), calls,
        original=original, candidate=candidate,
    )
    evidence = run_poc(original, candidate, _files_manifest(original))

    assert evidence.status == "pass"
    assert evidence.runner == "native"
    assert evidence.tier == "native_run"
    payload = evidence.to_dict()
    assert {"status", "runner", "tier", "poc", "regression", "limitations"} <= set(payload)
    assert payload["tier"] == "native_run"
    case_keys = {
        "case_id", "kind", "executable", "exit_code", "crashed", "stdout",
        "stderr", "expected_ok", "error", "timed_out",
    }
    for group in ("poc", "regression"):
        assert payload[group], group
        for case in payload[group]:
            assert case_keys <= set(case), (group, case)

    assert len(calls) == 4
    poc_original, poc_candidate, reg_original, reg_candidate = calls
    # Both sides of the differential are staged at the *same* path so argv[0]
    # dependent output stays comparable.
    assert {item["binary"] for item in calls} == {"target"}
    assert poc_original["binary_path"] == poc_candidate["binary_path"]
    assert poc_original["binary_path"].parent == poc_original["cwd"]
    # {tmp} is replaced by the staged directory path, identically for both sides
    assert "{tmp}" not in poc_original["argv"][0]
    assert poc_original["argv"][0] == poc_candidate["argv"][0]
    assert Path(poc_original["argv"][0]).name == "poc.marc"
    # staged files were present while the case executed
    assert poc_original["cwd_files"]["poc.marc"] == b"archive-bytes"
    assert reg_original["cwd_files"]["input.txt"] == b"input-bytes"
    assert not Path(poc_original["argv"][0]).exists()
    # binaries are staged byte-exact and executable at the shared path
    assert poc_original["binary_bytes"] == original
    assert poc_candidate["binary_bytes"] == candidate
    assert poc_original["binary_mode"] == 0o700
    assert poc_candidate["binary_mode"] == 0o700
    # case directories are separate per group/case and cleaned up afterwards
    assert poc_original["cwd"] != reg_original["cwd"]
    assert poc_original["cwd"].name.startswith("case-poc-")
    assert reg_original["cwd"].name.startswith("case-regression-")
    assert not poc_original["cwd"].parent.exists()

    original_cases = [case for case in evidence.cases if case.executable == "original"]
    candidate_cases = [case for case in evidence.cases if case.executable == "candidate"]
    assert original_cases[0].crashed is True
    assert "Segmentation fault" in original_cases[0].stderr
    assert candidate_cases[0].exit_code == 1
    assert "rejected" in candidate_cases[0].stderr
    assert original_cases[0].expected_ok is True
    assert candidate_cases[0].expected_ok is True


def test_v1_manifest_without_files_still_works(monkeypatch):
    calls: list[dict] = []
    original, candidate = b"ORIGINAL-BINARY", b"CANDIDATE"
    _install_fake_runner(
        monkeypatch, GuestRunner("native", "", "native_run"), calls,
        original=original, candidate=candidate,
    )
    evidence = run_poc(original, candidate, _plain_manifest(original))
    assert evidence.status == "pass"
    assert [item["argv"] for item in calls] == [["crash"], ["crash"], ["ok"], ["ok"]]
    # no manifest files: the case directory only holds the staged executable
    assert all(set(item["cwd_files"]) == {"target"} for item in calls)


def test_lima_staging_lives_under_configured_dir(monkeypatch, tmp_path: Path):
    calls: list[dict] = []
    runner = GuestRunner("lima", "/fake/limactl", "emulated_run", "binaryrepair")
    original, candidate = b"ORIGINAL-BINARY", b"CANDIDATE-BINARY"
    _install_fake_runner(monkeypatch, runner, calls, original=original, candidate=candidate)
    stage_base = tmp_path / "guest-stage"
    monkeypatch.setenv(poc_runner.STAGE_ENV, str(stage_base))
    evidence = run_poc(original, candidate, _files_manifest(original))

    assert evidence.status == "pass"
    assert evidence.runner == "limactl"
    assert evidence.tier == "emulated_run"
    case_dir = calls[0]["cwd"]
    assert stage_base in case_dir.parents
    assert case_dir.name.startswith("case-poc-")
    assert calls[0]["cwd_files"]["poc.marc"] == b"archive-bytes"
    # the executable is staged inside the guest-visible case directory
    assert calls[0]["binary_path"] == case_dir / "target"
    assert calls[0]["binary_mode"] == 0o700
    assert stage_base.exists()
    assert not case_dir.parent.exists()  # the unique staged root was removed
    # The outer run_poc lease records attempt evidence even without a real guest.
    assert evidence.lock_attempts
    assert evidence.lock_attempts[0]["purpose"] == "poc_runner.run_poc"
    assert evidence.lock_attempts[0]["instance"] == "binaryrepair"
    assert evidence.lock_attempts[0]["acquired"] is True
    assert evidence.lock_attempts[0]["released"] is True
    assert evidence.lock_blocked is False


def test_runner_unavailable_is_reported_not_faked(monkeypatch):
    original = FIXTURE.read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    monkeypatch.setattr(poc_runner, "find_guest_runner", lambda arch: None)

    def _must_not_execute(*args, **kwargs):  # noqa: ANN001
        raise AssertionError("PoC must not execute without a runner")

    monkeypatch.setattr(poc_runner, "run_path", _must_not_execute)
    evidence = run_poc(original, original, manifest)
    assert evidence.status == "unavailable"
    assert evidence.runner == "" and evidence.tier == ""
    assert evidence.cases == [] and evidence.regression == []
    assert any("runner" in item for item in evidence.limitations)


def test_manifest_rejects_unsafe_staged_file_names():
    manifest = _files_manifest(b"x")
    manifest["poc"][0]["files"][0]["name"] = "../escape"
    with pytest.raises(ValueError):
        load_manifest(manifest)
    evidence = run_poc(b"x", b"y", manifest)
    assert evidence.status == "fail"
    assert any("invalid PoC manifest" in item for item in evidence.limitations)


def test_manifest_rejects_invalid_base64():
    manifest = _files_manifest(b"x")
    manifest["poc"][0]["files"][0]["base64"] = "!!!!not-base64!!!!"
    with pytest.raises(ValueError):
        load_manifest(manifest)


@pytest.mark.skipif(not LINUX_X64, reason="native ELF x86-64 PoC requires Linux x86-64")
def test_real_poc_and_regression_pass_for_verified_candidate():
    original = FIXTURE.read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    outcome = repair_any(
        original, poc_manifest=manifest, allow_whole_image=True,
    )
    assert outcome.verified is True, outcome.report.to_dict()
    assert outcome.report.poc["status"] == "pass"
    assert outcome.report.poc["stdout_signature"] == "matched"
    checks = {
        check["id"]: check["status"]
        for check in outcome.report.verification["packet"]["checks"]
    }
    assert checks["poc.native.available"] == "passed"
    assert checks["poc.native.original_failure"] == "passed"
    assert checks["poc.native.candidate_pass"] == "passed"
    assert checks["poc.native.regression"] == "passed"
    assert checks["poc.native.stdout_signature"] == "passed"


@pytest.mark.skipif(not LINUX_X64, reason="native ELF x86-64 PoC requires Linux x86-64")
def test_noop_candidate_fails_poc_gate():
    original = FIXTURE.read_bytes()
    manifest = json.loads(MANIFEST.read_text())
    # Candidate identical to the vulnerable original: PoC original expectation
    # passes, but the candidate must also fail, so the gate rejects.
    evidence = run_poc(original, original, manifest)
    assert evidence.status == "fail"


@pytest.mark.skipif(not LIMA, reason="running Lima guest runner is required")
def test_lima_runner_executes_poc_manifest_in_guest():
    original = FIXTURE.read_bytes()
    manifest = {
        "schema_version": 1,
        "fixture_sha256": hashlib.sha256(original).hexdigest(),
        "format": "elf",
        "arch": "x86_64",
        "target": "vuln_copy",
        "poc": [
            {
                "id": "overflow-64",
                "argv": ["A" * 64],
                "original": {"crashed": True},
                "candidate": {"crashed": False, "exit_code": 0},
            }
        ],
        "regression": [
            {
                "id": "short-hi",
                "argv": ["hi"],
                "original": {"exit_code": 0, "stdout": "hi\n"},
                "candidate": {"exit_code": 0, "stdout": "hi\n"},
            }
        ],
    }
    evidence = run_poc(original, original, manifest, timeout=60)
    assert evidence.runner == Path(_RUNNER.tool).name
    assert evidence.tier == "emulated_run"
    original_poc = [case for case in evidence.cases if case.executable == "original"]
    assert original_poc and all(case.crashed for case in original_poc)
    assert all(
        "Segmentation fault" in case.stderr or "target signal" in case.stderr
        for case in original_poc
    )
    # candidate == vulnerable original must never pass the PoC differential
    assert evidence.status == "fail"
    assert all(case.exit_code == 0 for case in evidence.regression)
    assert all(case.stdout == "hi\n" for case in evidence.regression)


# ---------------------------------------------------------------------------
# Declared no-input model (UAF-style manifests with an empty regression list)
# ---------------------------------------------------------------------------

def _no_input_manifest(original: bytes, *, declared: bool) -> dict:
    manifest = _plain_manifest(original)
    manifest["regression"] = []
    if declared:
        manifest["no_input"] = True
    return manifest


def test_manifest_no_input_must_be_boolean():
    original = b"ORIGINAL"
    manifest = _no_input_manifest(original, declared=True)
    manifest["no_input"] = "yes"
    with pytest.raises(ValueError):
        load_manifest(manifest)
    data = load_manifest(_no_input_manifest(original, declared=True))
    assert data["no_input"] is True


def test_no_input_declaration_is_recorded_in_the_evidence(monkeypatch):
    calls: list[dict] = []
    original, candidate = b"ORIGINAL-BINARY", b"CANDIDATE-BINARY"
    _install_fake_runner(
        monkeypatch, GuestRunner("native", "", "native_run"), calls,
        original=original, candidate=candidate,
    )
    evidence = run_poc(original, candidate, _no_input_manifest(original, declared=True))
    assert evidence.status == "pass"
    assert evidence.no_input is True
    assert evidence.stdout_signature == "not_applicable"
    payload = evidence.to_dict()
    assert payload["no_input"] is True
    assert payload["stdout_signature"] == "not_applicable"
    assert payload["regression"] == []
    # Only the PoC differential ran; the declared model has no regression cases.
    assert len(calls) == 2


def test_undeclared_empty_regression_is_still_allowed_by_the_runner(monkeypatch):
    calls: list[dict] = []
    original, candidate = b"ORIGINAL-BINARY", b"CANDIDATE-BINARY"
    _install_fake_runner(
        monkeypatch, GuestRunner("native", "", "native_run"), calls,
        original=original, candidate=candidate,
    )
    evidence = run_poc(
        original, candidate, _no_input_manifest(original, declared=False),
    )
    # The runner records the honest evidence; the gate is what fails the
    # undeclared empty regression (poc.native.regression stays failed).
    assert evidence.status == "pass"
    assert evidence.no_input is False
    assert evidence.to_dict()["no_input"] is False
    assert evidence.to_dict()["regression"] == []


def test_errno_strace_parser_and_manifest_opt_in():
    text = """123 write(2, "x", 1) = 1
124 openat(AT_FDCWD, "missing", O_RDONLY) = -1 ENOENT (No such file or directory)
125 close(3) = -1 EBADF (Bad file descriptor)
126 exit_group(1) = ?
"""
    assert parse_strace_errors(text) == ["EBADF", "ENOENT"]
    manifest = json.loads(MANIFEST.read_text())
    manifest["errno_probe"] = "strace"
    assert load_manifest(manifest)["errno_probe"] == "strace"
    manifest["errno_probe"] = "ptrace"
    with pytest.raises(ValueError, match="errno_probe"):
        load_manifest(manifest)




@pytest.mark.skipif(not LINUX_X64, reason="LD_PRELOAD errno probe requires native Linux x86-64")
def test_ld_preload_errno_probe_captures_process_exit_errno():
    fixed = ROOT / "artifacts" / "paradigm-a-cwe121-2026-11-14" / "fixed.elf"
    if not fixed.is_file():
        pytest.skip("CWE121 fixed artifact missing")
    original = (ROOT / "fixtures" / "public" / "CWE121_src_char_declare_cpy_51b" / "original.elf").read_bytes()
    manifest = json.loads((ROOT / "fixtures" / "poc" / "cwe121.json").read_text())
    manifest["errno_probe"] = "ld_preload"
    evidence = run_poc(original, fixed.read_bytes(), manifest)
    assert evidence.status == "pass"
    assert evidence.errno_probe == "ld_preload"
    assert evidence.errno_signature == "matched"
    assert all(case.errno_value is not None for case in evidence.regression)


# ------------------------------------------------- Lima guest-lock integration


class _LockHolder:
    """Hold the Lima guest lock in a daemon thread (foreign-thread contention)."""

    def __init__(self, purpose: str = "test-holder"):
        self.purpose = purpose
        self.ready = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        lease = guest_coordinator.acquire_lima_guest_lock(
            purpose=self.purpose, instance="binaryrepair", timeout=10,
        )
        self.ready.set()
        self._stop.wait(60)
        lease.release()

    def __enter__(self):
        self._thread.start()
        assert self.ready.wait(15), "lock holder did not start"
        return self

    def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
        self._stop.set()
        self._thread.join(timeout=15)
        return False


def _fake_lima_runner() -> GuestRunner:
    return GuestRunner(
        kind="lima", tool="/fake/limactl", tier="emulated_run",
        instance="binaryrepair",
    )


def test_lima_lock_timeout_blocks_run_poc_without_execution(monkeypatch):
    original = b"ORIGINAL-BINARY"
    manifest = _plain_manifest(original)
    calls: list[object] = []

    def _must_not_execute(*args, **kwargs):  # noqa: ANN001
        calls.append(args)
        raise AssertionError("run_poc must not execute on a lock timeout")

    monkeypatch.setattr(poc_runner, "_select_runner", lambda fmt, arch: _fake_lima_runner())
    monkeypatch.setattr(poc_runner, "run_path", _must_not_execute)
    with _LockHolder():
        evidence = run_poc(original, b"CANDIDATE", manifest, lock_timeout=0.2)

    assert calls == []
    assert evidence.status == "unavailable"
    assert evidence.lock_blocked is True
    assert evidence.cases == [] and evidence.regression == []
    assert evidence.lock_attempts
    assert any(record["timeout"] for record in evidence.lock_attempts)
    assert any(
        "guest lock timeout" in item and "not executed" in item
        for item in evidence.limitations
    )


def test_lima_lock_unavailable_blocks_run_poc_without_execution(
    tmp_path: Path, monkeypatch,
):
    original = b"ORIGINAL-BINARY"
    manifest = _plain_manifest(original)
    calls: list[object] = []

    def _must_not_execute(*args, **kwargs):  # noqa: ANN001
        calls.append(args)
        raise AssertionError("run_poc must not execute when the lock is unusable")

    monkeypatch.setattr(poc_runner, "_select_runner", lambda fmt, arch: _fake_lima_runner())
    monkeypatch.setattr(poc_runner, "run_path", _must_not_execute)
    monkeypatch.setenv(
        guest_coordinator.LOCK_ENV,
        str(tmp_path / "missing-parent" / "lima.lock"),
    )
    evidence = run_poc(original, b"CANDIDATE", manifest)

    assert calls == []
    assert evidence.status == "unavailable"
    assert evidence.lock_blocked is True
    assert any(
        "guest lock unavailable" in item for item in evidence.limitations
    )


def test_lima_lock_attempts_recorded_on_success(monkeypatch):
    original = b"ORIGINAL-BINARY"
    manifest = _plain_manifest(original)
    run_kwargs: list[dict] = []

    def fake_run_path(path, argv, **kwargs):  # noqa: ANN001, ANN003
        run_kwargs.append(dict(kwargs))
        purpose = kwargs.get("lock_purpose", "")
        is_original = purpose.endswith("original")
        if argv and argv[0] == "crash":  # the PoC case
            if is_original:
                return GuestResult(
                    True, exit_code=139,
                    stderr=b"qemu: uncaught target signal 11",
                    crashed=True, runner="limactl", tier="emulated_run",
                )
            return GuestResult(
                True, exit_code=1, crashed=False,
                runner="limactl", tier="emulated_run",
            )
        return GuestResult(
            True, exit_code=0, stdout=b"ok\n", crashed=False,
            runner="limactl", tier="emulated_run",
        )

    monkeypatch.setattr(poc_runner, "_select_runner", lambda fmt, arch: _fake_lima_runner())
    monkeypatch.setattr(poc_runner, "run_path", fake_run_path)
    evidence = run_poc(original, b"CANDIDATE", manifest)

    assert evidence.status == "pass"
    assert evidence.lock_blocked is False
    assert evidence.lock_attempts
    outer = [
        record for record in evidence.lock_attempts
        if record["purpose"] == "poc_runner.run_poc"
    ]
    assert len(outer) == 1
    assert outer[0]["acquired"] is True and outer[0]["released"] is True
    assert outer[0]["instance"] == "binaryrepair"
    assert outer[0]["limactl"]["tool"] == "/fake/limactl"
    # Lima lock kwargs are forwarded to the per-case execution only for Lima.
    assert run_kwargs
    assert all(
        kwargs["lock_purpose"].startswith("poc_runner.run_path:")
        for kwargs in run_kwargs
    )
    assert all("lock_timeout" not in kwargs for kwargs in run_kwargs)


def test_native_poc_run_has_no_lock_attempts(monkeypatch):
    calls: list[dict] = []
    runner = GuestRunner(kind="native", tool="", tier="native_run")
    _install_fake_runner(
        monkeypatch, runner, calls,
        original=b"ORIGINAL-BINARY", candidate=b"CANDIDATE",
    )
    original = b"ORIGINAL-BINARY"
    evidence = run_poc(original, b"CANDIDATE", _plain_manifest(original))
    assert evidence.status == "pass"
    assert evidence.lock_attempts == []
    assert evidence.lock_blocked is False


def _foreign_acquire_times_out(timeout: float) -> bool:
    outcome: dict[str, bool] = {}

    def worker() -> None:
        try:
            lease = guest_coordinator.acquire_lima_guest_lock(
                purpose="foreign-check", instance="binaryrepair", timeout=timeout,
            )
            lease.release()
        except guest_coordinator.GuestLockTimeout:
            outcome["timeout"] = True

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=10)
    return bool(outcome.get("timeout"))


def test_lima_lock_is_held_while_staging(monkeypatch):
    original = b"ORIGINAL-BINARY"
    manifest = _plain_manifest(original)
    observations: dict[str, object] = {}
    real_staging_root = poc_runner._staging_root

    @contextlib.contextmanager
    def spy_staging_root(runner):  # noqa: ANN001
        with real_staging_root(runner) as root:
            observations["lock_held_during_staging"] = _foreign_acquire_times_out(0.15)
            yield root

    monkeypatch.setattr(poc_runner, "_staging_root", spy_staging_root)
    monkeypatch.setattr(
        poc_runner, "_select_runner", lambda fmt, arch: _fake_lima_runner(),
    )
    monkeypatch.setattr(
        poc_runner, "run_path",
        lambda *args, **kwargs: GuestResult(
            True, exit_code=0, stdout=b"ok\n", runner="limactl",
            tier="emulated_run",
        ),
    )
    evidence = run_poc(original, original, manifest)
    assert observations["lock_held_during_staging"] is True
    assert evidence.lock_attempts


def test_lima_lock_released_after_staging_failure(monkeypatch):
    original = b"ORIGINAL-BINARY"
    manifest = _plain_manifest(original)
    monkeypatch.setattr(
        poc_runner, "_select_runner", lambda fmt, arch: _fake_lima_runner(),
    )

    def failing_staging_root(runner):  # noqa: ANN001
        raise OSError("staging directory unavailable")

    monkeypatch.setattr(poc_runner, "_staging_root", failing_staging_root)
    evidence = run_poc(original, b"CANDIDATE", manifest)
    assert evidence.status == "fail"
    assert any("staging failed" in item for item in evidence.limitations)
    # The lease must not leak: an immediate foreign acquisition succeeds.
    lease = guest_coordinator.acquire_lima_guest_lock(
        purpose="after-failure", instance="binaryrepair", timeout=1,
    )
    lease.release()
