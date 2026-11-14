"""Tests for the release provenance validator (no network, no real gate run)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_provenance.py"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _sha(data)


def _evidence(tmp_path: Path, *, mode: str = "release") -> dict:
    artifacts = {}
    for relative in (
        "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json",
        "artifacts/coverage-closure-2026-11-14/acceptance.json",
        "artifacts/provider-matrix-2026-11-14/summary.json",
        "docs/status/claims.json",
    ):
        digest = _write(tmp_path / relative, relative.encode())
        artifacts[relative] = {"present": True, "sha256": digest}
    fixtures = {
        "fixtures/poc/marcx-capacity.json": {
            "present": True,
            "sha256": _write(tmp_path / "fixtures/poc/marcx-capacity.json", b"poc"),
        }
    }
    acceptance = {
        "available": True,
        "cases": {
            "marcx_pipeline_with_manifest": {
                "fixture_sha256": "a" * 64,
                "candidate_sha256": "b" * 64,
                "disposition": "verified_patch",
            },
            "heap_pipeline_with_manifest": {
                "fixture_sha256": "c" * 64,
                "candidate_sha256": "d" * 64,
                "disposition": "verified_patch",
            },
            "heap_target_scoped": {
                "fixture_sha256": "e" * 64,
                "candidate_sha256": "f" * 64,
                "target_scope": {"name": "heap_bad", "va": 1, "end": 2},
            },
        },
    }
    guest = {
        "available": True,
        "limactl_version": "limactl version 2.3.0",
        "config_sha256": "1" * 64,
        "guest_uname": "Linux x86_64",
        "qemu_version": "QEMU emulator version 8.2.0",
    }
    builder = {"kind": "local-frozen-tree", "python": "3.11", "platform": "t",
               "machine": "arm64", "kernel": "x", "github": None}
    if mode == "nightly":
        builder["kind"] = "local-frozen-tree"
    provenance = {
        "schema_version": 1,
        "subject": {
            "frozen_sha": "a" * 40,
            "release_sha": "a" * 40,
            "tree_sha": "b" * 40,
            "branch": "workbench-v3",
            "clean_tree": True,
        },
        "materials": {
            "artifacts": artifacts,
            "fixtures": fixtures,
            "acceptance_subjects": acceptance,
            "claims_sha256": artifacts["docs/status/claims.json"]["sha256"],
            "non_goals_doc": {"path": "docs/acceptance/x.md", "sha256": None,
                              "present": False},
        },
        "builder": builder,
        "guest": guest,
        "invocation": {"argv": ["release_gate.py"], "cwd": str(tmp_path),
                       "mode": mode, "release_sha": "a" * 40},
        "not_run": ["github_actions"],
    }
    return {
        "schema_version": 1,
        "kind": "release_gate_evidence",
        "mode": mode,
        "ok": True,
        "frozen_sha": "a" * 40,
        "release_sha": "a" * 40,
        "tree_sha": "b" * 40,
        "clean_tree": True,
        "checks": [],
        "violations": [],
        "provenance": provenance,
    }


def _run(tmp_path: Path, evidence: dict, *extra: str) -> subprocess.CompletedProcess:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--evidence", str(path),
         "--root", str(tmp_path), *extra],
        capture_output=True, text=True, timeout=60,
    )


def test_valid_provenance_passes(tmp_path: Path) -> None:
    result = _run(tmp_path, _evidence(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_valid_nightly_requires_guest(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path, mode="nightly")
    assert _run(tmp_path, evidence).returncode == 0
    evidence["provenance"]["guest"] = {"available": False}
    result = _run(tmp_path, evidence)
    assert result.returncode == 1
    assert "guest is unavailable for a nightly gate" in result.stdout


def test_artifact_digest_tamper_fails(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    relative = "artifacts/coverage-closure-2026-11-14/acceptance.json"
    (tmp_path / relative).write_bytes(b"tampered")
    result = _run(tmp_path, evidence)
    assert result.returncode == 1
    assert "digest mismatch" in result.stdout


def test_missing_provenance_fails(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    evidence["provenance"] = {}
    result = _run(tmp_path, evidence)
    assert result.returncode == 1
    assert "provenance block is missing" in result.stdout


def test_github_builder_requires_run_id(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    evidence["provenance"]["builder"]["kind"] = "github-actions"
    evidence["provenance"]["builder"]["github"] = {"workflow": "CI"}
    result = _run(tmp_path, evidence)
    assert result.returncode == 1
    assert "github.run_id" in result.stdout


def test_frozen_release_mismatch_fails(tmp_path: Path) -> None:
    evidence = _evidence(tmp_path)
    evidence["provenance"]["subject"]["frozen_sha"] = "c" * 40
    result = _run(tmp_path, evidence)
    assert result.returncode == 1
    assert "frozen_sha != release_sha" in result.stdout


def test_json_output_and_bad_input(tmp_path: Path) -> None:
    result = _run(tmp_path, _evidence(tmp_path), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["checks"]["acceptance_cases"] >= 3
    bad = subprocess.run(
        [sys.executable, str(SCRIPT), "--evidence", str(tmp_path / "missing.json")],
        capture_output=True, text=True, timeout=60,
    )
    assert bad.returncode == 2
