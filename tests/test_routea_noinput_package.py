"""Route A no-input package: invalid.json is absent, not sentinel."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from workers.executor import run_job
from workers.route_a import worker


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/public/CWE416_Use_After_Free__malloc_free_char_01_noinput"
ROUTE_A = Path(__file__).resolve().parents[1] / "delivery/p1-routea-kit-2026-11-07"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package(tmp_path: Path, *, invalid: dict | None = None) -> Path:
    root = tmp_path / "pkg"
    (root / "tests").mkdir(parents=True)
    shutil.copyfile(FIXTURE / "original.elf", root / "original.elf")
    shutil.copyfile(FIXTURE / "contract.json", root / "contract.json")
    shutil.copyfile(FIXTURE / "tests/valid.json", root / "tests/valid.json")
    shutil.copyfile(ROUTE_A / "candidate.elf", root / "candidate.elf")
    if invalid is not None:
        (root / "tests/invalid.json").write_text(json.dumps(invalid), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "job_id": "routea-noinput",
        "route": "route_a",
        "purpose": "repair",
        "input_mode": "none",
        "original": "original.elf",
        "contract": "contract.json",
        "tests": "tests",
        "candidate": "candidate.elf",
        "expected": {
            "original_sha256": _sha(root / "original.elf"),
            "candidate_sha256": _sha(root / "candidate.elf"),
            "contract_sha256": _sha(root / "contract.json"),
        },
    }
    (root / "package.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    files = sorted(p for p in root.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (root / "SHA256SUMS").write_text(
        "\n".join(f"{_sha(p)}  {p.relative_to(root).as_posix()}" for p in files) + "\n",
        encoding="utf-8",
    )
    return root


def test_noinput_routea_package_without_invalid_is_accepted(tmp_path: Path) -> None:
    package = _package(tmp_path)
    verified = run_job.verify_package(package, check_permissions=False)
    assert verified["route"] == "route_a"
    assert verified["input_mode"] == "none"


def test_noinput_routea_rejects_nonempty_invalid_sentinel(tmp_path: Path) -> None:
    package = _package(tmp_path, invalid={"tests": [{"id": "sentinel"}]})
    with pytest.raises(run_job.ExecutorError) as exc:
        run_job.verify_package(package, check_permissions=False)
    assert exc.value.reason == "package_invalid"
    assert "non-empty" in exc.value.message


def test_argv_routea_still_requires_invalid(tmp_path: Path) -> None:
    package = _package(tmp_path)
    manifest = json.loads((package / "package.json").read_text(encoding="utf-8"))
    manifest["input_mode"] = "argv"
    (package / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    files = sorted(p for p in package.rglob("*") if p.is_file() and p.name != "SHA256SUMS")
    (package / "SHA256SUMS").write_text(
        "\n".join(f"{_sha(p)}  {p.relative_to(package).as_posix()}" for p in files) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(run_job.ExecutorError) as exc:
        run_job.verify_package(package, check_permissions=False)
    assert "invalid.json" in exc.value.message


def test_worker_manifest_set_none_has_only_valid(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    shutil.copyfile(FIXTURE / "tests/valid.json", tests / "valid.json")
    digest, valid_hash, invalid_hash = worker.manifest_set_hash(str(tests), "none")
    assert len(digest) == 64
    assert valid_hash == _sha(tests / "valid.json")
    assert invalid_hash is None


def test_result_bundle_none_does_not_hash_missing_invalid(tmp_path: Path) -> None:
    package = _package(tmp_path)
    work = tmp_path / "work"
    (work / "route_a").mkdir(parents=True)
    shutil.copyfile(package / "candidate.elf", work / "route_a/candidate.elf")
    contract = json.loads((package / "contract.json").read_text(encoding="utf-8"))
    from workers.route_a.result_bundle import canonical_json_hash
    set_hash, _, _ = worker.manifest_set_hash(str(package / "tests"), "none")
    status = {
        "candidate": {"sha256": _sha(package / "candidate.elf")},
        "contract_sha256": canonical_json_hash(contract),
        "manifest_set_sha256": set_hash,
        "artifacts": [],
        "tool_versions": {},
    }
    (work / "route_a/status.json").write_text(json.dumps(status), encoding="utf-8")
    out = work / "result-bundle.json"
    from workers.route_a import result_bundle
    rc = result_bundle.main([
        "--job-dir", str(package),
        "--work-dir", str(work),
        "--out", str(out),
    ])
    assert rc == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["identity"]["invalid_sha256"] is None
    assert not any(e.get("role") == "invalid_manifest" for e in payload["evidence"])
    assert payload["gates"]["V0"]["status"] == "pass"
