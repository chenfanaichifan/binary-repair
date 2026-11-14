"""Tests for the coverage regression gate (fast, deterministic, no network)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import verify_coverage_gate as gate  # noqa: E402


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
        "detector": "test",
        "lead_ref": "",
        "novel": False,
    }


def _claims(ids: list[str]) -> dict:
    return {
        "non_goals": [
            {
                "id": gap_id,
                "category": "non_goal",
                "enforcement": "unsupported",
                "claim": "test claim",
                "owner": "test-owner",
                "review_by": "2027-01-31",
                "productization_criteria": "test criteria",
                "fallback": "test fallback",
            }
            for gap_id in ids
        ]
    }


def _universe() -> dict:
    cell = {
        "container": "elf", "arch": "x86_64", "bits": "64",
        "endian": "little", "strategy": "guard",
        "sink_class": "unbounded_copy", "destination_kind": "stack",
        "evidence_profile": "emulated_instruction",
        "runtime_tier": "emulated_run", "provider": "deterministic",
        "proof_scope": "target_scoped", "status": "supported",
        "reason": "test cell", "claims_non_goal_id": "",
    }
    return {
        "cells": [cell],
        "dimensions": {key: [cell[key]] for key in (
            "container", "arch", "bits", "endian", "strategy", "sink_class",
            "destination_kind", "evidence_profile", "runtime_tier",
            "provider", "proof_scope")},
        "statuses": ["verified", "supported", "non_goal", "unavailable",
                     "unknown"],
        "counts": {"verified": 0, "supported": 1, "non_goal": 0,
                   "unavailable": 0, "unknown": 0},
        "cell_count": 1,
        "unknown": 0,
        "unmapped_non_goal_ids": [],
        "missing_reason_count": 0,
        "missing_reason_cells": [],
    }


def _audit(gaps: list[dict]) -> dict:
    return {"gaps": gaps, "mode": "static", "universe": _universe()}


def test_real_tree_static_gate_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_coverage_gate.py"),
         "--static-only"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "coverage-gate: mode=static" in result.stdout
    assert "violations=0" in result.stdout


def test_evaluate_detects_detector_error() -> None:
    summary = gate.evaluate(
        _audit([_gap("GM-detector-error::claims_docs", "open", "medium")]),
        _claims([]), "")
    assert summary["violations"]
    assert any("detector error" in item for item in summary["violations"])


def test_evaluate_detects_high_severity_open() -> None:
    summary = gate.evaluate(
        _audit([_gap("EG-something", "open", "high")]),
        _claims([]), "")
    assert any("high-severity" in item for item in summary["violations"])


def test_allowlist_accepts_known_residual_and_rejects_new() -> None:
    allowed = ("EG-target-scope",)
    measured = [
        _gap("EG-target-scope", "open", "medium"),
        _gap("NG-dummy", "non_goal", "info", "non_goal"),
    ]
    ok = gate.evaluate(_audit(measured), _claims(["NG-dummy"]), "",
                       allowed_open=allowed)
    assert ok["violations"] == []
    bad = gate.evaluate(
        _audit([_gap("EG-new-open", "open", "medium"),
                _gap("NG-dummy", "non_goal", "info", "non_goal")]),
        _claims(["NG-dummy"]), "", allowed_open=allowed)
    assert any("ALLOWED_OPEN" in item for item in bad["violations"])


def test_unmapped_non_goal_is_a_violation_and_doc_or_claims_maps_it() -> None:
    audit = _audit([_gap("NG-test-1", "non_goal", "info", "non_goal")])
    unmapped = gate.evaluate(audit, _claims(["NG-other"]), "")
    assert any("not mapped" in item for item in unmapped["violations"])
    via_claims = gate.evaluate(audit, _claims(["NG-test-1"]), "")
    assert via_claims["violations"] == []
    via_doc = gate.evaluate(
        _audit([_gap("NG-test-1", "non_goal", "info", "non_goal"),
                _gap("NG-other", "non_goal", "info", "non_goal")]),
        _claims(["NG-other"]), "see NG-test-1 in this page")
    assert via_doc["violations"] == []


def test_claims_structure_validation() -> None:
    compact = {"non_goals": [{"id": "NG-x"}]}
    summary = gate.evaluate(_audit([]), compact, "")
    assert any("missing fields" in item for item in summary["violations"])
    not_a_list = {"non_goals": {"id": "NG-x"}}
    summary = gate.evaluate(_audit([]), not_a_list, "")
    assert any("non_goals" in item for item in summary["violations"])
    summary = gate.evaluate(_audit([]), None, "")
    assert any("claims.json" in item for item in summary["violations"])


def test_local_allowlist_must_be_tight_and_acceptance_required(tmp_path: Path) -> None:
    allowed = ("EG-target-scope", "RG-closed-now")
    audit = _audit([_gap("EG-target-scope", "open", "medium")])
    summary = gate.evaluate(audit, _claims([]), "", allowed_open=allowed,
                            local=True)
    assert any("no longer measured open" in item for item in summary["violations"])
    missing = gate.check_acceptance(tmp_path / "missing.json")
    assert missing
    passed = tmp_path / "passed.json"
    passed.write_text(json.dumps({"passed": True, "failures": []}), encoding="utf-8")
    assert gate.check_acceptance(passed) == []
    failed = tmp_path / "failed.json"
    failed.write_text(json.dumps({"passed": False}), encoding="utf-8")
    assert gate.check_acceptance(failed)


def test_cli_injected_bad_audit_fails(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(_audit([
        _gap("GM-detector-error::x", "open", "medium"),
        _gap("EG-new-open", "open", "low"),
    ])), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_coverage_gate.py"),
         "--audit-json", str(audit_path),
         "--claims", str(ROOT / "docs" / "status" / "claims.json"),
         "--non-goals", str(ROOT / "docs" / "acceptance"
                            / "non-goals-2026-11-14.md")],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode != 0
    assert "VIOLATION" in result.stdout


def test_manifest_route_detection_ignores_signature_declaration() -> None:
    """A `poc_manifest: ... = None` parameter is not a routing guard."""
    from app.services import coverage_audit

    source = """
def repair_any(
    data: bytes,
    *,
    poc_manifest: dict[str, Any] | None = None,
    verify: bool = True,
) -> RepairOutcome:
    # Repair any input.
    container = detect_container(data)
    from app.services.binary_repair_engine import repair_elf
    patched, raw = repair_elf(data)
    report = _from_elf_legacy(container, data, patched, raw, verify=verify,
                              external_poc=poc_manifest)
    return report


def _from_elf_legacy(container, data, patched, raw, *, verify,
                     external_poc=None):
    if external_poc is not None:
        report.limitations.append("cannot consume it")
    return report


def _select_runtime(data, container, sink):
    return None
"""
    evidence = coverage_audit._manifest_route_evidence(source)
    assert evidence["routed"] is False
    assert evidence["disclosed"] is True
    assert "poc_manifest is not None" not in evidence["guard_patterns"]


def test_manifest_route_detection_requires_guard_before_legacy_engine() -> None:
    """A real control-flow guard that routes before repair_elf is measured."""
    from app.services import coverage_audit

    source = """
def repair_any(
    data: bytes,
    *,
    poc_manifest: dict[str, Any] | None = None,
    verify: bool = True,
) -> RepairOutcome:
    # Repair any input.
    container = detect_container(data)
    if poc_manifest is not None:
        return _attempt_capacity(data, container, poc_manifest=poc_manifest)
    from app.services.binary_repair_engine import repair_elf
    patched, raw = repair_elf(data)
    return patched


def _from_elf_legacy(container, data, patched, raw, *, verify,
                     external_poc=None):
    return None


def _select_runtime(data, container, sink):
    return None
"""
    evidence = coverage_audit._manifest_route_evidence(source)
    assert evidence["routed"] is True
    assert evidence["guard_position"] < evidence["legacy_position"]
    assert "_attempt_capacity" in evidence["route_helpers"]
    assert "return" in evidence["route_helpers"]


def test_repo_claims_parse_and_preserve_invariants() -> None:
    claims = json.loads((ROOT / "docs" / "status" / "claims.json")
                        .read_text(encoding="utf-8"))
    assert claims["product_paths"] == ["asm_roundtrip", "binary_direct"]
    assert "not universal repair" in claims["scope"]
    assert any("paradigm A" in item
               for item in claims["explicitly_unimplemented"])
    ids, violations = gate.claims_non_goal_ids(claims)
    assert not violations
    assert len(ids) == 12  # 11 coverage claims + host-dependent Mach-O external PoC


def test_dynamic_unverified_is_allowed_static_but_rejected_local() -> None:
    audit = _audit([_gap("EG-target-scope", "dynamic_unverified")])
    static = gate.evaluate(audit, _claims([]), "", local=False)
    assert not any("dynamic_unverified" in item
                   for item in static["violations"])
    local = gate.evaluate(audit, _claims([]), "", local=True)
    assert any("dynamic_unverified_count==0" in item
               for item in local["violations"])


def test_universe_unknown_or_unmapped_is_a_violation() -> None:
    audit = _audit([])
    audit["universe"]["unknown"] = 2
    result = gate.evaluate(audit, _claims([]), "")
    assert any("unknown count" in item for item in result["violations"])

    audit = _audit([])
    cell = dict(audit["universe"]["cells"][0])
    cell.update({"status": "non_goal", "reason": "reserved",
                 "claims_non_goal_id": "NG-not-in-claims"})
    audit["universe"]["cells"] = [cell]
    audit["universe"]["counts"] = {"verified": 0, "supported": 0,
                                   "non_goal": 1, "unavailable": 0,
                                   "unknown": 0}
    result = gate.evaluate(audit, _claims([]), "")
    assert any("claims.json non_goals" in item for item in result["violations"])


def test_claims_productization_fields_are_required() -> None:
    audit = _audit([_gap("NG-x", "non_goal", "info", "non_goal")])
    claims = _claims(["NG-x"])
    del claims["non_goals"][0]["owner"]
    result = gate.evaluate(audit, claims, "")
    assert any("missing fields" in item for item in result["violations"])

    claims = _claims(["NG-x"])
    claims["non_goals"][0]["review_by"] = "2028-01-01"
    result = gate.evaluate(audit, claims, "")
    assert any("review_by" in item for item in result["violations"])


def test_static_gate_json_exposes_phase3_sections() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_coverage_gate.py"),
         "--static-only", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["dynamic_unverified_count"] >= 1
    assert payload["universe"]["unknown"] == 0
    assert payload["meta_audit"]["ok"] is True
    assert payload["meta_audit"]["recall"] >= 0.8
    assert payload["invariants"]["ok"] is True
    assert payload["invariants"]["packets_checked"] > 0
    assert payload["acceptance"]["ok"] is True


def test_meta_audit_and_invariants_runners_are_exposed() -> None:
    meta = gate.run_meta_audit_check()
    assert meta["ok"] is True and meta["passed"] is True
    invariants = gate.run_invariant_check()
    assert invariants["ok"] is True
    assert invariants["packets_checked"] > 0


def _live_doc_with_runtime(tier: str, available: bool) -> dict:
    audit = _audit([_gap("NG-x", "non_goal", "info", "non_goal")])
    audit["summary"] = {"gap_count": 1}
    audit["census"] = {
        "runtime_sources": {
            "sources": [{
                "format": "elf", "arch": "x86_64",
                "runtime_tier": tier, "available": available,
            }]
        }
    }
    return audit


def test_stale_artifact_mismatch_is_rejected() -> None:
    live = _live_doc_with_runtime("emulated_run", True)
    tampered = json.loads(json.dumps(live))
    tampered["summary"] = {"gap_count": 2}
    tampered["universe"]["cell_count"] = 99
    tampered["universe"]["unknown"] = 3
    result = gate.check_stale_artifacts(
        live, committed_override=tampered, verify_sums=False)
    assert result["ok"] is False
    assert any("gap_count" in item for item in result["mismatches"])
    assert any("universe_cell_count" in item for item in result["mismatches"])
    equal = gate.check_stale_artifacts(
        live, committed_override=json.loads(json.dumps(live)),
        verify_sums=False)
    assert equal["ok"] is True


def test_stale_artifact_checksums_are_verified(tmp_path: Path) -> None:
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir()
    matrix = audit_dir / "coverage-matrix.json"
    matrix.write_text('{"mode": "static"}', encoding="utf-8")
    report = audit_dir / "gap-report.md"
    report.write_text("# report\n", encoding="utf-8")
    checksums = []
    for name in ("coverage-matrix.json", "gap-report.md"):
        digest = gate._sha256_file(audit_dir / name)
        checksums.append(f"{digest}  {name}")
    sums = audit_dir / "SHA256SUMS"
    sums.write_text("\n".join(checksums) + "\n", encoding="utf-8")
    ok, mismatches = gate.verify_artifact_sums(audit_dir)
    assert ok, mismatches
    report.write_text("# tampered report\n", encoding="utf-8")
    ok, mismatches = gate.verify_artifact_sums(audit_dir)
    assert not ok
    assert any("sha256 mismatch" in item for item in mismatches)


def test_claims_measurement_sync_detects_drift() -> None:
    live = _audit([
        _gap("N-ok", "non_goal", "info", "non_goal"),
        _gap("C-ok", "closed"),
    ])
    live["summary"] = {"gap_count": 2}
    block = {
        "gap_count": 2, "closed": 1, "open": 0, "mitigated": 0,
        "non_goal": 1, "dynamic_unverified": 0, "high_severity_open": 0,
        "universe_cell_count": 1, "universe_unknown": 0,
    }
    claims = _claims(["N-ok"])
    claims["audit_status"] = {"mode": "release", "static": dict(block),
                              "release": dict(block)}
    assert gate.check_claims_sync(live, claims)["ok"] is True
    drifted = json.loads(json.dumps(claims))
    drifted["audit_status"]["static"]["gap_count"] = 99
    result = gate.check_claims_sync(live, drifted)
    assert result["ok"] is False
    assert any("gap_count" in item for item in result["mismatches"])
    missing = _claims(["N-ok"])
    result = gate.check_claims_sync(live, missing)
    assert result["ok"] is False
    assert result["audit_status_present"] is False


def test_claims_measurement_sync_requires_matching_blocks(tmp_path: Path) -> None:
    # A present audit_status without the block for the live mode fails closed.
    live = _audit([_gap("N-ok", "non_goal", "info", "non_goal")])
    live["summary"] = {"gap_count": 1}
    claims = _claims(["N-ok"])
    claims["audit_status"] = {"mode": "release", "release": {}}
    result = gate.check_claims_sync(live, claims)
    assert result["ok"] is False
    assert result["block"] == "static"
    assert any("absent" in item for item in result["mismatches"])


def test_provider_identity_mismatch_is_recorded_non_verified(tmp_path: Path) -> None:
    mismatch_path = tmp_path / "provider.json"
    mismatch_path.write_text(json.dumps({
        "provider_status": "ok",
        "provider": {
            "status": "ok", "model_identity_ok": False,
            "model_requested": "deepseek-chat",
            "model_returned": "deepseek-flash",
        },
    }), encoding="utf-8")
    result = gate.check_provider_identity(mismatch_path)
    assert result["ok"] is True
    assert result["identity_mismatch"] is True
    assert result["identity_recorded"] is True
    assert result["identity_verified"] is False
    assert "NON-VERIFIED IDENTITY" in result["reason"]
    verified_path = tmp_path / "provider_verified.json"
    payload = json.loads(mismatch_path.read_text(encoding="utf-8"))
    payload["provider"]["model_identity_ok"] = True
    verified_path.write_text(json.dumps(payload), encoding="utf-8")
    verified = gate.check_provider_identity(verified_path)
    assert verified["identity_mismatch"] is False
    assert verified["identity_verified"] is True


def test_fabricated_capability_is_rejected_when_tier_unmeasured() -> None:
    claims = _claims(["N-ok"])
    audit = _live_doc_with_runtime("emulated_run", True)
    universe = gate._as_dict(audit["universe"])
    universe["counts"] = {"verified": 0, "supported": 1, "non_goal": 0,
                          "unavailable": 0, "unknown": 0}
    document = gate.evaluate(audit, claims, "N-ok mapped")
    assert not any("fabricates capabilities" in item
                   for item in document["violations"])
    audit["census"]["runtime_sources"]["sources"][0]["available"] = False
    document = gate.evaluate(audit, claims, "N-ok mapped")
    assert any("fabricates capabilities" in item
               for item in document["violations"])


def test_static_gate_json_exposes_release_checks() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_coverage_gate.py"),
         "--static-only", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert "stale_artifacts" in payload
    assert set(payload["stale_artifacts"]) >= {"ok", "mismatches",
                                               "committed_sha"}
    assert "claims_sync" in payload
    assert set(payload["claims_sync"]) >= {"ok", "mismatches"}
    assert "provider_identity" in payload
    assert payload["provider_identity"]["identity_recorded"] is True
    assert payload["meta_audit"]["scenario_count"] >= 12


def test_meta_audit_check_runs_with_live_audit() -> None:
    from app.services import coverage_audit

    live = coverage_audit.build_audit(include_probes=False)
    report = gate.run_meta_audit_check(live)
    assert report["ok"] is True, report["violations"]
    assert report["scenario_count"] >= 12


def test_roadmap_id_parser_reads_table_rows() -> None:
    text = """
## Roadmap

| id | productization |
|---|---|
| `NG-a` | fix later |
| `RG-external-poc::<doc>::pe/arm64` | runner |
| not-an-id | x |
"""
    ids = gate.parse_roadmap_ids(text)
    assert ids == ["NG-a", "RG-external-poc::<doc>::pe/arm64"]


def test_roadmap_sync_requires_exact_id_equality(tmp_path: Path) -> None:
    claims = _claims(["NG-ok", "NG-second"])
    live = _audit([
        _gap("NG-ok", "non_goal", "info", "non_goal"),
        _gap("NG-second", "non_goal", "info", "non_goal"),
    ])
    live["summary"] = {"gap_count": 2}
    roadmap = tmp_path / "roadmap.md"
    roadmap.write_text(
        "| id | x |\n|---|---|\n| `NG-ok` | a |\n| `NG-second` | b |\n",
        encoding="utf-8")
    ok = gate.check_roadmap_sync(live, claims, roadmap)
    assert ok["ok"] is True, ok["mismatches"]
    assert ok["ids"] == ["NG-ok", "NG-second"]
    roadmap.write_text(
        "| id | x |\n|---|---|\n| `NG-ok` | a |\n| `NG-other` | b |\n",
        encoding="utf-8")
    drifted = gate.check_roadmap_sync(live, claims, roadmap)
    assert drifted["ok"] is False
    assert any("roadmap ids" in item for item in drifted["mismatches"])


def test_roadmap_sync_missing_document_is_explicit(tmp_path: Path) -> None:
    live = _audit([_gap("NG-ok", "non_goal", "info", "non_goal")])
    live["summary"] = {"gap_count": 1}
    result = gate.check_roadmap_sync(live, _claims(["NG-ok"]),
                                     tmp_path / "missing.md")
    assert result["ok"] is False
    assert result["present"] is False
    assert any("missing" in item for item in result["mismatches"])


def test_release_evidence_and_ci_claim_helpers() -> None:
    evidence = {
        "mode": "release", "ok": True,
        "release_sha": "a" * 40, "frozen_sha": "a" * 40, "violations": [],
        "checks": [{"id": "targeted-pytest", "status": "passed",
                    "required": True}],
    }
    complete = {
        **evidence,
        "provenance": {"artifact_sha256": "cd" * 32,
                       "lima_identity": "runner=lima:limactl"},
    }
    assert gate.check_release_evidence(complete)["ok"] is True
    mismatched = json.loads(json.dumps(complete))
    mismatched["frozen_sha"] = "b" * 40
    result = gate.check_release_evidence(mismatched)
    assert result["ok"] is False
    assert any("frozen_sha" in item for item in result["mismatches"])
    no_provenance = gate.check_release_evidence(evidence)
    assert no_provenance["ok"] is False
    assert any("provenance" in item for item in no_provenance["mismatches"])
    ci_bad = gate.check_ci_evidence_claim({
        "mode": "ci", "ci_run_url": "",
        "checks": [{"id": "coverage-gate-local", "status": "passed"}],
    })
    assert ci_bad["ok"] is False
    ci_ok = gate.check_ci_evidence_claim({
        "mode": "ci",
        "ci_run_url": "https://github.com/example/repo/actions/runs/1",
        "checks": [{"id": "coverage-gate-static", "status": "passed"}],
    })
    assert ci_ok["ok"] is True


def test_static_gate_json_exposes_roadmap_sync() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_coverage_gate.py"),
         "--static-only", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert "roadmap_sync" in payload
    assert set(payload["roadmap_sync"]) >= {"ok", "ids", "mismatches",
                                            "present"}
    assert payload["meta_audit"]["scenario_count"] >= 18


def _hosted_ci(**overrides: object) -> dict:
    hosted = {
        "run_id": 43614759619,
        "head_sha": "a" * 40,
        "gated_sha": "a" * 40,
        "run_url": "https://github.com/example/repo/actions/runs/1",
        "conclusion": "success",
    }
    hosted.update(overrides)
    return hosted


def test_release_claims_ci_evidence_v2() -> None:
    claims = {
        "release_sha": "a" * 40,
        "latest_verified_ci": {"run_id": 43614759619, "head_sha": "a" * 40},
        "ci_evidence": {"hosted_ci": _hosted_ci()},
    }
    result = gate.check_release_claims(claims)
    assert result["ok"] is True, result["mismatches"]
    missing = gate.check_release_claims({})
    assert missing["ok"] is False
    assert any("ci_evidence" in item for item in missing["mismatches"])


def test_release_claims_docs_only_delta_and_history_masquerade() -> None:
    docs_delta = {
        "from_sha": "a" * 40,
        "to_sha": "b" * 40,
        "paths": ["docs/status/claims.json", "README.md"],
    }
    claims = {
        "release_sha": "b" * 40,
        "ci_evidence": {"hosted_ci": _hosted_ci(
            head_sha="b" * 40, gated_sha="a" * 40,
            docs_only_delta=docs_delta)},
    }
    assert gate.check_release_claims(claims)["ok"] is True
    claims["ci_evidence"]["hosted_ci"]["docs_only_delta"] = {
        "from_sha": "a" * 40, "to_sha": "b" * 40,
        "paths": ["scripts/release_gate.py"],
    }
    bad_delta = gate.check_release_claims(claims)
    assert bad_delta["ok"] is False
    assert any("non-docs" in item for item in bad_delta["mismatches"])
    claims["ci_evidence"]["hosted_ci"] = _hosted_ci(
        head_sha="a" * 40, gated_sha="a" * 40)
    claims["release_sha"] = "b" * 40
    masquerade = gate.check_release_claims(claims)
    assert masquerade["ok"] is False
    assert any("historical SHA" in item for item in masquerade["mismatches"])


def test_release_claims_self_hosted_and_local_gate() -> None:
    not_run = {"ci_evidence": {"self_hosted_nightly": {"status": "not_run"}}}
    missing_signoff = gate.check_release_claims(not_run)
    assert missing_signoff["ok"] is False
    assert any("signoff" in item for item in missing_signoff["mismatches"])
    local_claim = {
        "ci_evidence": {
            "hosted_ci": _hosted_ci(),
            "local_gate": {"used_as_ci": True},
        }
    }
    local_result = gate.check_release_claims(local_claim)
    assert local_result["ok"] is False
    assert any("local_gate" in item for item in local_result["mismatches"])
    latest_mismatch = {
        "latest_verified_ci": {"run_id": 2, "head_sha": "c" * 40},
        "ci_evidence": {"hosted_ci": _hosted_ci()},
    }
    latest_result = gate.check_release_claims(latest_mismatch)
    assert latest_result["ok"] is False
    assert any("latest_verified_ci" in item
               for item in latest_result["mismatches"])


def test_release_claims_self_hosted_signoff_file(tmp_path: Path) -> None:
    signoff = tmp_path / "signoff.txt"
    signoff.write_text("operator: release\nreason: lima unavailable\n",
                       encoding="utf-8")
    claims = {
        "self_hosted_signoff": str(signoff),
        "ci_evidence": {"self_hosted_nightly": {"status": "not_run"}},
    }
    result = gate.check_release_claims(claims, root=tmp_path)
    assert result["ok"] is True, result["mismatches"]


def test_release_evidence_provenance_incomplete_and_branch_drift() -> None:
    evidence = {
        "mode": "release", "ok": True,
        "release_sha": "a" * 40, "frozen_sha": "a" * 40,
        "checks": [{"id": "targeted-pytest", "status": "passed",
                    "required": True}],
        "provenance": {"artifact_sha256": "cd" * 32},
    }
    partial = gate.check_release_evidence(evidence)
    assert partial["ok"] is False
    assert any("incomplete" in item for item in partial["mismatches"])
    evidence["provenance"]["lima_identity"] = "runner=lima:limactl"
    assert gate.check_release_evidence(evidence)["ok"] is True
    evidence["branch"] = "workbench-v3"
    evidence["provenance"]["branch"] = "stale-branch"
    drift = gate.check_release_evidence(evidence)
    assert drift["ok"] is False
    assert any("branch drift" in item for item in drift["mismatches"])


def test_universe_methodology_gate_wrapper() -> None:
    from app.services import coverage_audit

    live = coverage_audit.build_audit(include_probes=False)
    result = gate.check_universe_methodology(live)
    assert result["ok"] is True, result["mismatches"]
    assert result["cell_count"] >= 8
    assert result["unknown"] == 0
    assert len(result["registry_sha256"]) == 64
    tampered = json.loads(json.dumps(live))
    cells = tampered["universe"]["cells"]
    for cell in cells:
        if cell.get("status") == "supported":
            cell["sink_class"] = "audit_unregistered_sink"
            break
    bad = gate.check_universe_methodology(tampered)
    assert bad["ok"] is False
    assert bad["unexplained_cells"]


def test_static_gate_json_exposes_phase6_sections() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_coverage_gate.py"),
         "--static-only", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert "release_claims_sync" in payload
    assert set(payload["release_claims_sync"]) >= {"ok", "mismatches"}
    assert "universe_methodology" in payload
    assert set(payload["universe_methodology"]) >= {
        "ok", "registry_sha256", "cell_count", "unknown",
        "missing_registry_entries", "unexplained_cells"}
    assert payload["universe_methodology"]["ok"] is True
    assert payload["universe_methodology"]["unknown"] == 0
    assert payload["meta_audit"]["scenario_count"] >= 22
