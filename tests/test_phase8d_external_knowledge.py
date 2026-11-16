"""Offline tests for the Phase-8D CWE 5.0 external-knowledge scanner."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services import external_knowledge as knowledge  # noqa: E402
import scan_external_knowledge as scanner  # noqa: E402

ARTIFACT = ROOT / "artifacts/phase8d-external-knowledge-2026-11-17"


def _snapshot() -> dict:
    return knowledge.load_snapshot(ROOT)


def _artifact() -> dict:
    return json.loads((ARTIFACT / "external-knowledge.json").read_text(encoding="utf-8"))


def test_snapshot_is_versioned_and_measured() -> None:
    snapshot = _snapshot()
    assert snapshot["kind"] == knowledge.SNAPSHOT_KIND
    assert snapshot["catalog"]["version"] == "5.0"
    assert snapshot["catalog"]["date"] == "2026-10-28"
    assert snapshot["catalog"]["namespace"] == "http://cwe.mitre.org/cwe-8"
    assert len(snapshot["weaknesses"]) == 984
    assert snapshot["schema_drift"]["prior_version"] == "4.19"
    assert snapshot["schema_drift"]["new_count"] == 15
    assert snapshot["schema_drift"]["removed_count"] == 0
    assert snapshot["schema_drift"]["namespace_changed"] is True
    assert snapshot["schema_drift"]["current_counts"]["categories"] == 0
    assert snapshot["schema_drift"]["current_counts"]["groupings"] == 431


def test_schema_8_0_breaking_changes_are_explicit() -> None:
    snapshot = _snapshot()
    drift = knowledge.detect_version_drift(snapshot)
    assert drift["status"] == "current"
    assert drift["actual_schema_version"] == "8.0"
    assert drift["prior_schema_change"] is True
    schema = json.loads((ROOT / "data/external/cwe-5.0/schema-drift.json").read_text())
    assert schema["schema_version"] == "8.0"
    assert schema["prior_schema_version"] == "7.3"
    assert schema["changes"]["new_count"] == 15
    assert "Categories were removed" in " ".join(schema["breaking_changes"])


def test_version_drift_is_detected_not_hidden() -> None:
    snapshot = copy.deepcopy(_snapshot())
    snapshot["catalog"]["version"] = "4.19"
    drift = knowledge.detect_version_drift(snapshot)
    assert drift["status"] == "drifted"
    assert drift["catalog_version_drift"] is True
    snapshot["catalog"]["version"] = "5.0"
    snapshot["catalog"]["schema_location"] = (
        "http://cwe.mitre.org/cwe-7 http://cwe.mitre.org/data/xsd/cwe_schema_v7.3.xsd"
    )
    assert knowledge.detect_version_drift(snapshot)["status"] == "drifted"


def test_scan_maps_entries_to_candidates_without_support_claims() -> None:
    artifact = _artifact()
    assert artifact["kind"] == knowledge.SCAN_KIND
    assert artifact["summary"]["external_entries"] == 984
    assert artifact["summary"]["support_claimed"] is False
    assert artifact["summary"]["capability_promotion"] is False
    assert artifact["summary"]["mapped_candidates"] == 232
    candidates = artifact["mapping"]["candidates"]
    assert len(candidates) == 232
    assert all(item["status"] == "candidate" for item in candidates)
    assert all(item["support_claimed"] is False for item in candidates)
    assert all(item["discovery_source"] == "knowledge_source_scan" for item in candidates)
    assert all(item["verification_required"] is True for item in candidates)
    assert all(item["proposed_experiment"]["status"] == "proposed" for item in candidates)
    assert any(item["public_corpus_exposure"]["public_samples"] > 0 for item in candidates)
    assert all(item["public_corpus_exposure"]["verified_repairs"] >= 0 for item in candidates)


def test_candidates_validate_with_gap_registry() -> None:
    from app.services import gap_registry

    artifact = _artifact()
    validation = gap_registry.validate_records(artifact["mapping"]["candidates"])
    assert validation["ok"] is True, validation["violations"]
    assert all(c["status"] == "candidate" for c in artifact["mapping"]["candidates"])


def test_parser_reads_tiny_schema_8_catalog() -> None:
    xml = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
    <Weakness_Catalog xmlns=\"http://cwe.mitre.org/cwe-8\" Version=\"5.1\" Date=\"2026-12-01\">
      <Weaknesses>
        <Weakness ID=\"9999\" Name=\"Test Weakness\" Abstraction=\"Variant\" Structure=\"Simple\" Status=\"Draft\">
          <Description>A test weakness.</Description>
          <Related_Weaknesses><Related_Weakness Nature=\"ChildOf\" CWE_ID=\"122\"/></Related_Weaknesses>
        </Weakness>
      </Weaknesses>
      <Groupings><Grouping ID=\"1\" Name=\"test\"/></Groupings>
    </Weakness_Catalog>"""
    parsed = knowledge.parse_catalog(xml)
    assert parsed["catalog"]["version"] == "5.1"
    assert parsed["catalog"]["namespace"] == "http://cwe.mitre.org/cwe-8"
    assert parsed["catalog"]["counts"]["weaknesses"] == 1
    assert parsed["catalog"]["counts"]["groupings"] == 1
    assert parsed["weaknesses"][0]["related_cwe_ids"] == ["122"]


def test_committed_artifact_is_deterministic_and_offline(monkeypatch) -> None:
    assert scanner.check_artifact(ARTIFACT) == []

    def _no_network(*_args, **_kwargs):
        raise AssertionError("network must not be used in offline scan/check")

    monkeypatch.setattr(knowledge.urllib.request, "urlopen", _no_network)
    payload = scanner.build_artifact(live=False)
    assert payload["provenance"]["network_used"] is False
    assert payload["live_fetch"] is None


def test_tamper_and_invalid_versions_fail_closed(tmp_path) -> None:
    data = json.loads((ARTIFACT / "external-knowledge.json").read_text())
    (tmp_path / "external-knowledge.json").write_text(json.dumps(data))
    (tmp_path / "README.md").write_text("tampered")
    (tmp_path / "SHA256SUMS").write_text("")
    assert scanner.check_artifact(tmp_path)

    snapshot = _snapshot()
    snapshot = copy.deepcopy(snapshot)
    snapshot["weaknesses"] = snapshot["weaknesses"][:-1]
    assert knowledge.validate_snapshot(snapshot)


def test_snapshot_files_are_hashed_in_artifact() -> None:
    artifact = _artifact()
    provenance = artifact["provenance"]
    for rel, key in (
        ("data/external/cwe-5.0/snapshot.json", "snapshot_file_sha256"),
        ("data/external/cwe-5.0/schema-drift.json", "schema_drift_file_sha256"),
        ("data/external/cwe-5.0/provenance.json", "provenance_file_sha256"),
        ("benchmark/phase8c/manifest.json", "manifest_sha256"),
    ):
        import hashlib
        assert provenance[key] == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def test_no_hidden_material_or_capability_promotion() -> None:
    artifact = _artifact()
    text = json.dumps(artifact, sort_keys=True)
    assert "phase8c-hidden" not in text
    assert "hidden_manifest" not in text
    assert artifact["summary"]["support_claimed"] is False
    assert artifact["summary"]["capability_promotion"] is False
    for item in artifact["mapping"]["candidates"]:
        assert item["status"] == "candidate"
        assert item["support_claimed"] is False
