"""Tests for the release freeze wrapper (mocked subprocess, no network).

The wrapper ensures the gated tree is the published frozen SHA, runs the release
gate with ``--release-sha``, re-checks origin/mainline afterwards and writes a
reviewable evidence bundle.  These tests inject a fake runner so they never
touch git remotes, Lima or the real gate.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

spec = importlib.util.spec_from_file_location(
    "release_freeze", SCRIPTS / "release_freeze.py"
)
assert spec and spec.loader
release_freeze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_freeze)

SHA = "a" * 40
TREE = "b" * 40


def _runner(
    *,
    head: str = SHA,
    dirty: list[str] | None = None,
    mainline_start: str | None = SHA,
    mainline_end: str | None = None,
    gate_rc: int = 0,
    gate_ok: bool = True,
    gate_frozen: str | None = None,
    gate_stdout: str | None = None,
    state: dict | None = None,
):
    state = state if state is not None else {}
    state["fetches"] = 0
    state["gate_calls"] = 0

    def run(argv, cwd, timeout):
        argv = [str(part) for part in argv]
        joined = " ".join(argv)
        if argv and argv[0] == "git":
            sub = argv[1:]
            if sub[:2] == ["rev-parse", "HEAD"]:
                return release_freeze.RunResult(0, head + "\n")
            if sub[:1] == ["status"]:
                return release_freeze.RunResult(
                    0, "".join(line + "\n" for line in (dirty or []))
                )
            if sub[:2] == ["rev-parse", "HEAD^{tree}"]:
                return release_freeze.RunResult(0, TREE + "\n")
            if sub[:2] == ["rev-parse", "--abbrev-ref"]:
                return release_freeze.RunResult(0, "release/2026-11-14\n")
            if sub[:1] == ["fetch"]:
                state["fetches"] += 1
                return release_freeze.RunResult(0, "")
            if sub[:2] == ["rev-parse", "origin/workbench-v3"]:
                if state["fetches"] >= 2 and mainline_end is not None:
                    return release_freeze.RunResult(0, mainline_end + "\n")
                return release_freeze.RunResult(
                    0, (mainline_start or "") + "\n"
                )
            return release_freeze.RunResult(1, "", f"unexpected git: {sub}")
        if "release_gate.py" in joined:
            state["gate_calls"] += 1
            if "--evidence-out" in argv:
                out = Path(argv[argv.index("--evidence-out") + 1])
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps({"kind": "release_gate_evidence"}),
                               encoding="utf-8")
            payload = gate_stdout
            if payload is None:
                payload = json.dumps({
                    "ok": gate_ok,
                    "mode": "nightly",
                    "frozen_sha": gate_frozen or head,
                    "release_sha": gate_frozen or head,
                    "branch": "release/2026-11-14",
                    "clean_tree": True,
                    "status_counts": {"passed": 11, "failed": 0,
                                      "unavailable": 0, "skipped": 0},
                    "violations": [] if gate_ok else ["boom"],
                    "not_run": ["github_actions"],
                    "tree_sha": TREE,
                })
            return release_freeze.RunResult(gate_rc, payload, "")
        return release_freeze.RunResult(0, "", "")

    return run


def _freeze(tmp_path: Path, **kwargs):
    evidence = tmp_path / "evidence"
    return release_freeze.freeze(
        sha=kwargs.pop("sha", SHA),
        evidence_dir=evidence,
        expected_mainline=kwargs.pop("expected_mainline", "require"),
        offline=kwargs.pop("offline", False),
        overwrite=kwargs.pop("overwrite", False),
        root=tmp_path,
        run=kwargs.pop("run"),
    ), evidence


def test_freeze_success_writes_verified_bundle(tmp_path: Path) -> None:
    payload, evidence = _freeze(tmp_path, run=_runner())
    assert payload["ok"] is True
    assert payload["head_sha"] == SHA
    assert payload["tree_sha"] == TREE
    assert payload["mainline_unchanged"] is True
    assert payload["gate_rc"] == 0
    for name in ("gate.json", "freeze.json", "README.md", "SHA256SUMS"):
        assert (evidence / name).is_file(), name
    lines = (evidence / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    assert any("freeze.json" in line for line in lines)
    import hashlib
    for line in lines:
        digest, name = line.split(None, 1)
        actual = hashlib.sha256((evidence / name.strip()).read_bytes()).hexdigest()
        assert digest == actual
    assert json.loads((evidence / "freeze.json").read_text())["kind"] == "release_freeze"


def test_freeze_rejects_dirty_tree(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="dirty"):
        _freeze(tmp_path, run=_runner(dirty=[" M app/main.py"]))


def test_freeze_rejects_head_sha_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not match"):
        _freeze(tmp_path, sha="c" * 40, run=_runner())


def test_freeze_requires_mainline_match(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="origin/workbench-v3 does not match"):
        _freeze(tmp_path, run=_runner(mainline_start="d" * 40))


def test_freeze_fails_when_mainline_advances_during_gate(tmp_path: Path) -> None:
    payload, evidence = _freeze(
        tmp_path, run=_runner(mainline_end="e" * 40)
    )
    assert payload["ok"] is False
    assert payload["mainline_unchanged"] is False
    assert json.loads((evidence / "freeze.json").read_text())["ok"] is False


def test_freeze_fails_when_gate_fails_but_writes_evidence(tmp_path: Path) -> None:
    payload, evidence = _freeze(tmp_path, run=_runner(gate_rc=1, gate_ok=False))
    assert payload["ok"] is False
    assert payload["gate_rc"] == 1
    assert (evidence / "gate.json").is_file()
    assert (evidence / "freeze.json").is_file()


def test_freeze_offline_ignore_skips_mainline_checks(tmp_path: Path) -> None:
    payload, _ = _freeze(
        tmp_path, run=_runner(), offline=True, expected_mainline="ignore"
    )
    assert payload["ok"] is True
    assert payload["mainline_sha_start"] is None
    assert payload["mainline_unchanged"] is True


def test_freeze_refuses_non_empty_evidence_dir(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "old.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        release_freeze.freeze(
            sha=SHA, evidence_dir=evidence, root=tmp_path, run=_runner()
        )
    payload = release_freeze.freeze(
        sha=SHA, evidence_dir=evidence, root=tmp_path, run=_runner(),
        overwrite=True,
    )
    assert payload["ok"] is True


def test_freeze_records_ci_mode_without_claiming_ci_run(tmp_path: Path) -> None:
    payload, evidence = _freeze(
        tmp_path, run=_runner(mainline_start=None), offline=True,
        expected_mainline="ignore",
    )
    freeze = json.loads((evidence / "freeze.json").read_text())
    assert freeze["gate_summary"]["not_run"] == ["github_actions"]
    assert "not a GitHub Actions run" in freeze["evidence_scope"]
    assert payload["ok"] is True
