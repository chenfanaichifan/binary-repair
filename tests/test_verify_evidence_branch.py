"""Tests for scripts/verify_evidence_branch.py (real temporary git repos)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_evidence_branch as evidence  # noqa: E402

REQUIRED = ("gate.json", "freeze.json", "README.md", "SHA256SUMS")
GATE_DIR = "artifacts/release-gate-2026-11-15"
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_AUTHOR_DATE": "2026-11-15T00:00:00Z",
    "GIT_COMMITTER_DATE": "2026-11-15T00:00:00Z",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=GIT_ENV, timeout=60,
    )
    assert completed.returncode == 0, (
        f"git {' '.join(args)} failed: {completed.stderr or completed.stdout}"
    )
    return completed.stdout.strip()


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_evidence(
    repo: Path,
    gated: str,
    *,
    gate_override: dict | None = None,
    freeze_override: dict | None = None,
    skip: tuple[str, ...] = (),
    tamper_after_sums: bool = False,
    extra_files: dict[str, str] | None = None,
) -> str:
    gate_dir = repo / GATE_DIR
    gate_dir.mkdir(parents=True, exist_ok=True)
    gate = {"ok": True, "frozen_sha": gated, "release_sha": gated}
    if gate_override:
        gate.update(gate_override)
    freeze = {
        "kind": "release_freeze",
        "requested_sha": gated,
        "head_sha": gated,
        "gate_summary": {"frozen_sha": gated, "release_sha": gated},
    }
    if freeze_override:
        freeze.update(freeze_override)
    (gate_dir / "gate.json").write_text(json.dumps(gate, indent=2) + "\n", encoding="utf-8")
    (gate_dir / "freeze.json").write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
    (gate_dir / "README.md").write_text("# evidence\n", encoding="utf-8")
    sums = []
    for name in ("gate.json", "freeze.json", "README.md"):
        if name in skip:
            continue
        sums.append(f"{_sha256((gate_dir / name).read_bytes())}  {name}")
    (gate_dir / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    for name in skip:
        path = gate_dir / name
        if path.is_file():
            path.unlink()
    for relative, content in (extra_files or {}).items():
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    if tamper_after_sums:
        (gate_dir / "README.md").write_text("# evidence tampered\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "evidence")
    return _git(repo, "rev-parse", "HEAD")


def _repo_with_evidence(tmp_path: Path, **kwargs) -> tuple[Path, str, str]:
    repo, gated = _init_repo(tmp_path)
    _git(repo, "checkout", "-b", "evidence-branch")
    evidence_sha = _write_evidence(repo, gated, **kwargs)
    _git(repo, "checkout", "main")
    (repo / "mainline.txt").write_text("advanced\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "mainline advances")
    return repo, gated, evidence_sha


def test_valid_evidence_branch_passes(tmp_path: Path) -> None:
    repo, gated, evidence_sha = _repo_with_evidence(tmp_path)
    payload = evidence.evaluate(
        gated_sha=gated, evidence_ref="evidence-branch", mainline_ref="main", root=repo
    )
    assert payload["ok"] is True, payload["checks"]
    assert payload["gated_sha"] == gated
    assert payload["evidence_sha"] == evidence_sha
    assert all(check["status"] == "passed" for check in payload["checks"])
    assert set(payload) >= {"ok", "gated_sha", "evidence_sha", "changed_paths", "checks"}


def test_allowed_changed_paths_pass(tmp_path: Path) -> None:
    repo, gated, _evidence_sha = _repo_with_evidence(
        tmp_path,
        extra_files={
            "docs/release-notes-2026-11-15.md": "notes\n",
            "docs/acceptance/ci-notes-2026-11-15.md": "ci\n",
            "docs/status/claims.json": "{}\n",
        },
    )
    payload = evidence.evaluate(
        gated_sha=gated, evidence_ref="evidence-branch", mainline_ref="main", root=repo
    )
    assert payload["ok"] is True, payload["checks"]
    assert any(path.startswith("docs/release-") for path in payload["changed_paths"])
    assert "docs/status/claims.json" in payload["changed_paths"]


def test_gated_not_ancestor_fails(tmp_path: Path) -> None:
    repo, gated = _init_repo(tmp_path)
    _git(repo, "checkout", "--orphan", "unrelated")
    (repo / "other.txt").write_text("other\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "unrelated root")
    _git(repo, "checkout", "main")
    _git(repo, "checkout", "-b", "evidence-branch")
    _write_evidence(repo, gated)
    payload = evidence.evaluate(
        gated_sha=gated, evidence_ref="evidence-branch", mainline_ref="unrelated", root=repo
    )
    assert payload["ok"] is False
    by_id = {check["id"]: check for check in payload["checks"]}
    assert by_id["gated-is-ancestor"]["status"] == "failed"


def test_missing_required_file_fails(tmp_path: Path) -> None:
    repo, gated, _ = _repo_with_evidence(tmp_path, skip=("freeze.json",))
    payload = evidence.evaluate(
        gated_sha=gated, evidence_ref="evidence-branch", mainline_ref="main", root=repo
    )
    assert payload["ok"] is False
    by_id = {check["id"]: check for check in payload["checks"]}
    assert by_id["evidence-files"]["status"] == "failed"
    assert "missing" in by_id["evidence-files"]["detail"]


def test_tampered_sums_fail(tmp_path: Path) -> None:
    repo, gated, _ = _repo_with_evidence(tmp_path, tamper_after_sums=True)
    payload = evidence.evaluate(
        gated_sha=gated, evidence_ref="evidence-branch", mainline_ref="main", root=repo
    )
    assert payload["ok"] is False
    by_id = {check["id"]: check for check in payload["checks"]}
    assert by_id["sha256sums"]["status"] == "failed"
    assert "README.md" in by_id["sha256sums"]["detail"]


def test_gate_json_sha_mismatch_fails(tmp_path: Path) -> None:
    repo, gated, _ = _repo_with_evidence(
        tmp_path, gate_override={"frozen_sha": "f" * 40, "release_sha": "f" * 40}
    )
    payload = evidence.evaluate(
        gated_sha=gated, evidence_ref="evidence-branch", mainline_ref="main", root=repo
    )
    assert payload["ok"] is False
    by_id = {check["id"]: check for check in payload["checks"]}
    assert by_id["gate-json-sha"]["status"] == "failed"


def test_freeze_json_sha_mismatch_fails(tmp_path: Path) -> None:
    repo, gated, _ = _repo_with_evidence(
        tmp_path,
        freeze_override={"requested_sha": "f" * 40, "head_sha": "f" * 40},
    )
    payload = evidence.evaluate(
        gated_sha=gated, evidence_ref="evidence-branch", mainline_ref="main", root=repo
    )
    assert payload["ok"] is False
    by_id = {check["id"]: check for check in payload["checks"]}
    assert by_id["freeze-json-sha"]["status"] == "failed"


def test_disallowed_changed_path_fails(tmp_path: Path) -> None:
    repo, gated, _ = _repo_with_evidence(
        tmp_path, extra_files={"app/main.py": "# unexpected change\n"}
    )
    payload = evidence.evaluate(
        gated_sha=gated, evidence_ref="evidence-branch", mainline_ref="main", root=repo
    )
    assert payload["ok"] is False
    by_id = {check["id"]: check for check in payload["checks"]}
    assert by_id["changed-paths"]["status"] == "failed"
    assert "app/main.py" in by_id["changed-paths"]["detail"]


def test_missing_evidence_ref_fails(tmp_path: Path) -> None:
    repo, gated = _init_repo(tmp_path)
    payload = evidence.evaluate(
        gated_sha=gated, evidence_ref="does-not-exist", mainline_ref="main", root=repo
    )
    assert payload["ok"] is False
    by_id = {check["id"]: check for check in payload["checks"]}
    assert by_id["evidence-tip"]["status"] == "failed"
    assert "evidence tip unresolved" in by_id["sha256sums"]["detail"]


def test_unknown_gated_sha_fails(tmp_path: Path) -> None:
    repo, _gated = _init_repo(tmp_path)
    payload = evidence.evaluate(
        gated_sha="0" * 40, evidence_ref="main", mainline_ref="main", root=repo
    )
    assert payload["ok"] is False
    assert payload["gated_sha"] is None
    assert payload["checks"][0]["id"] == "gated-sha-resolves"
    assert payload["checks"][0]["status"] == "failed"


def test_short_gated_sha_is_resolved(tmp_path: Path) -> None:
    repo, gated, _ = _repo_with_evidence(tmp_path)
    payload = evidence.evaluate(
        gated_sha=gated[:12], evidence_ref="evidence-branch", mainline_ref="main", root=repo
    )
    assert payload["ok"] is True, payload["checks"]
    assert payload["gated_sha"] == gated


def test_json_cli_and_human_cli(tmp_path: Path, capsys) -> None:
    repo, gated, _ = _repo_with_evidence(tmp_path)
    code = evidence.main([
        "--gated-sha", gated, "--evidence-ref", "evidence-branch",
        "--mainline-ref", "main", "--json", "--root", str(repo),
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["checks"]

    code = evidence.main([
        "--gated-sha", gated, "--evidence-ref", "does-not-exist",
        "--mainline-ref", "main", "--root", str(repo),
    ])
    assert code == 1
    assert "verify-evidence-branch: FAIL" in capsys.readouterr().out


def test_parse_sums_reports_malformed_lines() -> None:
    entries, errors = evidence.parse_sums("not-a-hash  gate.json\n" + "a" * 64 + "  README.md\n")
    assert ("a" * 64, "README.md") in entries
    assert any("invalid digest" in error for error in errors)


def test_path_allowed_rules() -> None:
    assert evidence.path_allowed("artifacts/release-gate-2026-11-15/gate.json")
    assert evidence.path_allowed("docs/release-notes-2026-11-15.md")
    assert evidence.path_allowed("docs/acceptance/ci-notes.md")
    assert evidence.path_allowed("docs/status/claims.json")
    assert not evidence.path_allowed("app/main.py")
    assert not evidence.path_allowed("scripts/release_gate.py")
