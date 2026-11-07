#!/usr/bin/env python3
"""Host-safe self-test for the guest executor.

Nothing here executes a binary.  The tests cover the parts that must be right
before the guest window: package hashes, path/symlink rejection, the uid guard,
and the V0-V5 derivation from already-written evidence.

Run on any host:

    python workers/executor/self_test.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import run_job as rj  # noqa: E402


def _write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8", newline="\n")
    else:
        path.write_bytes(data)


def _sums(root: Path) -> None:
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name != "SHA256SUMS"):
        rows.append(f"{rj.sha256_file(path)}  {path.relative_to(root).as_posix()}")
    (root / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")


def make_package(root: Path, *, route: str = "route_b", purpose: str = "repair") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    original = b"\x7fELF-original-dummy\n"
    candidate = b"\x7fELF-candidate-dummy\n"
    contract = '{"schema_version": 3}\n'
    _write(root / "original.elf", original)
    _write(root / "candidate.elf", candidate)
    _write(root / "contract.json", contract)
    _write(root / "tests/valid.json", '{"schema_version": 1, "tests": [{"id": "valid"}]}\n')
    if route == "route_a":
        _write(root / "tests/invalid.json", '{"schema_version": 1, "tests": []}\n')
    manifest = {
        "schema_version": 1,
        "job_id": "job-self-test",
        "route": route,
        "purpose": purpose,
        "input_mode": "none",
        "original": "original.elf",
        "contract": "contract.json",
        "tests": "tests",
        "candidate": "candidate.elf",
        "expected": {
            "original_sha256": rj.sha256_bytes(original),
            "candidate_sha256": rj.sha256_bytes(candidate),
            "contract_sha256": rj.sha256_bytes(contract.encode()),
        },
    }
    if route == "route_b":
        manifest["func"] = "badSink"
        manifest["mode"] = "fixed"
        manifest["run_manifest"] = True
    _write(root / "package.json", json.dumps(manifest, indent=2) + "\n")
    _sums(root)
    return root


def test_account_guard() -> None:
    assert rj.account_problem(ack=False, system="Linux", euid=1003, expected_uid=1003) == "guest_ack_missing"
    assert rj.account_problem(ack=True, system="Windows", euid=1003, expected_uid=1003) == "not_linux:Windows"
    assert rj.account_problem(ack=True, system="Linux", euid=0, expected_uid=1003) == "root_forbidden"
    assert rj.account_problem(ack=True, system="Linux", euid=1000, expected_uid=1003) == "uid_mismatch:1000:1003"
    assert rj.account_problem(ack=True, system="Linux", euid=1003, expected_uid=1003) is None


def test_package_verification() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = make_package(Path(tmp) / "pkg")
        pkg = rj.verify_package(root)
        assert pkg["route"] == "route_b"
        assert pkg["verified_files"] == 5
        assert pkg["original_sha256"] == pkg["expected"]["original_sha256"]


def test_tamper_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = make_package(Path(tmp) / "pkg")
        with (root / "candidate.elf").open("ab") as handle:
            handle.write(b"x")
        try:
            rj.verify_package(root)
        except rj.ExecutorError as exc:
            assert exc.reason == "package_invalid"
        else:
            raise AssertionError("tampered package was accepted")


def test_unlisted_file_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = make_package(Path(tmp) / "pkg")
        _write(root / "extra.txt", "not in sums\n")
        try:
            rj.verify_package(root)
        except rj.ExecutorError as exc:
            assert "omits" in exc.message
        else:
            raise AssertionError("unlisted file was accepted")


def test_traversal_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = make_package(Path(tmp) / "pkg")
        manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
        manifest["original"] = "../outside.elf"
        _write(root / "package.json", json.dumps(manifest, indent=2) + "\n")
        _sums(root)
        try:
            rj.verify_package(root)
        except rj.ExecutorError as exc:
            assert "safe relative" in exc.message or "escapes" in exc.message
        else:
            raise AssertionError("traversal path was accepted")


def test_symlink_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = make_package(Path(tmp) / "pkg")
        target = root / "candidate.elf"
        link = root / "linked.elf"
        try:
            os.symlink(target.name, link)
        except (OSError, NotImplementedError):
            return  # Windows without developer mode; the package guard is unchanged
        try:
            rj.verify_package(root)
        except rj.ExecutorError as exc:
            assert "symlink" in exc.message
        else:
            raise AssertionError("symlink was accepted")


def test_route_b_gates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = make_package(Path(tmp) / "pkg")
        pkg = rj.verify_package(root)
        out = Path(tmp) / "out"
        out.mkdir()
        _write(out / "original.elf", (root / "original.elf").read_bytes())
        _write(out / "candidate.elf", (root / "candidate.elf").read_bytes())
        manifest = {
            "original_sha256": pkg["original_sha256"],
            "candidate_sha256": pkg["candidate_sha256"],
        }
        _write(out / "edit-manifest.json", json.dumps(manifest))
        _write(out / "audit.json", json.dumps({"pass": True}))
        _write(out / "manifest-repaired.json", json.dumps({"repaired_pass": True, "passed": 1, "total": 1}))
        _write(out / "reproducibility.json", json.dumps({"state": "measured", "pass": True}))
        gates, evidence, identity = rj.derive_route_b_gates(pkg, out)
        assert gates["V0"]["status"] == "passed"
        assert gates["V1"]["status"] == "passed"
        assert gates["V2"]["status"] == "not_run"
        assert gates["V3"]["status"] == "passed"
        assert gates["V4"]["status"] == "not_run"
        assert gates["V5"]["status"] == "passed"
        assert evidence and identity["candidate_sha256"] == pkg["candidate_sha256"]

        (out / "manifest-repaired.json").unlink()
        _write(out / "manifest-compare.json", json.dumps({"valid": "1/1"}))
        gates, _, _ = rj.derive_route_b_gates(pkg, out)
        assert gates["V3"]["status"] == "not_run"


def test_route_a_gates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        _write(out / "candidate.elf", b"candidate\n")
        result = {
            "gates": {
                "V0": {"status": "pass", "artifacts": ["candidate.elf"],
                       "evidence": [{"relative_path": "candidate.elf"}]},
                "V1": {"status": "pass", "artifacts": ["audit.json"],
                       "evidence": [{"relative_path": "audit.json"}]},
            },
            "identity": {"candidate_sha256": rj.sha256_file(out / "candidate.elf")},
        }
        _write(out / "audit.json", "{}\n")
        _write(out / "result-bundle.json", json.dumps(result))
        gates, evidence, identity = rj._route_a_gates(out)
        assert gates["V0"]["status"] == "passed"
        assert gates["V1"]["status"] == "passed"
        assert gates["V3"]["status"] == "not_run"
        assert identity["candidate_sha256"] == result["identity"]["candidate_sha256"]
        assert evidence


def test_sums_are_sorted_and_complete() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "out"
        out.mkdir()
        _write(out / "b.txt", "b\n")
        _write(out / "a.txt", "a\n")
        digest = rj.write_sums(out)
        lines = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        assert [line.split("  ", 1)[1] for line in lines] == ["a.txt", "b.txt"]
        assert digest == rj.sha256_bytes((out / "SHA256SUMS").read_bytes())


def main() -> int:
    tests = [
        ("account guard", test_account_guard),
        ("package verification", test_package_verification),
        ("tamper rejected", test_tamper_rejected),
        ("unlisted file rejected", test_unlisted_file_rejected),
        ("traversal rejected", test_traversal_rejected),
        ("symlink rejected", test_symlink_rejected),
        ("route B gate derivation", test_route_b_gates),
        ("route A gate derivation", test_route_a_gates),
        ("sums sorted and complete", test_sums_are_sorted_and_complete),
    ]
    failures = 0
    for name, test in tests:
        try:
            test()
        except Exception:  # noqa: BLE001
            failures += 1
            print(f"FAIL {name}")
            traceback.print_exc()
        else:
            print(f"PASS {name}")
    print(f"guest executor self-test: {len(tests) - failures}/{len(tests)} passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
