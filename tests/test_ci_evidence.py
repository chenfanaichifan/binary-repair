"""Offline CI evidence/claims consistency; online check is opt-in."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_claims_are_offline_consistent():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_ci_evidence.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "claims=ok" in result.stdout


def test_claims_do_not_claim_universal_repair():
    claims = json.loads((ROOT / "docs" / "status" / "claims.json").read_text())
    assert claims["product_paths"] == ["asm_roundtrip", "binary_direct"]
    assert "not universal repair" in claims["scope"]
    assert any("paradigm A" in item for item in claims["explicitly_unimplemented"])


# ---------------------------------------------------------------------------
# Phase-6 ci_evidence schema v2
# ---------------------------------------------------------------------------

import tempfile  # noqa: E402


def _v2_claims(tmp_path: Path, **overrides) -> dict:
    gated = "a" * 40
    signoff = tmp_path / "docs" / "release" / "CI-SIGNOFF-test.md"
    signoff.parent.mkdir(parents=True, exist_ok=True)
    signoff.write_text("owner signoff\n", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "latest_verified_ci": {
            "run_id": 111,
            "head_sha": gated,
            "branch": "workbench-v3",
            "conclusion": "success",
        },
        "ci_evidence": {
            "schema_version": 2,
            "gated_sha": gated,
            "hosted_ci": {
                "workflow": "CI / release-gate-hosted",
                "run_id": 111,
                "run_url": "https://github.com/chenfanaichifan/binary-repair/actions/runs/111",
                "head_sha": gated,
                "conclusion": "success",
                "scope": "GitHub-hosted Ubuntu release layer",
            },
            "self_hosted_nightly": {
                "status": "not_run",
                "reason": "no self-hosted lima runner provisioned",
                "signoff": "docs/release/CI-SIGNOFF-test.md",
            },
            "local_gate": {
                "status": "passed",
                "frozen_sha": gated,
                "gate_evidence_sha256": "b" * 64,
            },
        },
    }
    for key, value in overrides.items():
        node = payload
        parts = key.split(".")
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = value
    return payload


def _run_ci_evidence(tmp_path: Path, claims: dict) -> subprocess.CompletedProcess:
    path = tmp_path / "claims.json"
    path.write_text(json.dumps(claims), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_ci_evidence.py"),
         "--claims", str(path), "--root", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )


def test_ci_evidence_v2_valid(tmp_path: Path) -> None:
    result = _run_ci_evidence(tmp_path, _v2_claims(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "schema=v2" in result.stdout


def test_ci_evidence_v2_rejects_historical_mirror(tmp_path: Path) -> None:
    claims = _v2_claims(tmp_path)
    claims["latest_verified_ci"]["head_sha"] = "f" * 40
    result = _run_ci_evidence(tmp_path, claims)
    assert result.returncode == 1
    assert "latest_verified_ci.head_sha" in result.stdout


def test_ci_evidence_v2_requires_signoff_for_not_run(tmp_path: Path) -> None:
    claims = _v2_claims(tmp_path)
    claims["ci_evidence"]["self_hosted_nightly"]["signoff"] = (
        "docs/release/missing.md")
    result = _run_ci_evidence(tmp_path, claims)
    assert result.returncode == 1
    assert "signoff file is missing" in result.stdout


def test_ci_evidence_v2_docs_only_delta_paths(tmp_path: Path) -> None:
    claims = _v2_claims(tmp_path)
    claims["ci_evidence"]["hosted_ci"]["head_sha"] = "c" * 40
    claims["latest_verified_ci"]["head_sha"] = "c" * 40
    claims["ci_evidence"]["hosted_ci"]["docs_only_delta"] = {
        "from_sha": "a" * 40,
        "to_sha": "c" * 40,
        "paths": ["docs/status/claims.json"],
    }
    result = _run_ci_evidence(tmp_path, claims)
    assert result.returncode == 0, result.stdout + result.stderr
    claims["ci_evidence"]["hosted_ci"]["docs_only_delta"]["paths"] = [
        "app/main.py"]
    result = _run_ci_evidence(tmp_path, claims)
    assert result.returncode == 1
    assert "not evidence/docs-only" in result.stdout


def test_ci_evidence_v2_local_gate_sha_must_match(tmp_path: Path) -> None:
    claims = _v2_claims(tmp_path)
    claims["ci_evidence"]["local_gate"]["frozen_sha"] = "d" * 40
    result = _run_ci_evidence(tmp_path, claims)
    assert result.returncode == 1
    assert "local_gate.frozen_sha" in result.stdout
