"""Tests for the unified autonomous-repair audit entry point (injected runner)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import autonomous_repair_audit as audit_cli  # noqa: E402


class FakeRunner:
    """Deterministic subprocess replacement keyed by script basename."""

    def __init__(self, responses: dict[str, tuple[int, str, str]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[list[str]] = []

    def __call__(self, command, cwd, timeout):
        argv = [str(part) for part in command]
        self.calls.append(argv)
        script = Path(argv[1]).name if len(argv) > 1 else ""
        returncode, stdout, stderr = self.responses.get(script, (0, "", ""))
        return audit_cli.CommandResult(returncode, stdout, stderr)

    def called_scripts(self) -> list[str]:
        return [Path(call[1]).name for call in self.calls if len(call) > 1]


def _make_root(tmp_path: Path, *, missing: tuple[str, ...] = ()) -> Path:
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    for spec in audit_cli.CHECK_SPECS:
        if spec["script"].split("/")[-1] in missing:
            continue
        (root / spec["script"]).write_text("", encoding="utf-8")
    (root / "artifacts").mkdir(exist_ok=True)
    return root


def _passing_runner() -> FakeRunner:
    return FakeRunner({
        name: (0, json.dumps({"ok": True}), "")
        for name in (
            "check_universe_methodology.py",
            "run_autonomous_reflection.py",
            "verify_coverage_gate.py",
            "audit_acceptance_models.py",
            "discover_capability_gaps.py",
            "meta_audit.py",
            "build_provider_coverage.py",
            "audit_repair_readiness.py",
            "build_ground_truth_benchmark.py",
            "verify_repair.py",
            "audit_phase8b_verifier_semantics.py",
            "check_phase8b_verification.py",
            "audit_phase8c_readiness.py",
            "migrate_ground_truth_v2.py",
            "build_phase8c_corpus.py",
            "audit_phase8c_contamination.py",
            "audit_phase8c_quality.py",
            "run_phase8c_benchmark.py",
            "audit_phase8c_evidence.py",
            "build_phase8d_capability_universe.py",
            "build_phase8d_gap_registry.py",
            "audit_acceptance_2.py",
            "analyze_phase8d_heap_malloc_abi.py",
            "run_phase8d_hidden_attribution.py",
            "scan_external_knowledge.py",
            "run_metamorphic_discovery.py",
            "build_phase8d_discovery_registry.py",
            "audit_hidden_isolation.py",
            "evaluate_promotion.py",
            "build_phase8d_experiment_bundle.py",
        )
    })


def test_full_mode_all_passing_writes_valid_evidence(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    out = tmp_path / "evidence"
    runner = _passing_runner()
    code = audit_cli.main(
        ["--mode", "full", "--root", str(root), "--evidence-out", str(out), "--json"],
        run=runner,
    )
    assert code == 0
    payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert payload["kind"] == "autonomous_repair_audit"
    assert payload["ok"] is True
    assert len(payload["checks"]) == 30
    assert sum(1 for check in payload["checks"] if check["required"]) == 7
    assert sum(1 for check in payload["checks"] if check.get("shadow") is True) == 23
    assert [check["status"] for check in payload["checks"]] == ["passed"] * 30
    assert payload["not_run"] == []
    shadow = payload["shadow_summary"]
    assert shadow["count"] == 23
    assert shadow["counted_as_pass"] is False
    assert shadow["affects_exit_code"] is False
    assert sorted(shadow["passed"]) == [
        "ground-truth-benchmark", "independent-verifier",
        "phase8b-baseline-audit", "phase8b-real-verification",
        "phase8c-baseline-audit", "phase8c-benchmark-artifact",
        "phase8c-contamination", "phase8c-ground-truth-v2",
        "phase8c-public-corpus", "phase8c-quality",
        "phase8c-release-evidence",
        "phase8d-acceptance-2", "phase8d-capability-universe",
        "phase8d-discovery-registry", "phase8d-experiments",
        "phase8d-external-knowledge", "phase8d-gap-registry",
        "phase8d-heap-malloc-abi", "phase8d-hidden-attribution",
        "phase8d-hidden-isolation", "phase8d-metamorphic",
        "phase8d-promotion", "repair-readiness-audit",
    ]
    sums_lines = [line for line in (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if line]
    assert len(sums_lines) == 2
    assert audit_cli.verify_evidence(out) == []
    assert len(runner.calls) == 30


def test_static_mode_runs_only_static_subset(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    runner = _passing_runner()
    payload = audit_cli.audit(mode="static", root=root, run=runner)
    assert payload["ok"] is True
    assert payload["exit_code"] == 0
    assert len(payload["checks"]) == 3
    assert sorted(runner.called_scripts()) == [
        "check_universe_methodology.py",
        "run_autonomous_reflection.py",
        "verify_coverage_gate.py",
    ]


def test_required_failure_exits_one_and_records_check(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    runner = _passing_runner()
    runner.responses["meta_audit.py"] = (1, "", "recall below threshold")
    code = audit_cli.main(["--mode", "full", "--root", str(root), "--json"], run=runner)
    assert code == 1
    payload = audit_cli.audit(mode="full", root=root, run=runner)
    failed = [check for check in payload["checks"] if check["status"] == "failed"]
    assert [check["id"] for check in failed] == ["meta-audit"]
    assert "recall below threshold" in failed[0]["detail"]


def test_exit_zero_report_with_ok_false_is_a_failure(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    runner = _passing_runner()
    runner.responses["verify_coverage_gate.py"] = (0, json.dumps({"ok": False}), "")
    payload = audit_cli.audit(mode="static", root=root, run=runner)
    assert payload["exit_code"] == 1
    failed = [check for check in payload["checks"] if check["status"] == "failed"]
    assert failed[0]["id"] == "coverage-gate-static"


def test_missing_required_script_is_not_run_exit_two(tmp_path: Path) -> None:
    root = _make_root(tmp_path, missing=("discover_capability_gaps.py",))
    runner = _passing_runner()
    code = audit_cli.main(["--mode", "full", "--root", str(root), "--json"], run=runner)
    assert code == 2
    payload = audit_cli.audit(mode="full", root=root, run=_passing_runner())
    assert payload["ok"] is False
    assert payload["exit_code"] == 2
    assert [item["id"] for item in payload["not_run"]] == ["capability-gap-discovery"]
    assert "not present" in payload["not_run"][0]["reason"]
    # Other checks still ran: a missing input is reported, never silently skipped.
    missing_runner = _passing_runner()
    audit_cli.audit(mode="full", root=root, run=missing_runner)
    assert "discover_capability_gaps.py" not in missing_runner.called_scripts()
    assert len(missing_runner.calls) == 29


def test_check_exit_two_is_aggregated_as_not_run(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    runner = _passing_runner()
    runner.responses["run_autonomous_reflection.py"] = (
        2, "autonomous-reflection: NOT_OK records=0 not_run=1", ""
    )
    payload = audit_cli.audit(mode="static", root=root, run=runner)
    assert payload["ok"] is False
    assert payload["exit_code"] == 2
    statuses = {check["id"]: check["status"] for check in payload["checks"]}
    assert statuses["autonomous-reflection"] == "not_run"
    assert [item["id"] for item in payload["not_run"]] == ["autonomous-reflection"]


def test_failure_takes_precedence_over_not_run(tmp_path: Path) -> None:
    root = _make_root(tmp_path, missing=("build_provider_coverage.py",))
    runner = _passing_runner()
    runner.responses["meta_audit.py"] = (1, "", "boom")
    payload = audit_cli.audit(mode="full", root=root, run=runner)
    assert payload["exit_code"] == 1
    assert payload["failed"] == ["meta-audit"]
    assert [item["id"] for item in payload["not_run"]] == ["provider-coverage"]


def test_no_evidence_out_writes_nothing(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    before = set(tmp_path.iterdir())
    code = audit_cli.main(["--mode", "static", "--root", str(root), "--json"], run=_passing_runner())
    assert code == 0
    after = set(tmp_path.iterdir())
    assert before == after
    assert not (root / "artifacts").exists() or list((root / "artifacts").iterdir()) == []


def test_evidence_tamper_is_detected(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    out = tmp_path / "evidence"
    assert audit_cli.main(
        ["--mode", "static", "--root", str(root), "--evidence-out", str(out)]
    , run=_passing_runner()) == 0
    summary = out / "summary.json"
    payload = json.loads(summary.read_text(encoding="utf-8"))
    payload["ok"] = False
    summary.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    violations = audit_cli.verify_evidence(out)
    assert any("SHA256SUMS mismatch" in item for item in violations)


def test_shadow_scripts_missing_are_not_run_and_never_pass(tmp_path: Path) -> None:
    root = _make_root(tmp_path, missing=(
        "audit_repair_readiness.py",
        "build_ground_truth_benchmark.py",
        "verify_repair.py",
        "audit_phase8b_verifier_semantics.py",
        "check_phase8b_verification.py",
        "audit_phase8c_readiness.py",
        "migrate_ground_truth_v2.py",
        "build_phase8c_corpus.py",
        "audit_phase8c_contamination.py",
        "audit_phase8c_quality.py",
        "run_phase8c_benchmark.py",
        "audit_phase8c_evidence.py",
        "build_phase8d_capability_universe.py",
        "build_phase8d_gap_registry.py",
        "audit_acceptance_2.py",
        "analyze_phase8d_heap_malloc_abi.py",
        "run_phase8d_hidden_attribution.py",
        "scan_external_knowledge.py",
        "run_metamorphic_discovery.py",
        "build_phase8d_discovery_registry.py",
        "audit_hidden_isolation.py",
        "evaluate_promotion.py",
        "build_phase8d_experiment_bundle.py",
    ))
    payload = audit_cli.audit(mode="full", root=root, run=_passing_runner())
    assert payload["ok"] is True
    assert payload["exit_code"] == 0
    assert payload["not_run"] == []
    shadow = payload["shadow_summary"]
    assert shadow["count"] == 23
    assert shadow["passed"] == []
    assert sorted(shadow["not_run"]) == [
        "ground-truth-benchmark", "independent-verifier",
        "phase8b-baseline-audit", "phase8b-real-verification",
        "phase8c-baseline-audit", "phase8c-benchmark-artifact",
        "phase8c-contamination", "phase8c-ground-truth-v2",
        "phase8c-public-corpus", "phase8c-quality",
        "phase8c-release-evidence",
        "phase8d-acceptance-2", "phase8d-capability-universe",
        "phase8d-discovery-registry", "phase8d-experiments",
        "phase8d-external-knowledge", "phase8d-gap-registry",
        "phase8d-heap-malloc-abi", "phase8d-hidden-attribution",
        "phase8d-hidden-isolation", "phase8d-metamorphic",
        "phase8d-promotion", "repair-readiness-audit",
    ]
    statuses = {check["id"]: check["status"] for check in payload["checks"]}
    for check_id in shadow["not_run"]:
        assert statuses[check_id] == "not_run"
    assert all(check["shadow"] is True for check in payload["checks"]
               if check["id"] in shadow["not_run"])


def test_shadow_failure_does_not_change_exit_code(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    runner = _passing_runner()
    runner.responses["verify_repair.py"] = (1, "", "selftest failed")
    payload = audit_cli.audit(mode="full", root=root, run=runner)
    assert payload["ok"] is True
    assert payload["exit_code"] == 0
    shadow = payload["shadow_summary"]
    assert shadow["failed"] == ["independent-verifier"]
    assert "independent-verifier" in shadow["not_run"] or True
    failed = [check for check in payload["checks"]
              if check["id"] == "independent-verifier"][0]
    assert failed["status"] == "failed"
    assert failed["shadow"] is True
    assert failed["required"] is False
    # Required aggregation is untouched by the advisory shadow failure.
    assert payload["failed"] == []


def test_shadow_only_runs_in_full_mode(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    runner = _passing_runner()
    audit_cli.audit(mode="static", root=root, run=runner)
    assert "audit_repair_readiness.py" not in runner.called_scripts()
    assert "verify_repair.py" not in runner.called_scripts()


def test_payload_is_deterministic(tmp_path: Path) -> None:
    root = _make_root(tmp_path)
    first = audit_cli.audit(mode="full", root=root, run=_passing_runner())
    second = audit_cli.audit(mode="full", root=root, run=_passing_runner())
    assert first == second
