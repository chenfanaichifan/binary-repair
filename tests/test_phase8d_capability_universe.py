"""Phase-8D D00 baseline and D01 capability-universe tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import build_phase8d_capability_universe as builder  # noqa: E402

BASE = ROOT / "artifacts/phase8d-baseline-2026-11-17/baseline.json"
REGISTRY = ROOT / "artifacts/phase8d-capability-universe-2026-11-17/registry.json"
SCHEMA = ROOT / "contracts/phase8d-capability-universe.schema.json"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )


def test_phase8c_release_and_evidence_are_ancestors() -> None:
    for sha in (
        "4a7b2355ffc5225d013a777bc7d588abac58f944",
        "ec503e4b1df53ad39fa836bd34d93a18564d78f9",
    ):
        check = _git("merge-base", "--is-ancestor", sha, "HEAD")
        assert check.returncode == 0, check.stderr


def test_baseline_records_phase8c_gate_ci_and_ref_cleanup() -> None:
    payload = json.loads(BASE.read_text(encoding="utf-8"))
    assert payload["kind"] == "phase8d_baseline"
    assert payload["phase8c"]["release_sha"] == builder.PHASE8C_RELEASE_SHA
    assert payload["phase8c"]["tree_sha"] == builder.PHASE8C_TREE_SHA
    assert payload["phase8c"]["evidence_tip"] == builder.PHASE8C_EVIDENCE_TIP
    for key in ("release_tag", "evidence_tag", "evidence_branch"):
        assert payload["phase8c"][key]["status"] == (
            "deleted_or_renamed_by_consolidation"
        )
    assert payload["phase8c"]["release_tag"]["tag_object_sha"] == (
        builder.PHASE8C_RELEASE_TAG_OBJECT
    )
    assert payload["phase8c"]["evidence_tag"]["tag_object_sha"] == (
        builder.PHASE8C_EVIDENCE_TAG_OBJECT
    )
    assert payload["gate"]["passed"] == 13
    assert payload["gate"]["failed"] == 0
    assert payload["gate"]["required"] == 13
    assert payload["gate"]["ok"] is True
    assert payload["ci"]["final_ci_run"] == 43748886046
    assert payload["ci"]["final_ubuntu_run"] == 43748886289
    assert payload["ci"]["final_ci_conclusion"] == "success"
    assert payload["phase8b"]["verified"] == 2
    assert payload["consolidation"]["refs_removed_or_renamed"] is True
    assert payload["phase8c_results"]["hidden_verified"] == 0
    assert payload["phase8c_results"]["hidden_material_committed"] is False
    assert payload["phase8c_results"]["no_capability_promotion"] is True


def test_baseline_ci_ids_are_present_in_final_evidence_addendum() -> None:
    addendum = (ROOT / builder.PHASE8C_ADDENDUM).read_text(encoding="utf-8")
    assert str(builder.FINAL_CI_RUN) in addendum
    assert str(builder.FINAL_UBUNTU_RUN) in addendum


def test_registry_validates_against_contract() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(registry)


def test_registry_is_deterministic_and_check_passes() -> None:
    first = builder.build_artifacts()
    second = builder.build_artifacts()
    assert first == second
    assert builder.check_artifacts() == []
    assert len(first) == 6


def test_no_generalized_or_promoted_unit_and_no_auto_promotion() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    counts = registry["counts"]
    assert counts["generalized"] == 0
    assert counts["promoted"] == 0
    assert registry["state_machine"]["automatic_promotion_allowed"] is False
    transitions = registry["state_machine"]["transitions"]
    assert "promoted" not in transitions["analysis_only"]
    assert "promoted" not in transitions["candidate_generated"]
    assert "promoted" not in transitions["independently_verified"]
    assert transitions["generalized"] == ["promoted", "not_run", "unmeasurable"]
    assert registry["state_machine"]["promotion_requires"]["from_state"] == "generalized"


def test_illegal_shortcuts_are_rejected_by_transition_table() -> None:
    transitions = {
        old: set(new)
        for old, new in json.loads(REGISTRY.read_text())["state_machine"]["transitions"].items()
    }
    assert "independently_verified" not in transitions["analysis_only"]
    assert "independently_verified" not in transitions["unknown"]
    assert "promoted" not in transitions["independently_verified"]
    assert "promoted" not in transitions["candidate_generated"]
    assert "promoted" in transitions["generalized"]


def test_legal_denominators_and_rate_semantics() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    denominators = registry["denominators"]
    assert denominators["declared_cells"]["denominator"] == 240
    assert denominators["public_runtime_oracle"]["denominator"] == 24
    assert denominators["hidden_runtime_oracle"]["denominator"] == 6
    assert denominators["public_analysis_only"]["denominator"] == 8
    assert denominators["hidden_analysis_only"]["denominator"] == 2
    for name, block in denominators.items():
        assert block["represented_cases"] == block["denominator"], name
        assert sum(block["state_case_counts"].values()) == block["denominator"], name
        if block["denominator"] == 0:
            assert all(value is None for value in block["rates"].values())
    pub = denominators["public_runtime_oracle"]["state_case_counts"]
    assert pub["independently_verified"] == 2
    assert pub["candidate_generated"] == 1
    assert pub["analysis_only"] == 19
    assert pub["unsupported"] == 2
    hidden = denominators["hidden_runtime_oracle"]["state_case_counts"]
    assert hidden["analysis_only"] == 6
    assert hidden["independently_verified"] == 0
    assert registry["coverage"]["public_runtime_oracle"]["verified_rate"] == pytest.approx(2 / 24)
    assert registry["coverage"]["hidden_runtime_oracle"]["verified_rate"] == 0.0
    assert registry["coverage"]["analysis_only"]["public_denominator"] == 8
    assert registry["coverage"]["analysis_only"]["hidden_denominator"] == 2


def test_unknown_outside_catalog_is_unmeasurable_not_zero() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    unknown = registry["unknown_space"]
    assert unknown["outside_catalog_state"] == "unmeasurable"
    assert unknown["outside_catalog_count"] is None
    assert unknown["outside_catalog_measured_fraction"] is None
    assert unknown["inside_catalog_unknown_units"] > 0
    assert "zero" in unknown["reason"].lower()
    assert registry["coverage"]["declared_universe"]["unknown_is_not_zero_outside_catalog"] is True


def test_units_have_resolvable_evidence_and_dimensions() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    dimension_ids = {item["id"] for item in registry["dimensions"]}
    unit_ids = {item["id"] for item in registry["units"]}
    for unit in registry["units"]:
        assert set(unit["dimension_ids"]) <= dimension_ids
        assert unit["represented_cases"] >= 1
        assert unit["state"] in registry["state_machine"]["states"]
        for dep in unit["dependencies"]:
            assert dep in unit_ids or dep.startswith("dimension:") or dep.startswith("cell:")
        for ref in unit["evidence_refs"]:
            path = ref.split("#", 1)[0]
            assert (ROOT / path).is_file(), f"missing evidence path {path}"


def test_dimension_dependencies_form_a_dag() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    deps = {item["id"]: set(item["dependencies"]) for item in registry["dimensions"]}

    def visit(node: str, seen: set[str]) -> None:
        if node in seen:
            raise AssertionError(f"dependency cycle at {node}")
        seen.add(node)
        for dep in deps[node]:
            assert dep in deps
            visit(dep, set(seen))

    for node in deps:
        visit(node, set())


def test_schema_rejects_invalid_state_and_unknown_shape() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    bad = json.loads(json.dumps(registry))
    bad["units"][0]["state"] = "auto_promoted"
    assert list(validator.iter_errors(bad))
    bad = json.loads(json.dumps(registry))
    bad["unknown_space"]["outside_catalog_count"] = 0
    assert list(validator.iter_errors(bad))


def test_baseline_and_universe_docs_are_ascii_and_reproducible() -> None:
    for path in (
        ROOT / "docs/operations/phase8d-baseline-and-capability.md",
        ROOT / "artifacts/phase8d-baseline-2026-11-17/README.md",
        ROOT / "artifacts/phase8d-capability-universe-2026-11-17/README.md",
    ):
        data = path.read_bytes()
        data.decode("ascii")


def test_builder_has_no_network_or_ai_paths() -> None:
    source = (ROOT / "scripts/build_phase8d_capability_universe.py").read_text().lower()
    for token in ("requests", "urllib", "openai", "anthropic", "http://", "https://"):
        assert token not in source
