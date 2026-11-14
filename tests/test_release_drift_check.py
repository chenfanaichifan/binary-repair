"""Tests for scripts/release_drift_check.py (mock git subprocess runner)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import release_drift_check as drift  # noqa: E402

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
TAG = "release-2026-11-15"
EVIDENCE = "release/2026-11-15-evidence"


class FakeGit:
    """Deterministic read-only git replacement."""

    def __init__(
        self,
        *,
        refs: dict[str, str],
        counts: dict[tuple[str, str], int] | None = None,
        files: dict[str, list[str]] | None = None,
        blobs: dict[tuple[str, str], str] | None = None,
        fetch_rc: int = 0,
    ) -> None:
        self.refs = refs
        self.counts = counts or {}
        self.files = files or {}
        self.blobs = blobs or {}
        self.fetch_rc = fetch_rc
        self.calls: list[list[str]] = []

    def __call__(self, command, cwd, timeout):
        args = [str(part) for part in command]
        if args and args[0] == "git":
            args = args[1:]
        self.calls.append(args)
        if args[:1] == ["fetch"]:
            return drift.CommandResult(self.fetch_rc, "", "" if not self.fetch_rc else "fetch failed")
        if args[:2] == ["rev-parse", "--verify"]:
            ref = args[2].removesuffix("^{commit}")
            if ref in self.refs:
                return drift.CommandResult(0, self.refs[ref] + "\n")
            return drift.CommandResult(128, "", f"fatal: bad revision {ref}")
        if args[:2] == ["rev-list", "--count"]:
            start, end = args[2].split("..", 1)
            return drift.CommandResult(0, f"{self.counts.get((start, end), 0)}\n")
        if args[:3] == ["ls-tree", "-r", "--name-only"]:
            paths = self.files.get(args[3], [])
            return drift.CommandResult(0, "".join(f"{path}\n" for path in paths))
        if args[:1] == ["show"]:
            spec = args[1]
            sha, _, path = spec.partition(":")
            blob = self.blobs.get((sha, path))
            if blob is None:
                return drift.CommandResult(128, "", f"missing {spec}")
            return drift.CommandResult(0, blob)
        return drift.CommandResult(1, "", f"unexpected git args: {args}")


def _gate_blob(gated: str) -> str:
    return json.dumps({"ok": True, "frozen_sha": gated, "release_sha": gated})


def _clean_fake() -> FakeGit:
    return FakeGit(
        refs={TAG: SHA_A, "origin/workbench-v3": SHA_A, EVIDENCE: "e" * 40},
        counts={(SHA_A, SHA_A): 0},
        files={"e" * 40: [f"artifacts/release-gate-2026-11-15/gate.json"]},
        blobs={("e" * 40, "artifacts/release-gate-2026-11-15/gate.json"): _gate_blob(SHA_A)},
    )


def test_clean_release_is_ok_and_reports_contract_fields(tmp_path: Path) -> None:
    payload = drift.evaluate(
        tag=TAG, offline=True, root=tmp_path, run=_clean_fake()
    )
    assert payload["ok"] is True
    for field in ("ok", "tag_sha", "mainline_sha", "drift", "evidence_gated_sha"):
        assert field in payload
    assert payload["tag_sha"] == SHA_A
    assert payload["mainline_sha"] == SHA_A
    assert payload["drift"] == 0
    assert payload["evidence_gated_sha"] == SHA_A
    assert payload["evidence_ref"] == EVIDENCE


def test_mainline_drift_exits_nonzero(tmp_path: Path) -> None:
    fake = FakeGit(
        refs={TAG: SHA_A, "origin/workbench-v3": SHA_B, EVIDENCE: "e" * 40},
        counts={(SHA_A, SHA_B): 3},
        files={"e" * 40: ["artifacts/release-gate-2026-11-15/gate.json"]},
        blobs={("e" * 40, "artifacts/release-gate-2026-11-15/gate.json"): _gate_blob(SHA_A)},
    )
    payload = drift.evaluate(tag=TAG, offline=True, root=tmp_path, run=fake)
    assert payload["ok"] is False
    assert payload["drift"] == 3
    assert any("drifted" in reason for reason in payload["reasons"])

    assert drift.main(["--tag", TAG, "--offline", "--json", "--root", str(tmp_path)], run=fake) == 1


def test_evidence_sha_mismatch_is_not_ok(tmp_path: Path) -> None:
    fake = _clean_fake()
    fake.blobs[("e" * 40, "artifacts/release-gate-2026-11-15/gate.json")] = _gate_blob(SHA_C)
    payload = drift.evaluate(tag=TAG, offline=True, root=tmp_path, run=fake)
    assert payload["ok"] is False
    assert any("evidence gated sha" in reason for reason in payload["reasons"])


def test_missing_tag_is_reported_not_crashing(tmp_path: Path) -> None:
    fake = FakeGit(refs={"origin/workbench-v3": SHA_A})
    payload = drift.evaluate(tag=TAG, offline=True, root=tmp_path, run=fake)
    assert payload["ok"] is False
    assert payload["tag_sha"] is None
    assert any("cannot resolve" in reason for reason in payload["reasons"])


def test_missing_evidence_ref_is_reported(tmp_path: Path) -> None:
    fake = FakeGit(
        refs={TAG: SHA_A, "origin/workbench-v3": SHA_A},
        counts={(SHA_A, SHA_A): 0},
    )
    payload = drift.evaluate(tag=TAG, offline=True, root=tmp_path, run=fake)
    assert payload["ok"] is False
    assert payload["evidence_gated_sha"] is None


def test_evidence_ref_is_derived_from_tag(tmp_path: Path) -> None:
    assert drift.derive_evidence_ref("release-2026-11-15") == "release/2026-11-15-evidence"
    assert drift.derive_evidence_ref("v1") == "v1-evidence"


def test_explicit_evidence_ref_override_is_used(tmp_path: Path) -> None:
    fake = _clean_fake()
    payload = drift.evaluate(
        tag=TAG, evidence_ref="evidence/custom", offline=True, root=tmp_path, run=fake
    )
    assert payload["evidence_ref"] == "evidence/custom"
    assert payload["ok"] is False  # the fake only defines the conventional ref


def test_online_mode_fetches_and_offline_mode_does_not(tmp_path: Path) -> None:
    offline_fake = _clean_fake()
    drift.evaluate(tag=TAG, offline=True, root=tmp_path, run=offline_fake)
    assert not any(call[:1] == ["fetch"] for call in offline_fake.calls)

    online_fake = _clean_fake()
    drift.evaluate(tag=TAG, offline=False, root=tmp_path, run=online_fake)
    assert any(call[:1] == ["fetch"] for call in online_fake.calls)


def test_fetch_failure_is_recorded_but_existing_refs_still_checked(tmp_path: Path) -> None:
    fake = _clean_fake()
    fake.fetch_rc = 1
    payload = drift.evaluate(tag=TAG, offline=False, root=tmp_path, run=fake)
    assert payload["ok"] is True
    assert any("fetch failed" in reason for reason in payload["reasons"])


def test_prefers_gate_json_named_after_the_tag(tmp_path: Path) -> None:
    fake = FakeGit(
        refs={TAG: SHA_A, "origin/workbench-v3": SHA_A, EVIDENCE: "e" * 40},
        counts={(SHA_A, SHA_A): 0},
        files={"e" * 40: [
            "artifacts/release-gate-2026-11-14/gate.json",
            "artifacts/release-gate-2026-11-15/gate.json",
        ]},
        blobs={
            ("e" * 40, "artifacts/release-gate-2026-11-14/gate.json"): _gate_blob(SHA_C),
            ("e" * 40, "artifacts/release-gate-2026-11-15/gate.json"): _gate_blob(SHA_A),
        },
    )
    payload = drift.evaluate(tag=TAG, offline=True, root=tmp_path, run=fake)
    assert payload["ok"] is True
    assert payload["evidence_gated_sha"] == SHA_A


def test_json_cli_shape(tmp_path: Path, capsys) -> None:
    fake = _clean_fake()
    assert drift.main(["--tag", TAG, "--offline", "--json", "--root", str(tmp_path)], run=fake) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    for field in ("ok", "tag_sha", "mainline_sha", "drift", "evidence_gated_sha"):
        assert field in payload


def test_human_cli_reports_drift(tmp_path: Path, capsys) -> None:
    fake = FakeGit(
        refs={TAG: SHA_A, "origin/workbench-v3": SHA_B, EVIDENCE: "e" * 40},
        counts={(SHA_A, SHA_B): 2},
        files={"e" * 40: ["artifacts/release-gate-2026-11-15/gate.json"]},
        blobs={("e" * 40, "artifacts/release-gate-2026-11-15/gate.json"): _gate_blob(SHA_A)},
    )
    assert drift.main(["--tag", TAG, "--offline", "--root", str(tmp_path)], run=fake) == 1
    output = capsys.readouterr().out
    assert "release-drift: DRIFT" in output
    assert "drift=2" in output
