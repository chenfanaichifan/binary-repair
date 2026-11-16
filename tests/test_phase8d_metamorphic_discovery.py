"""Offline tests for Phase-8D metamorphic/mutation discovery."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services import metamorphic_discovery as mechanism  # noqa: E402
import run_metamorphic_discovery as runner  # noqa: E402

ARTIFACT = ROOT / "artifacts/phase8d-discovery-2026-11-17"


def _manifest() -> dict:
    return json.loads((ROOT / mechanism.MANIFEST_REL).read_text(encoding="utf-8"))


def _artifact() -> dict:
    return json.loads((ARTIFACT / "discovery.json").read_text(encoding="utf-8"))


def test_relations_are_variant_groups_not_hidden() -> None:
    relations = mechanism.relation_groups(_manifest())
    assert len(relations) == 2
    assert all(item["variant_sample_ids"] for item in relations)
    assert all("hidden" not in item["relation_id"] for item in relations)
    variants = mechanism.variants_from_manifest(_manifest())
    assert [item["sample_id"] for item in variants] == [
        "variant-cwe122-O2",
        "variant-cwe122-O2-stripped",
        "variant-cwe125-O3-static",
        "variant-cwe125-Os-static-stripped",
    ]


def test_family_specific_mutations_are_bounded_and_deterministic() -> None:
    manifest = _manifest()
    sample = next(item for item in manifest["samples"]
                  if item["sample_id"] == "variant-cwe122-O2")
    mutations = mechanism.build_mutations(sample)
    assert len(mutations) <= mechanism.MAX_MUTATIONS_PER_VARIANT
    assert [item["mutation_id"] for item in mutations] == [
        "length-0", "length-15", "length-16", "length-17", "length-64", "length-256",
    ]
    assert mutations == mechanism.build_mutations(sample)
    index_sample = next(item for item in manifest["samples"]
                        if item["sample_id"] == "variant-cwe125-O3-static")
    assert [item["mutation_id"] for item in mechanism.build_mutations(index_sample)] == [
        "index-0", "index-5", "index-15", "index-16", "index-1000000",
    ]


def test_fake_engine_and_oracle_produce_measured_differences() -> None:
    def engine(_sample, _path):
        if "stripped" in str(_sample.get("sample_id")):
            return {
                "status": "unsupported", "detection": None,
                "candidate": {"produced": False, "sha256": None},
                "not_run_reason": "target resolution failed",
            }
        return {
            "status": "executed", "detection": False,
            "candidate": {"produced": False, "sha256": None},
            "repair": {"disposition": "analysis_only"},
        }

    def oracle(_path, argv):
        return SimpleNamespace(
            available=True, crashed=(len(argv[0]) >= 64) if argv else False,
            exit_code=255 if argv and len(argv[0]) >= 64 else 0,
            timed_out=False, runner="fake", tier="fake", error=None,
        )

    payload = mechanism.discover(
        root=ROOT, engine_fn=engine, execute_fn=oracle,
        max_variants=2, max_mutations=2,
    )
    assert payload["summary"]["variant_count"] == 2
    assert payload["summary"]["engine_executed"] == 1
    assert payload["summary"]["engine_not_run_or_unsupported"] == 1
    assert payload["summary"]["mutation_count"] == 2
    assert payload["summary"]["mutations_executed"] == 2
    assert payload["summary"]["engine_difference_count"] >= 1
    assert all(item["executed"] for item in payload["mutation_runs"][0]["variants"])
    assert payload["provenance"]["network_used"] is False
    assert payload["provenance"]["ai_used"] is False


def test_committed_discovery_artifact_is_consistent_and_honest() -> None:
    payload = _artifact()
    assert payload["kind"] == mechanism.KIND
    assert payload["provenance"]["no_hidden_material_read"] is True
    assert payload["provenance"]["network_used"] is False
    assert payload["provenance"]["ai_used"] is False
    assert "hidden" not in json.dumps(payload["relations"]).lower()
    variants = payload["variant_runs"]
    assert len(variants) == 4
    by_id = {item["sample_id"]: item for item in variants}
    assert by_id["variant-cwe122-O2"]["engine"]["status"] == "executed"
    assert by_id["variant-cwe122-O2"]["engine"]["candidate_produced"] is False
    assert by_id["variant-cwe122-O2-stripped"]["engine"]["status"] == "unsupported"
    assert payload["summary"]["mutations_executed"] == payload["summary"]["mutation_count"]
    assert payload["summary"]["relation_difference_count"] == 0
    assert payload["summary"]["engine_difference_count"] == 2
    assert runner.check_artifact(ARTIFACT) == []


def test_mutation_tamper_is_detected(tmp_path) -> None:
    data = (ARTIFACT / "discovery.json").read_bytes()
    (tmp_path / "discovery.json").write_bytes(data.replace(b"relation_holds", b"relation_holdz"))
    (tmp_path / "README.md").write_text("x")
    (tmp_path / "SHA256SUMS").write_text("")
    assert runner.check_artifact(tmp_path)
