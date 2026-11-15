"""Phase-8C C12 release evidence bundle integrity tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_phase8c_evidence as evidence  # noqa: E402


def test_committed_bundle_verifies() -> None:
    assert evidence.verify_bundle() == []


def test_bundle_summary_binds_public_and_hidden_evidence() -> None:
    summary = json.loads((ROOT / evidence.OUT_REL / "summary.json").read_text())
    assert summary["kind"] == "phase8c_release_evidence"
    assert summary["status"] == "ok_with_limitations"
    assert summary["base_sha"] == evidence.BASE_SHA
    assert summary["public_benchmark"]["sample_count"] == 32
    assert summary["public_benchmark"]["runtime_oracle_samples"] == 24
    assert summary["public_benchmark"]["analysis_only_samples"] == 8
    assert summary["public_benchmark"]["false_verified"] == 0
    assert summary["public_benchmark"]["deterministic_claim_withdrawn"] == 1
    assert summary["public_benchmark"]["repeats"] == 2
    hidden = summary["hidden_benchmark"]
    assert hidden["sample_count"] == 8
    assert (hidden["runtime_count"], hidden["analysis_only_count"]) == (6, 2)
    assert hidden["verified"] == 0
    assert hidden["false_verified"] == 0
    assert hidden["material_committed"] is False
    assert hidden["commitment_sha256"] == (
        "eaec60aadd42388efb725a668b887465268c78fd257ec4622ac56eac571bae12"
    )
    assert summary["quality"]["hidden_contamination"] == "pass"
    assert summary["quality"]["hidden_aggregate"] == "pass"


def test_bundle_does_not_claim_capability_promotion() -> None:
    summary = json.loads((ROOT / evidence.OUT_REL / "summary.json").read_text())
    text = " ".join(summary["limitations"] + summary["not_claimed"]).lower()
    assert "capability promotion" in text
    assert "no new vulnerability-repair capability" in text
    assert summary["hidden_benchmark"]["material_committed"] is False


def test_environment_is_public_and_has_no_hidden_material() -> None:
    env = json.loads((ROOT / evidence.OUT_REL / "environment.json").read_text())
    assert env["kind"] == "phase8c_environment"
    assert env["hidden_material_committed"] is False
    assert env["network_used"] is False
    assert env["ai_provider_used"] is False
    assert "hidden_root_present" in env


def test_private_hidden_references_and_per_sample_fields_are_rejected() -> None:
    assert evidence._contains_hidden_material("x", "path") == []
    assert evidence._contains_hidden_material(
        {"sample_id": "hidden-1"}, "summary"
    )
    assert evidence._contains_hidden_material(
        "/Users/x/.binaryrepair/phase8c-hidden/hidden-manifest.json", "summary"
    )
    # The public aggregate directory name is not the private root.
    assert evidence._contains_hidden_material(
        "artifacts/phase8c-hidden-2026-11-16/aggregate.json", "summary"
    ) == []


def test_tampered_bundle_is_detected(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    for name in ("summary.json", "environment.json", "README.md"):
        (out / name).parent.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes((ROOT / evidence.OUT_REL / name).read_bytes())
    # Deliberately stale SHA256SUMS copied from the committed bundle is fine;
    # tamper summary content instead and require a mismatch.
    (out / "SHA256SUMS").write_bytes(
        (ROOT / evidence.OUT_REL / "SHA256SUMS").read_bytes())
    summary = json.loads((out / "summary.json").read_text())
    summary["public_benchmark"]["false_verified"] = 7
    (out / "summary.json").write_text(json.dumps(summary) + "\n")
    problems = evidence.verify_bundle(out)
    assert any("sha256 mismatch summary.json" in item or "false_verified" in item
               for item in problems)


def test_write_bundle_round_trip(tmp_path: Path) -> None:
    out = tmp_path / "bundle"
    evidence.write_bundle(out)
    assert evidence.verify_bundle(out) == []
    summary = json.loads((out / "summary.json").read_text())
    assert summary["public_benchmark"]["sample_count"] == 32


def test_evidence_script_is_offline_and_has_no_ai_imports() -> None:
    source = (ROOT / "scripts/audit_phase8c_evidence.py").read_text().lower()
    assert "requests" not in source
    assert "openai" not in source
    assert "anthropic" not in source
    assert "urllib" not in source
