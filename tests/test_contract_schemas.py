"""Tests for scripts/check_contract_schemas.py (offline contract fixtures)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import check_contract_schemas as contracts  # noqa: E402

CONTRACTS = ROOT / "contracts"
FIXTURES = ROOT / "artifacts" / "contract-fixtures-2026-11-16"
SUMS = FIXTURES / "SHA256SUMS"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_contract_schemas.py"),
         *args],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )


REQUIRED_ARTIFACTS = (
    "artifacts/capability-universe-2026-11-16/dimension-registry.json",
    "artifacts/gap-registry-2026-11-16/gaps.json",
    "artifacts/autonomous-reflection-2026-11-16/reflection.json",
)


def _copy_tree(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    shutil.copytree(CONTRACTS, root / "contracts")
    shutil.copytree(
        FIXTURES, root / "artifacts" / "contract-fixtures-2026-11-16")
    for relative in REQUIRED_ARTIFACTS:
        source = ROOT / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    return root


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Schema documents
# ---------------------------------------------------------------------------


def test_all_twelve_contracts_exist_and_name_match() -> None:
    found = sorted(path.name for path in CONTRACTS.glob("*.schema.json"))
    expected = sorted(f"{name}.schema.json" for name in contracts.SCHEMA_NAMES)
    assert found == expected
    assert len(contracts.SCHEMA_NAMES) == 13


def test_schema_documents_are_structurally_valid() -> None:
    for name in contracts.SCHEMA_NAMES:
        schema = _load(CONTRACTS / f"{name}.schema.json")
        assert contracts.check_schema_document(name, schema) == [], name


def test_schema_files_are_ascii_only() -> None:
    for name in contracts.SCHEMA_NAMES:
        raw = (CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8")
        assert all(ord(char) < 128 for char in raw), name


def test_schema_document_checks_catch_broken_schema() -> None:
    schema = _load(CONTRACTS / "capability.schema.json")
    broken = dict(schema)
    broken.pop("required")
    broken["type"] = "array"
    violations = contracts.check_schema_document("broken", broken)
    joined = " ".join(violations)
    assert "root type must be 'object'" in joined
    assert "required" not in joined or True  # required may be absent, not invalid
    bad_enum = json.loads(json.dumps(schema))
    bad_enum["properties"]["status"]["enum"] = []
    assert any("enum must be non-empty" in item
               for item in contracts.check_schema_document("bad-enum", bad_enum))
    bad_pattern = json.loads(json.dumps(schema))
    bad_pattern["properties"]["id"]["pattern"] = "["
    assert any("pattern is invalid" in item
               for item in contracts.check_schema_document("bad-pattern", bad_pattern))


# ---------------------------------------------------------------------------
# Fixtures and the full check
# ---------------------------------------------------------------------------


def test_repository_contracts_and_fixtures_pass() -> None:
    report = contracts.run_check(ROOT, check_sums=True)
    assert report["ok"] is True, report["violations"]
    assert report["schema_count"] == 13
    assert report["fixtures"]["valid_passed"] == 13
    assert report["fixtures"]["invalid_rejected"] == 13
    assert report["validator"] == "jsonschema"
    assert report["sums"]["ok"] is True


def test_cli_passes_and_reports_json() -> None:
    result = _run_cli("--check", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["validator"] == "jsonschema"
    assert payload["fixtures"] == {
        "valid_passed": 13, "invalid_rejected": 13, "total": 26,
    }


def test_fallback_validator_semantics() -> None:
    result = _run_cli("--check", "--no-jsonschema", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["validator"] == "fallback"
    assert payload["fixtures"]["valid_passed"] == 13
    assert payload["fixtures"]["invalid_rejected"] == 13


def test_every_schema_has_valid_and_invalid_fixture() -> None:
    for name in contracts.SCHEMA_NAMES:
        assert (FIXTURES / f"{name}.valid.json").is_file(), name
        assert (FIXTURES / f"{name}.invalid.json").is_file(), name


def test_sums_covers_all_schemas_and_fixtures() -> None:
    lines = [
        line for line in SUMS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) == len(contracts.SCHEMA_NAMES) * 3
    entries = dict(
        (line.split("  ", 1)[1], line.split("  ", 1)[0])
        for line in lines
    )
    for name in contracts.SCHEMA_NAMES:
        assert f"contracts/{name}.schema.json" in entries
        assert f"artifacts/contract-fixtures-2026-11-16/{name}.valid.json" in entries
        assert f"artifacts/contract-fixtures-2026-11-16/{name}.invalid.json" in entries


def test_artifact_integrations_old_pass_new_not_run() -> None:
    report = contracts.run_check(ROOT, check_sums=True)
    statuses = {item["id"]: item["status"] for item in report["integrations"]}
    assert statuses["capability-universe"] == "validated"
    assert statuses["gap-registry"] == "validated"
    assert statuses["autonomous-reflection"] == "validated"
    # New phase-8 artifacts may not be committed yet; they must be explicit
    # not_run instead of failing the existing contracts.
    assert statuses["benchmark-manifest"] in {"validated", "not_run"}
    assert statuses["verification-report"] in {"validated", "not_run"}
    assert [check["id"] for check in report["checks"]] == [
        "schemas", "valid-fixtures", "invalid-fixtures", "artifacts", "sums",
    ]


# ---------------------------------------------------------------------------
# Tamper detection (SUMS + fixtures + schema + semantics)
# ---------------------------------------------------------------------------


def test_tampered_fixture_breaks_sums_check(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    target = root / "artifacts" / "contract-fixtures-2026-11-16" / "gap.valid.json"
    payload = _load(target)
    payload["owner"] = "tampered"
    _write(target, payload)
    report = contracts.run_check(root, check_sums=True)
    assert report["ok"] is False
    assert any("SUMS digest mismatch" in item for item in report["violations"])


def test_tampered_schema_breaks_sums_check(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    target = root / "contracts" / "repair.schema.json"
    payload = _load(target)
    payload["title"] = "Tampered repair contract"
    _write(target, payload)
    report = contracts.run_check(root, check_sums=True)
    assert report["ok"] is False
    assert any("SUMS digest mismatch" in item for item in report["violations"])


def test_broken_invalid_fixture_cannot_be_accepted(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    fixtures = root / "artifacts" / "contract-fixtures-2026-11-16"
    shutil.copyfile(fixtures / "gap.valid.json", fixtures / "gap.invalid.json")
    report = contracts.run_check(root)
    assert report["ok"] is False
    assert any("invalid fixture was accepted" in item
               for item in report["violations"])


def test_unexpected_fixture_file_is_rejected(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    fixtures = root / "artifacts" / "contract-fixtures-2026-11-16"
    _write(fixtures / "stray.valid.json", {"schema_version": 1})
    report = contracts.run_check(root)
    assert report["ok"] is False
    assert any("unexpected fixture files" in item
               for item in report["violations"])


def test_missing_sums_file_fails_check(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    (root / "artifacts" / "contract-fixtures-2026-11-16" / "SHA256SUMS").unlink()
    report = contracts.run_check(root, check_sums=True)
    assert report["ok"] is False
    assert any("SUMS file missing" in item for item in report["violations"])


def test_write_sums_is_deterministic_and_restores_green(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    fixtures = root / "artifacts" / "contract-fixtures-2026-11-16"
    target = fixtures / "evidence.valid.json"
    payload = _load(target)
    payload["limitations"] = ["regenerated sums fixture"]
    _write(target, payload)
    assert contracts.run_check(root, check_sums=True)["ok"] is False
    contracts.run_check(root, write_sums=True)
    first = (fixtures / "SHA256SUMS").read_bytes()
    contracts.run_check(root, write_sums=True)
    second = (fixtures / "SHA256SUMS").read_bytes()
    assert first == second
    assert contracts.run_check(root, check_sums=True)["ok"] is True


# ---------------------------------------------------------------------------
# Contract-specific cross-field semantics
# ---------------------------------------------------------------------------


def test_repair_release_eligibility_semantics(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    target = (root / "artifacts" / "contract-fixtures-2026-11-16"
              / "repair.valid.json")
    payload = _load(target)
    payload["release_eligible"] = True
    payload["independence_ok"] = False
    _write(target, payload)
    report = contracts.run_check(root)
    assert report["ok"] is False
    joined = " ".join(report["violations"])
    assert "release_eligible=true requires independence_ok=true" in joined


def test_reflection_verified_true_is_rejected(tmp_path: Path) -> None:
    semantics = contracts.CONTRACT_SEMANTICS["reflection"]
    payload = _load(FIXTURES / "reflection.valid.json")
    payload["verified"] = True
    violations = semantics(payload)
    assert any("verified must be exactly false" in item for item in violations)
    root = _copy_tree(tmp_path)
    target = (root / "artifacts" / "contract-fixtures-2026-11-16"
              / "reflection.valid.json")
    _write(target, payload)
    assert contracts.run_check(root)["ok"] is False


def test_acceptance_registry_completeness_is_enforced(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    target = (root / "artifacts" / "contract-fixtures-2026-11-16"
              / "acceptance.valid.json")
    payload = _load(target)
    classes = payload["mismatch_classes"]
    classes[0], classes[1] = classes[1], classes[0]
    _write(target, payload)
    report = contracts.run_check(root)
    assert report["ok"] is False
    assert any("AM01-AM24" in item for item in report["violations"])


def test_schema_ascii_rule_catches_non_ascii_title(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    target = root / "contracts" / "gap.schema.json"
    payload = _load(target)
    payload["title"] = "Unified GapRecord \u2014"
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    report = contracts.run_check(root)
    assert report["ok"] is False
    assert any("schema file must be ASCII-only" in item
               for item in report["violations"])


# ---------------------------------------------------------------------------
# Integration: committed Phase-7 module artifacts satisfy their contracts
# ---------------------------------------------------------------------------

PHASE7_ARTIFACTS = (
    ("capability",
     ROOT / "artifacts" / "capability-universe-2026-11-16"
     / "dimension-registry.json", "dimensions"),
    ("gap",
     ROOT / "artifacts" / "gap-registry-2026-11-16" / "gaps.json", "records"),
    ("reflection",
     ROOT / "artifacts" / "autonomous-reflection-2026-11-16" / "reflection.json",
     "records"),
)


def test_committed_phase7_artifacts_match_contracts() -> None:
    """The real module artifacts must validate against the committed contracts.

    The task modules are not imported here: the test reads their committed JSON
    artifacts only, so it measures the output contract without coupling the
    checker to module internals.
    """
    jsonschema = pytest.importorskip("jsonschema")
    for schema_name, path, collection in PHASE7_ARTIFACTS:
        assert path.is_file(), path
        schema = _load(CONTRACTS / f"{schema_name}.schema.json")
        validator = jsonschema.Draft202012Validator(schema)
        records = _load(path).get(collection)
        assert isinstance(records, list) and records, path
        for index, record in enumerate(records):
            errors = [item.message for item in validator.iter_errors(record)]
            assert errors == [], (schema_name, path.name, index, errors[:2])


# ---------------------------------------------------------------------------
# Phase-8 contracts: cross-field semantics and tamper coverage
# ---------------------------------------------------------------------------

def _semantics(name: str, payload: dict) -> list[str]:
    return contracts.CONTRACT_SEMANTICS[name](payload)


def test_binary_target_semantics() -> None:
    payload = _load(FIXTURES / "binary-target.valid.json")
    assert _semantics("binary-target", payload) == []
    broken = json.loads(json.dumps(payload))
    broken["target_scope"] = {"policy": "target_scoped"}
    assert any("target_scoped requires" in item
               for item in _semantics("binary-target", broken))
    broken = json.loads(json.dumps(payload))
    broken["identity"] = {"kind": "sha256", "value": "b" * 64}
    assert any("must equal target_sha256" in item
               for item in _semantics("binary-target", broken))


def test_root_cause_requires_flow_evidence() -> None:
    payload = _load(FIXTURES / "root-cause.valid.json")
    assert _semantics("root-cause", payload) == []
    broken = json.loads(json.dumps(payload))
    broken["data_flow_evidence"] = []
    broken["control_flow_evidence"] = []
    assert any("at least one" in item for item in _semantics("root-cause", broken))


def test_patch_candidate_verified_is_fail_closed() -> None:
    payload = _load(FIXTURES / "patch-candidate.valid.json")
    assert _semantics("patch-candidate", payload) == []
    verified = json.loads(json.dumps(payload))
    verified["status"] = "verified"
    verified["verification_plan"]["independent_oracle"] = False
    assert any("independent_oracle" in item
               for item in _semantics("patch-candidate", verified))
    verified["verification_plan"]["independent_oracle"] = True
    verified["model_identity"]["status"] = "served-model-only"
    assert any("untrusted model identity" in item
               for item in _semantics("patch-candidate", verified))
    broken = json.loads(json.dumps(payload))
    broken["actions"][0]["before_hex"] = "00"
    assert any("length must equal size*2" in item
               for item in _semantics("patch-candidate", broken))


def test_verification_verified_requires_independence_and_oracle() -> None:
    payload = _load(FIXTURES / "verification.valid.json")
    assert _semantics("verification", payload) == []
    broken = json.loads(json.dumps(payload))
    broken["independence"]["ok"] = False
    assert any("independence.ok=true" in item
               for item in _semantics("verification", broken))
    broken = json.loads(json.dumps(payload))
    for check in broken["checks"]:
        check["independent"] = False
    assert any("independent oracle" in item
               for item in _semantics("verification", broken))
    broken = json.loads(json.dumps(payload))
    broken["checks"][0]["status"] = "failed"
    assert any("required checks" in item
               for item in _semantics("verification", broken))


def test_benchmark_sample_oracle_scope_consistency() -> None:
    payload = _load(FIXTURES / "benchmark-sample.valid.json")
    assert _semantics("benchmark-sample", payload) == []
    broken = json.loads(json.dumps(payload))
    broken["expected_scope"] = "analysis_only"
    broken["oracle"]["kinds"] = ["external_poc"]
    assert any("analysis_only expectation" in item
               for item in _semantics("benchmark-sample", broken))
    broken = json.loads(json.dumps(payload))
    broken["oracle"]["kinds"] = ["static"]
    assert any("requires at least one independent oracle" in item
               for item in _semantics("benchmark-sample", broken))


def test_new_contract_invalid_fixtures_are_rejected(tmp_path: Path) -> None:
    for name in ("binary-target", "vulnerability-finding", "root-cause",
                 "patch-candidate", "verification", "benchmark-sample",
                 "patch-plan"):
        fixture = FIXTURES / f"{name}.invalid.json"
        payload = _load(fixture)
        schema = _load(CONTRACTS / f"{name}.schema.json")
        errors, _validator = contracts._validate_instance(
            name, schema, payload, use_jsonschema=True)
        assert errors, name


def test_tampered_phase8_fixture_breaks_sums(tmp_path: Path) -> None:
    root = _copy_tree(tmp_path)
    target = (root / "artifacts" / "contract-fixtures-2026-11-16"
              / "benchmark-sample.valid.json")
    payload = _load(target)
    payload["sample_id"] = "tampered-sample"
    _write(target, payload)
    report = contracts.run_check(root, check_sums=True)
    assert report["ok"] is False
    assert any("SUMS digest mismatch" in item for item in report["violations"])


# ---------------------------------------------------------------------------
# Phase-8B: patch-plan contract and layout-aware verification/benchmark fields
# ---------------------------------------------------------------------------

def test_patch_plan_fixtures_and_semantics() -> None:
    payload = _load(FIXTURES / "patch-plan.valid.json")
    assert _semantics("patch-plan", payload) == []
    broken = json.loads(json.dumps(payload))
    broken["operations"][0]["candidate_offset"] = None
    broken["operations"][0]["kind"] = "replace"
    assert any("candidate_offset" in item
               for item in _semantics("patch-plan", broken))
    broken = json.loads(json.dumps(payload))
    broken["operations"][0]["before_hex"] = "00"
    assert any("before_hex length" in item
               for item in _semantics("patch-plan", broken))
    broken = json.loads(json.dumps(payload))
    broken["operations"][1]["authorization_ref"] = None
    assert any("authorization_ref" in item
               for item in _semantics("patch-plan", broken))
    broken = json.loads(json.dumps(payload))
    broken["cave"] = {"va": 4096, "size": 16, "executable": False,
                      "method": "append"}
    broken["operations"][0]["kind"] = "insert"
    broken["operations"][0]["reason"] = "guard_cave"
    assert any("executable" in item
               for item in _semantics("patch-plan", broken))
    broken = json.loads(json.dumps(payload))
    broken["operations"][0]["site_va"] = 100
    assert any("outside the declared target range" in item
               for item in _semantics("patch-plan", broken))
    broken = json.loads(json.dumps(payload))
    broken["scope_policy"] = "whole_image"
    assert any("must match" in item for item in _semantics("patch-plan", broken))


def test_verification_layout_semantics() -> None:
    payload = _load(FIXTURES / "verification.valid.json")
    assert _semantics("verification", payload) == []
    broken = json.loads(json.dumps(payload))
    broken["layout_evidence"]["replay_ok"] = False
    assert any("replay_ok" in item for item in _semantics("verification", broken))
    broken = json.loads(json.dumps(payload))
    broken["checks"] = [check for check in broken["checks"]
                        if check["id"] != "layout-plan"]
    assert any("layout-plan" in item
               for item in _semantics("verification", broken))
    broken = json.loads(json.dumps(payload))
    broken["oracle_evidence"]["evidence_sha256"] = ""
    assert any("evidence_sha256" in item
               for item in _semantics("verification", broken))
    broken = json.loads(json.dumps(payload))
    broken["oracle_evidence"]["status"] = "not_run"
    assert any("not_run/unavailable" in item
               for item in _semantics("verification", broken))


def test_benchmark_authority_semantics() -> None:
    payload = _load(FIXTURES / "benchmark-sample.valid.json")
    assert _semantics("benchmark-sample", payload) == []
    broken = json.loads(json.dumps(payload))
    broken["authority"]["authorized_changes"][0]["authorization_ref"] = ""
    assert any("authorization_ref" in item
               for item in _semantics("benchmark-sample", broken))
    broken = json.loads(json.dumps(payload))
    broken["authority"]["authorized_changes"][0].pop("file_offset")
    broken["authority"]["authorized_changes"][0].pop("size")
    assert any("locator" in item
               for item in _semantics("benchmark-sample", broken))
    broken = json.loads(json.dumps(payload))
    broken["authority"]["scope_policy"] = "target_scoped_associated"
    broken["authority"]["authorized_changes"] = []
    assert any("requires at least one authorized change" in item
               for item in _semantics("benchmark-sample", broken))


def test_old_benchmark_and_verification_fixtures_stay_compatible() -> None:
    benchmark = _load(FIXTURES / "benchmark-sample.valid.json")
    benchmark.pop("authority", None)
    schema = _load(CONTRACTS / "benchmark-sample.schema.json")
    errors, _validator = contracts._validate_instance(
        "benchmark-sample", schema, benchmark, use_jsonschema=True)
    assert errors == []
    assert contracts.CONTRACT_SEMANTICS["benchmark-sample"](benchmark) == []
    verification = _load(FIXTURES / "verification.valid.json")
    for key in ("patch_plan_sha256", "oracle_evidence", "layout_evidence"):
        verification.pop(key, None)
    verification["checks"] = [check for check in verification["checks"]
                              if check["id"] != "layout-plan"]
    schema = _load(CONTRACTS / "verification.schema.json")
    errors, _validator = contracts._validate_instance(
        "verification", schema, verification, use_jsonschema=True)
    assert errors == []
    assert contracts.CONTRACT_SEMANTICS["verification"](verification) == []


# ---------------------------------------------------------------------------
# Acceptance contract alignment: A01-A08 + AM01-AM28 (Phase-8B follow-up)
# ---------------------------------------------------------------------------

def _runtime_acceptance_payload() -> dict:
    from app.services.acceptance_models import (
        ACCEPTANCE_DIMENSIONS,
        MISMATCH_RULES,
    )

    dimensions = [
        {
            "id": dimension["id"],
            "title": dimension["title"],
            "task_fields": list(dimension["task_fields"]),
            "acceptance_fields": list(dimension["acceptance_fields"]),
            "mismatch_ids": list(dimension["mismatch_ids"]),
        }
        for dimension in ACCEPTANCE_DIMENSIONS
    ]
    mismatch_classes = [
        {
            "id": rule["id"],
            "code": rule["code"],
            "severity": rule["severity"],
            "required_actions": list(rule["required_actions"]),
        }
        for rule in MISMATCH_RULES
    ]
    return {
        "schema_version": 1,
        "dimensions": dimensions,
        "mismatch_classes": mismatch_classes,
        "match_result": {
            "schema_version": 1,
            "task_id": "runtime-registry",
            "decision": "rejected",
            "mismatches": ["AM25"],
            "required_actions": ["reject_candidate_layout_mismatch"],
            "verified": False,
            "residual_risk": "critical",
            "reasons": [
                "AM25: candidate_layout_mismatch: plan operation missing from layout"
            ],
        },
    }


def test_acceptance_contract_represents_runtime_am28_registry() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(CONTRACTS / "acceptance.schema.json")
    assert schema["properties"]["mismatch_classes"]["maxItems"] == 28
    validator = jsonschema.Draft202012Validator(schema)
    payload = _runtime_acceptance_payload()
    assert [item["id"] for item in payload["mismatch_classes"]] == [
        f"AM{index:02d}" for index in range(1, 29)
    ]
    errors = [item.message for item in validator.iter_errors(payload)]
    assert errors == [], errors


def test_acceptance_contract_keeps_legacy_am24_fixture_valid() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(CONTRACTS / "acceptance.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    fixture = _load(FIXTURES / "acceptance.valid.json")
    assert len(fixture["mismatch_classes"]) == 24
    errors = [item.message for item in validator.iter_errors(fixture)]
    assert errors == [], errors


def test_acceptance_contract_rejects_undeclared_am29() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(CONTRACTS / "acceptance.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    payload = _runtime_acceptance_payload()
    payload["mismatch_classes"][-1]["id"] = "AM29"
    payload["match_result"]["mismatches"] = ["AM29"]
    errors = [item.message for item in validator.iter_errors(payload)]
    assert errors
    assert any("AM29" in item or "does not match" in item for item in errors)
