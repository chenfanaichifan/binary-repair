"""Tests for the reflection engine (12-question contract) and its CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services import reflection_engine as engine  # noqa: E402
import run_autonomous_reflection as reflection_cli  # noqa: E402


def _evidence(kind: str = "gap", ref: str = "GAP-1") -> engine.EvidenceRef:
    return engine.EvidenceRef(kind=kind, ref=ref, sha256="a" * 64)


def _capability_observation() -> engine.FailureObservation:
    return engine.FailureObservation(
        source="gap-registry:artifacts/gap-registry-2026-11-16/candidates.json#GAP-1",
        expected="the declared capacity strategy is verified on the cell",
        observed="analysis_only: no capacity evidence profile matched",
        evidence=[_evidence("gap", "GAP-1"), _evidence("cell", "elf/x86_64/64/little")],
        refs=["elf/x86_64/64/little"],
        metadata={
            "failure_type": "capability",
            "capability_id": "capacity",
            "samples": ["fixtures/elf/vuln-capacity-confusion-x86_64.elf"],
        },
    )


def _infrastructure_observation() -> engine.FailureObservation:
    return engine.FailureObservation(
        source="runner:lima",
        expected="guest run completes",
        observed="timeout waiting for limactl shell",
        evidence=[engine.EvidenceRef(kind="infrastructure", ref="limactl")],
        metadata={"failure_type": "capability", "capability_id": "capacity"},
    )


def test_twelve_questions_are_complete_and_ordered() -> None:
    record = engine.reflect(_capability_observation())
    questions = record["12_questions"]
    assert [item["q"] for item in questions] == list(engine.QUESTION_IDS)
    assert len(questions) == 12
    for question in questions:
        assert set(question) == {"q", "answer", "evidence", "status"}
        assert question["status"] in engine.QUESTION_STATUSES
        assert question["answer"].strip()
        assert isinstance(question["evidence"], list)
        if question["status"] == "unknown":
            assert question["answer"].startswith("unknown:")


def test_verified_is_always_false() -> None:
    for observation in (
        _capability_observation(),
        _infrastructure_observation(),
        engine.FailureObservation(source="x", expected="y", observed="z"),
    ):
        record = engine.reflect(observation)
        assert record["verified"] is False
        assert "verified" in record


def test_capability_observation_can_be_candidate_with_planned_experiment() -> None:
    record = engine.reflect(_capability_observation())
    assert record["failure_type"] == "capability"
    assert record["capability_decision"] == "candidate"
    plan = record["experiment_plan"]
    assert plan["status"] == "planned"
    for key in ("samples", "acceptance_criteria", "independent_verification",
                "regression_checks"):
        assert plan[key], key
    assert engine.validate_record(record) == []


def test_infrastructure_failure_never_becomes_capability_gap() -> None:
    record = engine.reflect(_infrastructure_observation())
    assert record["failure_type"] == "infrastructure"
    assert record["capability_decision"] == "not_run"
    assert record["experiment_plan"]["status"] == "cannot_plan"
    assert "infrastructure" in record["experiment_plan"]["reason"]
    assert engine.validate_record(record) == []


def test_no_evidence_cannot_be_candidate() -> None:
    record = engine.reflect(
        engine.FailureObservation(
            source="audit",
            expected="something",
            observed="something else",
            metadata={"failure_type": "capability", "capability_id": "capacity"},
        )
    )
    assert record["failure_type"] == "unknown"
    assert record["capability_decision"] == "not_run"
    assert record["experiment_plan"]["status"] == "cannot_plan"


def test_capability_hint_without_concrete_samples_cannot_plan() -> None:
    observation = engine.FailureObservation(
        source="gap-registry:candidates#GAP-2",
        expected="cell verified",
        observed="analysis_only",
        evidence=[engine.EvidenceRef(kind="gap", ref="GAP-2")],
        metadata={"failure_type": "capability", "capability_id": "capacity"},
    )
    record = engine.reflect(observation)
    assert record["failure_type"] == "capability"
    assert record["experiment_plan"]["status"] == "cannot_plan"
    assert record["capability_decision"] == "analysis_only"
    assert engine.validate_record(record) == []


def test_evaluation_and_knowledge_classification() -> None:
    evaluation = engine.FailureObservation(
        source="acceptance-audit",
        expected="no acceptance mismatch",
        observed="acceptance mismatch ids: AM01, AM02",
        evidence=[engine.EvidenceRef(kind="artifact", ref="report.json#case-1")],
        metadata={"failure_type": "evaluation"},
    )
    record = engine.reflect(evaluation)
    assert record["failure_type"] == "evaluation"
    assert record["capability_decision"] == "analysis_only"
    assert "evaluation" in record["experiment_plan"]["reason"]

    knowledge = engine.FailureObservation(
        source="gap-registry",
        expected="known cell",
        observed="unknown cell discovered outside the universe",
    )
    knowledge_record = engine.reflect(knowledge)
    assert knowledge_record["failure_type"] == "knowledge"
    assert knowledge_record["capability_decision"] == "not_run"


def test_default_classification_never_defaults_to_capability() -> None:
    record = engine.reflect(
        engine.FailureObservation(source="misc", expected="a", observed="b")
    )
    assert record["failure_type"] == "unknown"
    assert record["capability_decision"] == "not_run"


def test_deterministic_ordering_and_id() -> None:
    first = engine.reflect(_capability_observation())
    second = engine.reflect(_capability_observation())
    assert first["reflection_id"] == second["reflection_id"]
    assert first == second
    # Evidence and refs are sorted; the output is stable under input reordering.
    observation = engine.FailureObservation(
        source="x",
        expected="e",
        observed="o",
        evidence=[_evidence("cell", "b"), _evidence("gap", "a")],
        refs=["z", "a"],
    )
    record = engine.reflect(observation)
    # Ordered by (kind, ref): cell:b sorts before gap:a.
    assert [item["ref"] for item in record["observations"][0]["evidence"]] == ["b", "a"]
    assert record["observations"][0]["refs"] == ["a", "z"]


def test_multiple_observations_infrastructure_dominates() -> None:
    record = engine.reflect([_capability_observation(), _infrastructure_observation()])
    assert record["failure_type"] == "infrastructure"
    assert record["capability_decision"] == "not_run"
    assert len(record["observations"]) == 2


def test_validate_record_catches_contract_violations() -> None:
    record = engine.reflect(_capability_observation())

    tampered = json.loads(json.dumps(record))
    tampered["verified"] = True
    assert any("verified" in item for item in engine.validate_record(tampered))

    missing = json.loads(json.dumps(record))
    missing["12_questions"].pop()
    assert any("12_questions" in item for item in engine.validate_record(missing))

    bad_decision = json.loads(json.dumps(record))
    bad_decision["capability_decision"] = "verified_patch"
    assert any("capability_decision" in item for item in engine.validate_record(bad_decision))

    bad_plan = json.loads(json.dumps(record))
    bad_plan["experiment_plan"].pop("regression_checks")
    assert any("regression_checks" in item for item in engine.validate_record(bad_plan))

    empty_sample = json.loads(json.dumps(record))
    empty_sample["experiment_plan"]["samples"] = []
    assert any("samples" in item for item in engine.validate_record(empty_sample))

    no_evidence = json.loads(json.dumps(record))
    for observation in no_evidence["observations"]:
        observation["evidence"] = []
    no_evidence["capability_decision"] = "candidate"
    assert any("evidence" in item for item in engine.validate_record(no_evidence))

    infra_candidate = engine.reflect(_infrastructure_observation())
    infra_candidate["capability_decision"] = "candidate"
    assert any("infrastructure" in item for item in engine.validate_record(infra_candidate))

    empty_answer = json.loads(json.dumps(record))
    empty_answer["12_questions"][0]["answer"] = ""
    assert any("answer" in item for item in engine.validate_record(empty_answer))


# ---------------------------------------------------------------------------
# CLI: scripts/run_autonomous_reflection.py
# ---------------------------------------------------------------------------


def _write_inputs(root: Path, *, missing: tuple[str, ...] = ()) -> None:
    gap = {
        "candidates": [
            {
                "gap_id": "GAP-1",
                "discovery_source": "failure_driven",
                "category": "case_target_analysis_failure",
                "subcategory": "cwe121-unchecked-strcpy",
                "target": {"kind": "case", "id": "cwe121-unchecked-strcpy"},
                "evidence_refs": [
                    "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json#cases",
                    "docs/status/claims.json#non_goals[id=EG-cases-target-not-analyzed]",
                ],
                "observed_failure": "deterministic baseline records analysis_only for the case",
                "proposed_experiment": {"status": "proposed", "steps": ["review"]},
            }
        ]
    }
    acceptance = {
        "cases": [
            {"case_id": "case-1", "expected_mismatches": ["AM01"], "ok": True}
        ]
    }
    coverage = {
        "gaps": [
            {
                "gap_id": "RG-1",
                "category": "runtime_gap",
                "status": "mitigated",
                "symptom": "host-dependent declared-vs-measured runtime tier",
                "evidence": ["probe:lima unavailable on host"],
            }
        ]
    }
    files = {
        "gap_candidates": ("artifacts/gap-registry-2026-11-16/candidates.json", gap),
        "acceptance_audit": (
            "artifacts/acceptance-model-audit-2026-11-16/report.json", acceptance
        ),
        "coverage_matrix": (
            "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json", coverage
        ),
    }
    for key, (relative, payload) in files.items():
        if key in missing:
            continue
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _run_reflection(root: Path, out: Path, *extra: str) -> int:
    return reflection_cli.main([
        "--root", str(root), "--out", str(out), *extra,
    ])


def test_cli_builds_bundle_from_fixture_inputs(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    out = tmp_path / "bundle"
    assert _run_reflection(tmp_path, out, "--json") == 0
    payload = json.loads((out / "reflection.json").read_text(encoding="utf-8"))
    assert payload["kind"] == "autonomous_reflection"
    assert payload["summary"]["records"] == 3
    assert payload["summary"]["verified_true_count"] == 0
    decisions = payload["summary"]["capability_decision_counts"]
    assert decisions.get("candidate") == 1
    assert decisions.get("analysis_only") == 1
    assert decisions.get("not_run") == 1
    assert payload["not_run"] == []
    assert reflection_cli.verify_bundle(out) == []
    assert reflection_cli.main(["--root", str(tmp_path), "--out", str(out), "--check"]) == 0


def test_gap_candidate_category_hints_drive_classification(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    candidates = root / "artifacts/gap-registry-2026-11-16/candidates.json"
    candidates.parent.mkdir(parents=True)
    payload = {
        "candidates": [
            {"gap_id": "GAP-CAP", "category": "case_target_analysis_failure",
             "target": {"kind": "case", "id": "case-1"},
             "evidence_refs": ["docs/status/claims.json#non_goals[id=NG-1]"]},
            {"gap_id": "GAP-EVAL", "category": "audit_meta_mismatch_regression",
             "target": {"kind": "matrix"}, "evidence_refs": ["artifacts/a.json#row"]},
            {"gap_id": "GAP-KNOW", "category": "universe_dimension_gap",
             "target": {"kind": "dimension", "id": "D01"},
             "evidence_refs": ["docs/acceptance/x.md#dim"]},
            {"gap_id": "GAP-DIFF", "category": "platform_capability_differential",
             "target": {"kind": "cell", "cell": "pe/x86_64"},
             "evidence_refs": ["scripts/check_capability_contract.py --json#cells"]},
        ]
    }
    candidates.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    acceptance = root / "artifacts/acceptance-model-audit-2026-11-16/report.json"
    acceptance.parent.mkdir(parents=True)
    acceptance.write_text(json.dumps({"cases": []}) + "\n", encoding="utf-8")
    coverage = root / "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json"
    coverage.parent.mkdir(parents=True)
    coverage.write_text(json.dumps({"gaps": []}) + "\n", encoding="utf-8")
    out = tmp_path / "bundle"
    assert _run_reflection(root, out) == 0
    bundle = json.loads((out / "reflection.json").read_text(encoding="utf-8"))
    by_gap = {
        record["observations"][0]["observation_id"]: record
        for record in bundle["records"]
    }
    assert by_gap["gap-GAP-CAP"]["failure_type"] == "capability"
    assert by_gap["gap-GAP-CAP"]["capability_decision"] == "candidate"
    assert by_gap["gap-GAP-EVAL"]["failure_type"] == "evaluation"
    assert by_gap["gap-GAP-KNOW"]["failure_type"] == "knowledge"
    assert by_gap["gap-GAP-DIFF"]["failure_type"] == "evaluation"


def test_cli_missing_input_is_explicit_not_run_exit2(tmp_path: Path) -> None:
    _write_inputs(tmp_path, missing=("acceptance_audit",))
    out = tmp_path / "bundle"
    assert _run_reflection(tmp_path, out, "--json") == 2
    payload = json.loads((out / "reflection.json").read_text(encoding="utf-8"))
    assert [item["input"] for item in payload["not_run"]] == ["acceptance_audit"]
    assert "does not exist" in payload["not_run"][0]["reason"]
    # No acceptance records were invented from the missing input.
    assert all(
        "acceptance" not in record["observations"][0]["source"]
        for record in payload["records"]
    )


def test_cli_check_detects_tampering(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    out = tmp_path / "bundle"
    assert _run_reflection(tmp_path, out) == 0
    reflection_path = out / "reflection.json"
    payload = json.loads(reflection_path.read_text(encoding="utf-8"))
    payload["records"][0]["verified"] = True
    reflection_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    assert reflection_cli.main(["--root", str(tmp_path), "--out", str(out), "--check"]) == 1


def test_cli_check_missing_bundle_is_failure(tmp_path: Path) -> None:
    _write_inputs(tmp_path)
    out = tmp_path / "missing-bundle"
    assert reflection_cli.main(["--root", str(tmp_path), "--out", str(out), "--check"]) == 1
    assert not out.exists()
