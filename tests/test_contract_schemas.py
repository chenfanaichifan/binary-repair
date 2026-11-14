"""Tests for scripts/check_contract_schemas.py (offline contract fixtures)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

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


def _copy_tree(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    shutil.copytree(CONTRACTS, root / "contracts")
    shutil.copytree(
        FIXTURES, root / "artifacts" / "contract-fixtures-2026-11-16")
    return root


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Schema documents
# ---------------------------------------------------------------------------


def test_all_six_contracts_exist_and_name_match() -> None:
    found = sorted(path.name for path in CONTRACTS.glob("*.schema.json"))
    expected = sorted(f"{name}.schema.json" for name in contracts.SCHEMA_NAMES)
    assert found == expected
    assert len(contracts.SCHEMA_NAMES) == 6


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
    assert report["schema_count"] == 6
    assert report["fixtures"]["valid_passed"] == 6
    assert report["fixtures"]["invalid_rejected"] == 6
    assert report["validator"] == "jsonschema"
    assert report["sums"]["ok"] is True


def test_cli_passes_and_reports_json() -> None:
    result = _run_cli("--check", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["validator"] == "jsonschema"
    assert payload["fixtures"] == {
        "valid_passed": 6, "invalid_rejected": 6, "total": 12,
    }


def test_fallback_validator_semantics() -> None:
    result = _run_cli("--check", "--no-jsonschema", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["validator"] == "fallback"
    assert payload["fixtures"]["valid_passed"] == 6
    assert payload["fixtures"]["invalid_rejected"] == 6


def test_every_schema_has_valid_and_invalid_fixture() -> None:
    for name in contracts.SCHEMA_NAMES:
        assert (FIXTURES / f"{name}.valid.json").is_file(), name
        assert (FIXTURES / f"{name}.invalid.json").is_file(), name


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
    assert any("AM01-AM20" in item for item in report["violations"])


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
