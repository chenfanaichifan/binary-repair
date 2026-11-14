"""Tests for the staged release/nightly gate (mocked artifacts, no network).

The gate's real ``--pr``/``--release``/``--nightly`` runs are intentionally
expensive (static+local audit probes, full pytest, real Lima guest).  These
tests exercise the mode logic and validators with injected subprocess results
and fabricated-but-consistent artifacts, so they run in ~1s and never touch the
network or a browser.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import release_gate as gate  # noqa: E402
from release_gate import Check, Paths, RunResult  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / fake artifacts
# ---------------------------------------------------------------------------


def _gap(gap_id: str, status: str, severity: str = "info",
         category: str = "engine_gap") -> dict:
    return {
        "gap_id": gap_id,
        "category": category,
        "severity": severity,
        "status": status,
        "symptom": "test gap",
        "evidence": ["test:evidence"],
        "next_step": "none",
    }


def _audit(gaps: list[dict]) -> dict:
    return {"gaps": gaps, "mode": "static"}


def _claims(ids: list[str]) -> dict:
    return {
        "schema_version": 1,
        "scope": "bounded, evidence-gated binary repair; not universal repair",
        "product_paths": ["asm_roundtrip", "binary_direct"],
        "non_goals": [
            {
                "id": gap_id,
                "category": "non_goal",
                "enforcement": "analysis_only; no candidate",
                "claim": "test claim",
            }
            for gap_id in ids
        ],
    }


def _static_gate_summary(**overrides) -> str:
    payload = {
        "mode": "static",
        "ok": True,
        "violations": [],
        "open_gap_ids": [],
        "non_goal_gap_ids": ["NG-a"],
        "allowed_open": [],
        "dynamic_unverified_count": 3,
        "dynamic_unverified_gap_ids": ["EG-capacity-strategy"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def _local_gate_summary(**overrides) -> str:
    payload = {
        "mode": "local",
        "ok": True,
        "violations": [],
        "open_gap_ids": [],
        "non_goal_gap_ids": ["NG-a"],
        "allowed_open": [],
        "dynamic_unverified_count": 0,
        "dynamic_unverified_gap_ids": [],
        "universe": {
            "ok": True,
            "unknown": 0,
            "cell_count": 8,
            "counts": {"verified": 3, "supported": 2, "non_goal": 3},
            "non_goal_count": 3,
            "unmapped_non_goal_ids": [],
            "missing_reason_count": 0,
        },
        "meta_audit": {
            "ok": True,
            "passed": True,
            "recall": 1.0,
            "precision": 1.0,
            "violations": [],
            "scenario_count": 5,
        },
        "invariants": {
            "ok": True,
            "violations": [],
            "packets_checked": 7,
            "limitations": [],
        },
        "acceptance": {"ok": True, "violations": []},
    }
    payload.update(overrides)
    return json.dumps(payload)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _acceptance_payload(**overrides) -> dict:
    payload = {
        "generated_by": "tests",
        "passed": True,
        "failures": [],
        "marcx_review_api": {
            "decision": {"success": True, "outcome": "success_within_scope"},
            "checks_failed": [],
            "checks_not_run": [],
            "runtime_tier": "emulated_run",
        },
        "marcx_pipeline_with_manifest": {
            "strategy": "capacity",
            "with_manifest": True,
            "disposition": "verified_patch",
            "verified": True,
            "download_allowed": True,
            "gate_outcome": "success_within_scope",
            "candidate_sha256": "a" * 64,
        },
        "marcx_pipeline_without_manifest": {
            "strategy": "capacity",
            "with_manifest": False,
            "verified": False,
            "download_allowed": False,
            "candidate_sha256": None,
        },
        "heap_pipeline_with_manifest": {
            "strategy": "guard",
            "with_manifest": True,
            "disposition": "verified_patch",
            "verified": True,
            "download_allowed": True,
            "gate_outcome": "success_within_scope",
            "candidate_sha256": "b" * 64,
        },
        "heap_pipeline_without_manifest": {
            "strategy": "guard",
            "with_manifest": False,
            "verified": False,
            "download_allowed": False,
            "candidate_sha256": None,
        },
        "heap_target_scoped": {
            "target": "heap_bad",
            "strategy": "guard",
            "with_manifest": True,
            "disposition": "verified_patch",
            "verified": True,
            "download_allowed": True,
            "gate_outcome": "success_within_scope",
            "target_scope_check": "passed",
            "target_scope": {"name": "heap_bad", "va": 0x401130, "end": 0x40116C},
            "candidate_sha256": "c" * 64,
        },
        "heap_wrong_target": {
            "target": "main",
            "verified": False,
            "download_allowed": False,
            "candidate_present": False,
        },
    }
    payload.update(overrides)
    return payload


def _write_acceptance(path: Path, **overrides) -> dict:
    payload = _acceptance_payload(**overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return payload


def _write_provider_matrix(
    root: Path,
    *,
    cases: int = 12,
    provider_status: str = "ok",
    unavailable_reason: str | None = None,
    tamper: bool = False,
    drop_field: str | None = None,
) -> Path:
    artifact = root / "artifacts" / "provider-matrix-2026-11-14"
    per_case = artifact / "per-case"
    per_case.mkdir(parents=True, exist_ok=True)
    (artifact / "README.md").write_text(
        "# Provider matrix evidence (test fixture)\n", encoding="utf-8"
    )
    case_rows: list[dict] = []
    per_case_names: list[str] = []
    ai_verified = provider_status == "ok" and False
    for index in range(cases):
        case_id = f"case-{index:02d}"
        record = {
            "case_id": case_id,
            "family": "test",
            "input_sha256": f"{index:064x}",
            "provider": "deepseek" if provider_status == "ok" else None,
            "model": "deepseek-chat" if provider_status == "ok" else None,
            "seed": None,
            "cost": None,
            "elapsed_ms": 12,
            "target_policy": "target_scoped",
            "target_scope": {"name": "heap_bad", "va": 0x401130},
            "target_scope_check": "passed",
            "target_in_scope": True,
            "baseline_whole_image": {"disposition": "verified_patch"},
            "baseline_target_strict": {
                "disposition": "verified_patch",
                "verified": True,
                "expected": "verified_patch",
                "matches_expected": True,
                "target_scope": {"name": "heap_bad", "va": 0x401130},
                "target_in_scope": True,
                "actions": 1,
            },
            "reference_fix": {"status": "reference"},
            "ai_target": {
                "attempted": provider_status == "ok",
                "status": "not_attempted" if provider_status != "ok" else "ok",
                "verified": bool(ai_verified),
            },
            "inconclusive_reasons": [],
            "limitations": [],
        }
        if drop_field:
            record.pop(drop_field, None)
        path = per_case / f"{case_id}.json"
        path.write_text(json.dumps(record), encoding="utf-8")
        per_case_names.append(f"per-case/{case_id}.json")
        case_rows.append({
            "case_id": case_id,
            "family": "test",
            "input_sha256": record["input_sha256"],
            "baseline_whole_image_disposition": "verified_patch",
            "baseline_target_strict_disposition": "verified_patch",
            "baseline_target_strict_expected": "verified_patch",
            "baseline_target_strict_matches_expected": True,
            "target_scope_resolved": True,
            "target_in_scope": True,
            "reference_status": "reference",
            "ai_status": "not_attempted",
            "ai_verified": bool(ai_verified),
            "elapsed_ms": 12,
        })
    summary = {
        "schema_version": 1,
        "kind": "provider_matrix",
        "generated_at": "2026-11-14T00:00:00Z",
        "command": "test",
        "provider": {"requested": "reference", "provider": None},
        "provider_status": provider_status,
        "unavailable_reason": unavailable_reason,
        "seed": None,
        "cost": None,
        "elapsed_ms": 12,
        "aggregate": {
            "target_strict_pass_rate": 0.75,
            "target_in_scope_rate": 1.0,
            "target_scope_resolved": 12,
            "cases": cases,
        },
        "target_strict_pass_rate": 0.75,
        "target_in_scope_rate": 1.0,
        "cases": case_rows,
        "limitations": [],
        "notes": [],
    }
    summary_path = artifact / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    files = ["README.md", "summary.json", *per_case_names]
    sums_lines = []
    for name in files:
        digest = _sha((artifact / name).read_bytes())
        sums_lines.append(f"{digest}  {name}")
    (artifact / "SHA256SUMS").write_text("\n".join(sums_lines) + "\n",
                                         encoding="utf-8")
    if tamper:
        summary_path.write_text(
            json.dumps({**summary, "notes": ["tampered after hashing"]}),
            encoding="utf-8",
        )
    return artifact


def _write_claims_docs(root: Path, audit: dict) -> None:
    claims = _claims(["NG-a"])
    path = root / "docs" / "status" / "claims.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(claims), encoding="utf-8")
    doc = root / "docs" / "acceptance" / "non-goals-2026-11-14.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("| NG-a | mapped non goal |\n", encoding="utf-8")


def _green_audit() -> dict:
    return _audit([
        _gap("EG-closed", "closed"),
        _gap("NG-a", "non_goal", category="non_goal"),
        _gap("EG-dynamic", "dynamic_unverified"),
    ])


def _write_tree(root: Path) -> Paths:
    """Create the minimal files the release layer reads (scripts are faked)."""
    paths = Paths(root)
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "verify_coverage_gate.py").write_text(
        "# fake coverage gate placeholder (subprocess is faked in tests)\n",
        encoding="utf-8",
    )
    _write_claims_docs(root, _green_audit())
    _write_acceptance(paths.acceptance)
    (root / "artifacts" / "coverage-closure-2026-11-14" / "capture_acceptance.py").write_text(
        "# fake acceptance capture placeholder (subprocess is faked in tests)\n",
        encoding="utf-8",
    )
    _write_provider_matrix(root)
    tests = root / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_release_gate.py").write_text("def test_dummy():\n    pass\n",
                                                encoding="utf-8")
    return paths


def _dispatcher(
    *,
    static: str | None = None,
    local: str | None = None,
    meta: str | None = None,
    pytest_rc: int = 0,
    capture: str | None = None,
):
    """Fake subprocess runner dispatching on the argv of each check."""

    def run(argv, cwd, timeout):
        joined = " ".join(str(part) for part in argv)
        if "verify_coverage_gate.py" in joined:
            if "--local" in argv:
                return RunResult(0, local if local is not None
                                 else _local_gate_summary(), "")
            return RunResult(0, static if static is not None
                             else _static_gate_summary(), "")
        if "meta_audit.py" in joined:
            return RunResult(0, meta if meta is not None else json.dumps(
                {"ok": True, "violations": [], "recall": 1.0,
                 "precision": 1.0, "scenario_count": 5}), "")
        if "capture_acceptance.py" in joined:
            if capture is not None:
                return RunResult(1, "", capture)
            target = Path(str(argv[1])).parent / "acceptance.json"
            target.write_text(json.dumps(_acceptance_payload()), encoding="utf-8")
            return RunResult(0, "captured", "")
        if "-m" in argv and "pytest" in argv:
            return RunResult(pytest_rc, "", "" if pytest_rc == 0 else "pytest failed")
        return RunResult(0, "", "")

    return run


# ---------------------------------------------------------------------------
# Static gate / claims measurement (PR layer pieces)
# ---------------------------------------------------------------------------


def test_static_gate_allows_dynamic_unverified_and_reports_it(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts" / "verify_coverage_gate.py").write_text("# fake\n")
    check = gate.check_static_coverage_gate(
        paths, _dispatcher(static=_static_gate_summary(dynamic_unverified_count=5))
    )
    assert check.status == gate.CHECK_PASSED
    assert "dynamic_unverified=5" in check.detail


def test_static_gate_fails_on_violation(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "scripts" / "verify_coverage_gate.py").write_text("# fake\n")
    check = gate.check_static_coverage_gate(
        paths,
        _dispatcher(static=_static_gate_summary(
            ok=False, violations=["non_goal id not mapped: NG-x"])),
    )
    assert check.status == gate.CHECK_FAILED
    assert any("NG-x" in violation for violation in check.violations)


def test_claims_measurement_green_with_dynamic_rows(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    _write_claims_docs(tmp_path, _green_audit())
    check = gate.check_claims_measurement(
        paths, build_audit=lambda **kwargs: _green_audit()
    )
    assert check.status == gate.CHECK_PASSED
    assert "dynamic_unverified=1" in check.detail


def test_claims_measurement_fails_on_open_gap(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    audit = _audit([_gap("EG-open", "open", severity="medium")])
    _write_claims_docs(tmp_path, audit)
    check = gate.check_claims_measurement(paths, build_audit=lambda **kwargs: audit)
    assert check.status == gate.CHECK_FAILED
    assert any("open gaps" in violation for violation in check.violations)


def test_claims_measurement_fails_on_matrix_claim_mismatch(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    audit = _audit([
        _gap("NG-a", "non_goal", category="non_goal"),
        _gap("MM-stale-claim", "mitigated", category="matrix_claim_mismatch"),
    ])
    _write_claims_docs(tmp_path, audit)
    check = gate.check_claims_measurement(paths, build_audit=lambda **kwargs: audit)
    assert check.status == gate.CHECK_FAILED
    assert any("matrix/claim" in violation for violation in check.violations)


def test_claims_measurement_fails_on_detector_error(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    audit = _audit([_gap("GM-detector-error::claims_docs", "closed")])
    _write_claims_docs(tmp_path, audit)
    check = gate.check_claims_measurement(paths, build_audit=lambda **kwargs: audit)
    assert check.status == gate.CHECK_FAILED
    assert any("detector error" in violation for violation in check.violations)


def test_claims_measurement_fails_on_unmapped_non_goal(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    audit = _audit([_gap("NG-unmapped", "non_goal", category="non_goal")])
    _write_claims_docs(tmp_path, audit)
    check = gate.check_claims_measurement(paths, build_audit=lambda **kwargs: audit)
    assert check.status == gate.CHECK_FAILED
    assert any("not mapped" in violation for violation in check.violations)


def test_claims_measurement_fails_when_claims_document_missing(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    audit = _green_audit()
    check = gate.check_claims_measurement(paths, build_audit=lambda **kwargs: audit)
    assert check.status == gate.CHECK_FAILED
    assert any("claims.json" in violation for violation in check.violations)


# ---------------------------------------------------------------------------
# Acceptance contract
# ---------------------------------------------------------------------------


def test_acceptance_contract_green(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    _write_acceptance(paths.acceptance)
    check = gate.check_acceptance_contract(paths)
    assert check.status == gate.CHECK_PASSED, check.violations


def test_acceptance_contract_missing_file(tmp_path: Path) -> None:
    check = gate.check_acceptance_contract(Paths(tmp_path))
    assert check.status == gate.CHECK_FAILED
    assert any("unavailable" in violation for violation in check.violations)


def test_acceptance_contract_flags_unpassed_and_missing_roles(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    _write_acceptance(paths.acceptance, passed=False, failures=["marcx failed"])
    violations, _detail = gate.validate_acceptance(
        json.loads(paths.acceptance.read_text(encoding="utf-8"))
    )
    assert any("did not pass" in item for item in violations)


def test_acceptance_contract_flags_verified_control(tmp_path: Path) -> None:
    paths = Paths(tmp_path)
    payload = _write_acceptance(paths.acceptance)
    payload["marcx_pipeline_without_manifest"]["verified"] = True
    payload["marcx_pipeline_without_manifest"]["download_allowed"] = True
    violations, _detail = gate.validate_acceptance(payload)
    assert any("control must not be verified" in item for item in violations)


def test_acceptance_contract_flags_bad_target_scope(tmp_path: Path) -> None:
    payload = _write_acceptance(Paths(tmp_path).acceptance)
    payload["heap_target_scoped"]["target_scope_check"] = "failed"
    payload["heap_target_scoped"]["target_scope"] = {"va": "not-an-int"}
    violations, _detail = gate.validate_acceptance(payload)
    assert any("target-scoped ownership case" in item for item in violations)


def test_acceptance_contract_flags_wrong_target_download(tmp_path: Path) -> None:
    payload = _write_acceptance(Paths(tmp_path).acceptance)
    payload["heap_wrong_target"]["download_allowed"] = True
    payload["heap_wrong_target"]["candidate_present"] = True
    violations, _detail = gate.validate_acceptance(payload)
    assert any("wrong-target control must not allow download" in item
               for item in violations)
    assert any("must not carry a candidate" in item for item in violations)


# ---------------------------------------------------------------------------
# Provider-matrix artifact
# ---------------------------------------------------------------------------


def test_provider_matrix_green(tmp_path: Path) -> None:
    artifact = _write_provider_matrix(tmp_path)
    violations, detail = gate.evaluate_provider_matrix(artifact)
    assert violations == []
    assert detail["cases"] == 12
    assert detail["provider_status"] == "ok"


def test_provider_matrix_missing_dir(tmp_path: Path) -> None:
    violations, _detail = gate.evaluate_provider_matrix(
        tmp_path / "artifacts" / "provider-matrix-2026-11-14"
    )
    assert any("artifact missing" in item for item in violations)


def test_provider_matrix_stale_digest(tmp_path: Path) -> None:
    artifact = _write_provider_matrix(tmp_path, tamper=True)
    violations, _detail = gate.evaluate_provider_matrix(artifact)
    assert any("stale or tampered" in item for item in violations)


def test_provider_matrix_missing_target_strict_field(tmp_path: Path) -> None:
    artifact = _write_provider_matrix(tmp_path, drop_field="target_in_scope")
    violations, _detail = gate.evaluate_provider_matrix(artifact)
    assert any("target-strict fields" in item for item in violations)


def test_provider_matrix_unavailable_requires_reason_and_no_claimed_ai(
    tmp_path: Path,
) -> None:
    artifact = _write_provider_matrix(
        tmp_path, provider_status="unavailable", unavailable_reason=None
    )
    violations, _detail = gate.evaluate_provider_matrix(artifact)
    assert any("unavailable_reason" in item for item in violations)

    good = tmp_path / "good"
    artifact = _write_provider_matrix(
        good, provider_status="unavailable",
        unavailable_reason="provider_error: _ProviderHTTPError(401)",
    )
    violations, _detail = gate.evaluate_provider_matrix(artifact)
    assert violations == []


def test_provider_matrix_wrong_case_count(tmp_path: Path) -> None:
    artifact = _write_provider_matrix(tmp_path, cases=11)
    violations, _detail = gate.evaluate_provider_matrix(artifact)
    assert any("12 case rows" in item for item in violations)


# ---------------------------------------------------------------------------
# Local coverage gate payload evaluation
# ---------------------------------------------------------------------------


def test_local_gate_payload_green() -> None:
    violations, detail = gate.evaluate_local_gate_payload(
        json.loads(_local_gate_summary()), 0
    )
    assert violations == []
    assert detail["universe_unknown"] == 0


def test_local_gate_payload_requires_dynamic_unverified_zero() -> None:
    payload = json.loads(_local_gate_summary(dynamic_unverified_count=2))
    violations, _detail = gate.evaluate_local_gate_payload(payload, 0)
    assert any("dynamic_unverified=2" in item for item in violations)


def test_local_gate_payload_missing_dynamic_field_is_a_violation() -> None:
    payload = json.loads(_local_gate_summary())
    for key in ("dynamic_unverified_count", "dynamic_unverified_gap_ids"):
        payload.pop(key, None)
    violations, _detail = gate.evaluate_local_gate_payload(payload, 0)
    assert any("dynamic_unverified_count" in item for item in violations)


def test_local_gate_payload_universe_and_acceptance_violations() -> None:
    payload = json.loads(_local_gate_summary())
    payload["universe"]["unknown"] = 1
    payload["universe"]["unmapped_non_goal_ids"] = ["NG-x"]
    payload["acceptance"] = {"ok": False, "violations": ["acceptance not passed"]}
    violations, _detail = gate.evaluate_local_gate_payload(payload, 0)
    assert any("universe.unknown=1" in item for item in violations)
    assert any("unmapped non-goal" in item for item in violations)
    assert any("acceptance.ok" in item for item in violations)


# ---------------------------------------------------------------------------
# Mode orchestration
# ---------------------------------------------------------------------------


def test_pr_mode_green(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    summary = gate.run_pr(
        paths,
        run=_dispatcher(),
        build_audit=lambda **kwargs: _green_audit(),
    )
    assert summary.ok, summary.violations
    assert [check.check_id for check in summary.checks] == [
        "static-coverage-gate", "claims-measurement-diff", "targeted-pytest",
    ]


def test_pr_mode_fails_on_static_violation(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    summary = gate.run_pr(
        paths,
        run=_dispatcher(static=_static_gate_summary(
            ok=False, violations=["high-severity open gap"])),
        build_audit=lambda **kwargs: _green_audit(),
    )
    assert not summary.ok
    assert any("high-severity" in violation for violation in summary.violations)


def test_pr_mode_targeted_pytest_requires_an_existing_file(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    (tmp_path / "tests" / "test_release_gate.py").unlink()
    summary = gate.run_pr(
        paths, run=_dispatcher(), build_audit=lambda **kwargs: _green_audit()
    )
    assert not summary.ok
    assert any("targeted" in violation for violation in summary.violations)


def test_release_mode_green(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    summary = gate.run_release(
        paths, run=_dispatcher(), build_audit=lambda **kwargs: _green_audit()
    )
    assert summary.ok, summary.violations
    ids = [check.check_id for check in summary.checks]
    assert ids == [
        "static-coverage-gate", "claims-measurement-diff", "acceptance-contract",
        "local-coverage-gate", "meta-audit", "acceptance-invariants",
        "universe-unknown-zero", "provider-matrix", "full-pytest",
    ]


def test_release_mode_fails_on_missing_acceptance(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    paths.acceptance.unlink()
    summary = gate.run_release(
        paths, run=_dispatcher(), build_audit=lambda **kwargs: _green_audit()
    )
    assert not summary.ok
    assert any("acceptance" in violation for violation in summary.violations)


def test_release_mode_fails_on_stale_provider_matrix(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    _write_provider_matrix(tmp_path, tamper=True)
    summary = gate.run_release(
        paths, run=_dispatcher(), build_audit=lambda **kwargs: _green_audit()
    )
    assert not summary.ok
    assert any("stale or tampered" in violation for violation in summary.violations)


def test_release_mode_fails_on_open_gap(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    audit = _audit([
        _gap("NG-a", "non_goal", category="non_goal"),
        _gap("EG-open", "open", severity="medium"),
    ])
    _write_claims_docs(tmp_path, audit)
    summary = gate.run_release(
        paths, run=_dispatcher(), build_audit=lambda **kwargs: audit
    )
    assert not summary.ok
    assert any("open gaps" in violation for violation in summary.violations)


def test_release_mode_fails_on_invariant_violation(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    local = json.loads(_local_gate_summary())
    local["invariants"] = {"ok": False, "violations": ["tampered check"],
                           "packets_checked": 1, "limitations": []}
    summary = gate.run_release(
        paths, run=_dispatcher(local=json.dumps(local)),
        build_audit=lambda **kwargs: _green_audit(),
    )
    assert not summary.ok
    assert any("invariants" in violation for violation in summary.violations)


def test_release_mode_fails_on_missing_meta_audit(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    local = json.loads(_local_gate_summary())
    local.pop("meta_audit", None)
    summary = gate.run_release(
        paths, run=_dispatcher(local=json.dumps(local)),
        build_audit=lambda **kwargs: _green_audit(),
    )
    assert not summary.ok
    assert any("meta-audit" in violation for violation in summary.violations)


def test_release_mode_fails_on_full_pytest_failure(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    summary = gate.run_release(
        paths, run=_dispatcher(pytest_rc=1),
        build_audit=lambda **kwargs: _green_audit(),
    )
    assert not summary.ok
    assert any("full pytest" in violation for violation in summary.violations)


# ---------------------------------------------------------------------------
# Nightly layer (real-capture branch mocked; unavailable is honest)
# ---------------------------------------------------------------------------


def test_nightly_mode_green_with_available_runner(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    summary = gate.run_nightly(
        paths,
        run=_dispatcher(),
        build_audit=lambda **kwargs: _green_audit(),
        runner_probe=lambda: {"available": True, "runner": "lima:limactl",
                              "tier": "emulated_run", "reason": ""},
    )
    assert summary.ok, summary.violations
    capture = next(
        check for check in summary.checks
        if check.check_id == "nightly-real-lima-acceptance"
    )
    assert capture.status == gate.CHECK_PASSED
    assert "lima:limactl" in capture.detail


def test_nightly_mode_degrades_when_runner_unavailable(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    summary = gate.run_nightly(
        paths,
        run=_dispatcher(),
        build_audit=lambda **kwargs: _green_audit(),
        runner_probe=lambda: {"available": False, "runner": "",
                              "reason": "no guest runner for x86_64"},
    )
    assert summary.ok, summary.violations
    capture = next(
        check for check in summary.checks
        if check.check_id == "nightly-real-lima-acceptance"
    )
    assert capture.status == gate.CHECK_UNAVAILABLE
    assert "no guest runner" in capture.detail
    assert summary.notes and "unavailable" in summary.notes[0]


def test_nightly_mode_fails_when_capture_fails(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    summary = gate.run_nightly(
        paths,
        run=_dispatcher(capture="capture crashed"),
        build_audit=lambda **kwargs: _green_audit(),
        runner_probe=lambda: {"available": True, "runner": "lima:limactl",
                              "tier": "emulated_run", "reason": ""},
    )
    assert not summary.ok
    assert any("acceptance capture failed" in violation
               for violation in summary.violations)


def test_nightly_mode_fails_when_capture_is_not_passing(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)

    def run(argv, cwd, timeout):
        joined = " ".join(str(part) for part in argv)
        if "capture_acceptance.py" in joined:
            target = Path(str(argv[1])).parent / "acceptance.json"
            target.write_text(json.dumps({"passed": False, "failures": ["x"]}),
                              encoding="utf-8")
            return RunResult(0, "", "")
        return _dispatcher()(argv, cwd, timeout)

    summary = gate.run_nightly(
        paths,
        run=run,
        build_audit=lambda **kwargs: _green_audit(),
        runner_probe=lambda: {"available": True, "runner": "lima:limactl",
                              "tier": "emulated_run", "reason": ""},
    )
    assert not summary.ok
    assert any("did not pass" in violation for violation in summary.violations)


# ---------------------------------------------------------------------------
# CLI surface and structured summary
# ---------------------------------------------------------------------------


def test_cli_list_checks_prints_matrix(capsys: pytest.CaptureFixture[str]) -> None:
    assert gate.main(["--list-checks"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == {"pr", "release", "nightly"}
    assert "provider-matrix" in payload["release"]
    assert "nightly-real-lima-acceptance" in payload["nightly"]


def test_cli_requires_a_mode() -> None:
    with pytest.raises(SystemExit) as excinfo:
        gate.main([])
    assert excinfo.value.code == 2


def test_summary_dict_is_structured(tmp_path: Path) -> None:
    paths = _write_tree(tmp_path)
    summary = gate.run_pr(
        paths, run=_dispatcher(), build_audit=lambda **kwargs: _green_audit()
    )
    payload = summary.to_dict()
    assert payload["mode"] == "pr"
    assert payload["ok"] is True
    assert payload["exit_code"] == 0
    assert payload["violations"] == []
    assert {check["id"] for check in payload["checks"]} == {
        "static-coverage-gate", "claims-measurement-diff", "targeted-pytest",
    }
    assert payload["status_counts"]["passed"] == 3


def test_check_helpers_mark_status() -> None:
    check = Check("x", "title")
    assert check.status == gate.CHECK_SKIPPED
    check.fail("boom")
    assert check.status == gate.CHECK_FAILED
    assert check.violations == ["boom"]
    unavailable = Check("y", "title").unavailable("missing")
    assert unavailable.status == gate.CHECK_UNAVAILABLE
