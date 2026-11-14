"""Tests for the unified Gap Registry and the six discovery mechanisms.

Offline and deterministic: the discovery mechanisms run real committed checkers
(subprocess) but never touch the network or a provider.  The tests validate:

* 12 claims non-goals migrate to 12 ``source=claims_non_goal`` records with
  deterministic ids and status ``non_goal``;
* the mitigated ``RG-runtime-evidence::...::native_run`` record exists and is
  the only non-candidate failure-driven baseline record;
* the GapRecord schema rejects duplicates / invalid statuses / missing fields and
  forbids auto-promotion of discovery candidates;
* the discovery artifact contains exactly the expected mechanism adapters:
  knowledge / failure_driven / differential run and produce candidates, while
  mutation / metamorphic / sample_based / knowledge_source_scan are ``not_run``
  with explicit reasons and zero candidates;
* every candidate has a ``proposed_experiment`` (proposed id+steps or explicit
  cannot_plan) and the artifact is reproducible via ``--check`` (tamper
  detection included).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from app.services import gap_registry as gaps  # noqa: E402

import discover_capability_gaps as discovery  # noqa: E402

ARTIFACT = ROOT / "artifacts" / "gap-registry-2026-11-16"
GAPS_PATH = ARTIFACT / "gaps.json"
CANDIDATES_PATH = ARTIFACT / "candidates.json"
README_PATH = ARTIFACT / "README.md"
SUMS_PATH = ARTIFACT / "SHA256SUMS"
ARTIFACT_FILES = ("gaps.json", "candidates.json", "README.md")
MATRIX_PATH = "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json"
CLAIMS_PATH = "docs/status/claims.json"
BUILDER = ROOT / "scripts" / "discover_capability_gaps.py"
PYTHON = sys.executable

EXPECTED_MECHANISMS = (
    "knowledge",
    "failure_driven",
    "differential",
    "mutation",
    "metamorphic",
    "sample_based",
    "knowledge_source_scan",
)
RUN_MECHANISMS = ("knowledge", "failure_driven", "differential")
NOT_RUN_MECHANISMS = ("mutation", "metamorphic", "sample_based", "knowledge_source_scan")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=None)
def _load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry() -> dict:
    assert GAPS_PATH.is_file(), (
        f"missing gap registry artifact {GAPS_PATH}; run "
        "scripts/discover_capability_gaps.py"
    )
    return _load_json(str(GAPS_PATH.relative_to(ROOT)))


@pytest.fixture(scope="module")
def candidates_artifact() -> dict:
    assert CANDIDATES_PATH.is_file(), CANDIDATES_PATH
    return _load_json(str(CANDIDATES_PATH.relative_to(ROOT)))


def _run_builder(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("BINARYREPAIR_ASSISTANT_PROVIDER_KEY", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [PYTHON, str(BUILDER), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=240,
        env=env,
    )


# ---------------------------------------------------------------------------
# Claims migration / mitigated baseline
# ---------------------------------------------------------------------------


def test_twelve_claims_non_goals_migrate_deterministically():
    claims = _load_json(CLAIMS_PATH)
    matrix = _load_json(MATRIX_PATH)
    records = gaps.claim_records(claims)
    assert len(records) == 12
    claim_ids = [item["id"] for item in claims["non_goals"]]
    assert [record["subcategory"] for record in records] == claim_ids
    assert len({record["gap_id"] for record in records}) == 12
    for record, claim in zip(records, claims["non_goals"]):
        assert record["schema_version"] == 1
        assert record["discovery_source"] == "claims_non_goal"
        assert record["status"] == "non_goal"
        assert record["category"] == claim["category"]
        assert record["observed_failure"] == claim["claim"]
        assert record["existing_capability"] == claim["enforcement"]
        assert record["owner"] == claim["owner"]
        assert record["review_by"] == claim["review_by"]
        assert record["evidence_refs"][0].startswith(CLAIMS_PATH)
        assert record["evidence_refs"][1].startswith(MATRIX_PATH)
        assert record["verification_required"] is True
        assert record["false_verified_risk"] in gaps.FALSE_VERIFIED_RISK
        # deterministic id: recomputing gives the same id
        assert record["gap_id"] == gaps.deterministic_gap_id(
            "claims_non_goal", str(claim["id"])
        )
        plan = record["proposed_experiment"]
        assert plan["status"] in gaps.EXPERIMENT_STATUSES
        if plan["status"] == "proposed":
            assert plan["experiment_id"] and plan["steps"]
        else:
            assert plan["reason"]
    with pytest.raises(ValueError):
        gaps.claim_records({"non_goals": []})


def test_mitigated_runtime_evidence_record_is_present():
    matrix = _load_json(MATRIX_PATH)
    records = gaps.mitigated_records(matrix)
    assert len(records) == 1
    record = records[0]
    assert record["gap_id"].startswith("GAP-FAIL-RG-RUNTIME-EVIDENCE")
    assert "NATIVE-RUN" in record["gap_id"]
    assert record["discovery_source"] == "failure_driven"
    assert record["status"] == "resolved"
    assert record["category"] == "runtime_gap"
    assert record["target"]["kind"] == "audit_gap"
    assert record["target"]["gap_id"].startswith(
        "RG-runtime-evidence::elf/x86_64/64/little::native_run"
    )
    assert "mitigated" in record["existing_capability"]
    assert record["verification_required"] is True
    assert record["false_verified_risk"] == "high"
    assert record["proposed_experiment"]["status"] == "proposed"


def test_validate_records_rejects_invalid_and_promoted_records():
    claims = _load_json(CLAIMS_PATH)
    matrix = _load_json(MATRIX_PATH)
    records = gaps.claim_records(claims) + gaps.mitigated_records(matrix)
    assert gaps.validate_records(records)["ok"] is True

    duplicated = records + [dict(records[0])]
    result = gaps.validate_records(duplicated)
    assert result["ok"] is False
    assert any("duplicate" in item for item in result["violations"])

    invalid_status = [dict(record) for record in records]
    invalid_status[0]["status"] = "verified"
    result = gaps.validate_records(invalid_status)
    assert result["ok"] is False
    assert any("invalid status" in item for item in result["violations"])

    missing = [dict(record) for record in records]
    del missing[1]["observed_failure"]
    result = gaps.validate_records(missing)
    assert result["ok"] is False
    assert any("missing fields" in item for item in result["violations"])

    promoted = [dict(record) for record in records]
    promoted[0]["status"] = "candidate"
    result = gaps.validate_records(promoted)
    assert result["ok"] is False
    assert any("claims_non_goal" in item for item in result["violations"])

    bad_plan = [dict(record) for record in records]
    bad_plan[0]["proposed_experiment"] = {"status": "cannot_plan", "reason": ""}
    result = gaps.validate_records(bad_plan)
    assert result["ok"] is False
    assert any("cannot_plan missing reason" in item for item in result["violations"])


def test_candidate_construction_stays_candidate():
    candidate = gaps.make_candidate(
        discovery_source="knowledge",
        key="test:key",
        category="universe_dimension_gap",
        subcategory="D03",
        target={"kind": "dimension", "id": "D03"},
        observed_failure="test gap",
        existing_capability="nothing",
        severity="medium",
        evidence_refs=["docs/status/claims.json#non_goals"],
        plan=gaps.cannot_plan("no experiment"),
        owner="analysis",
        review_by="2027-05-14",
    )
    assert candidate["status"] == "candidate"
    assert candidate["gap_id"] == gaps.deterministic_gap_id("knowledge", "test:key")
    with pytest.raises(ValueError):
        gaps.make_candidate(
            discovery_source="mutation",  # not a runnable source
            key="x",
            category="x",
            subcategory="x",
            target={"kind": "x"},
            observed_failure="x",
            existing_capability="x",
            severity="low",
            evidence_refs=["x"],
            plan=gaps.cannot_plan("x"),
            owner="x",
            review_by="2027-05-14",
        )


# ---------------------------------------------------------------------------
# Artifact contract
# ---------------------------------------------------------------------------


def test_artifact_schema_records_and_ids(registry):
    assert registry["schema_version"] == 1
    assert registry["kind"] == "gap_registry"
    assert registry["no_auto_promotion"] is True
    records = registry["records"]
    assert registry["record_count"] == len(records)
    assert registry["base_record_count"] == 13
    assert registry["candidate_record_count"] == registry["record_count"] - 13
    assert registry["records_by_source"]["claims_non_goal"] == 12
    assert registry["records_by_status"]["non_goal"] == 12
    assert registry["records_by_status"]["resolved"] == 1
    assert registry["records_by_status"]["candidate"] == registry["candidate_record_count"]
    validation = gaps.validate_records(records)
    assert validation["ok"] is True, validation["violations"]
    assert validation["unique_id_count"] == len(records)
    assert [record["gap_id"] for record in records] == sorted(
        record["gap_id"] for record in records
    )
    claim_ids = [item["id"] for item in _load_json(CLAIMS_PATH)["non_goals"]]
    migrated = sorted(
        record["subcategory"] for record in records
        if record["discovery_source"] == "claims_non_goal"
    )
    assert migrated == sorted(claim_ids)
    resolved = [record for record in records if record["status"] == "resolved"]
    assert len(resolved) == 1
    assert resolved[0]["gap_id"].startswith("GAP-FAIL-RG-RUNTIME-EVIDENCE")
    for source in registry["provenance"]["sources"]:
        assert _sha256(ROOT / source["path"]) == source["sha256"]
    assert len(registry["provenance"]["source_digest_sha256"]) == 64


def test_mechanisms_are_real_runs_or_explicit_not_run(candidates_artifact):
    mechanisms = candidates_artifact["mechanisms"]
    assert candidates_artifact["kind"] == "gap_discovery_candidates"
    assert candidates_artifact["no_auto_promotion"] is True
    assert tuple(mechanism["mechanism"] for mechanism in mechanisms) == EXPECTED_MECHANISMS
    by_name = {mechanism["mechanism"]: mechanism for mechanism in mechanisms}
    assert len(by_name) == 7
    for name in RUN_MECHANISMS:
        mechanism = by_name[name]
        assert mechanism["status"] == "run", name
        assert mechanism["candidate_count"] >= 1, name
        assert mechanism["run_evidence"], name
        assert mechanism["reason"] is None
    for name in NOT_RUN_MECHANISMS:
        mechanism = by_name[name]
        assert mechanism["status"] == "not_run", name
        assert mechanism["candidate_count"] == 0, name
        assert mechanism["reason"] and len(mechanism["reason"]) > 20, name
        assert mechanism["run_evidence"] is None
    # Real run evidence fields (not placeholders)
    knowledge = by_name["knowledge"]["run_evidence"]
    assert knowledge["dimension_count"] == 20
    assert knowledge["non_covered_dimensions"] == 15
    assert len(knowledge["registry_digest"]) == 64
    failure = by_name["failure_driven"]["run_evidence"]
    assert "check_universe_methodology.py" in failure["command"]
    assert failure["ok"] is True
    assert failure["cell_count"] == 240
    assert failure["open_failures"] == 0
    assert failure["meta_mismatch_records"] == 47
    assert failure["failed_target_cases"] == 12
    differential = by_name["differential"]["run_evidence"]
    assert "check_capability_contract.py" in differential["command"]
    assert differential["cell_count"] == 8
    assert differential["negative_checks"] == 5
    assert differential["failed_negative_checks"] == 0
    assert differential["divergent_or_poc_missing_cells"] >= 4


def test_candidates_are_not_promoted_and_have_plans(candidates_artifact, registry):
    candidates = candidates_artifact["candidates"]
    assert candidates_artifact["candidate_count"] == len(candidates)
    assert candidates_artifact["candidate_count"] == registry["candidate_record_count"]
    assert candidates_artifact["validation"]["ok"] is True
    seen_ids: set[str] = set()
    for record in candidates:
        assert record["status"] == "candidate", record["gap_id"]
        assert record["discovery_source"] in RUN_MECHANISMS
        assert record["gap_id"] not in seen_ids
        seen_ids.add(record["gap_id"])
        plan = record["proposed_experiment"]
        assert plan["status"] in gaps.EXPERIMENT_STATUSES
        if plan["status"] == "proposed":
            assert plan["experiment_id"]
            assert isinstance(plan["steps"], list) and plan["steps"]
        else:
            assert plan["reason"].strip()
        assert record["evidence_refs"]
        assert record["target"]["kind"]
        assert record["verification_required"] is True
    categories: dict[str, int] = {}
    for record in candidates:
        categories[record["category"]] = categories.get(record["category"], 0) + 1
    assert categories.get("universe_dimension_gap") == 15
    assert categories.get("case_target_analysis_failure") == 12
    assert categories.get("audit_meta_mismatch_regression", 0) >= 19
    assert categories.get("platform_capability_differential", 0) >= 4
    # No candidate is a claims non_goal.
    assert all(record["discovery_source"] != "claims_non_goal" for record in candidates)


def test_artifact_files_and_sha256sums():
    for path in (GAPS_PATH, CANDIDATES_PATH, README_PATH, SUMS_PATH):
        assert path.is_file(), path
    entries: dict[str, str] = {}
    for line in SUMS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, relative = line.split(None, 1)
        entries[relative.strip()] = digest
    assert set(entries) == set(ARTIFACT_FILES)
    for name, digest in entries.items():
        assert _sha256(ARTIFACT / name) == digest
    for name in ARTIFACT_FILES:
        assert (ARTIFACT / name).read_bytes().decode("ascii")
    readme = README_PATH.read_text(encoding="utf-8")
    for mechanism in EXPECTED_MECHANISMS:
        assert mechanism in readme
    assert "not_run" in readme
    assert "candidate" in readme
    assert "RG-runtime-evidence" in readme


# ---------------------------------------------------------------------------
# Determinism and --check
# ---------------------------------------------------------------------------


def test_builder_is_deterministic_and_reproduces_committed_artifact(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    proc_a = _run_builder("--out", str(first), env_extra={"PYTHONHASHSEED": "0"})
    assert proc_a.returncode == 0, proc_a.stderr
    proc_b = _run_builder("--out", str(second), env_extra={"PYTHONHASHSEED": "12345"})
    assert proc_b.returncode == 0, proc_b.stderr
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    if sys.platform == "darwin":
        # The reference host can reproduce the committed artifact byte-for-byte.
        for name in (*ARTIFACT_FILES, "SHA256SUMS"):
            assert (first / name).read_bytes() == (ARTIFACT / name).read_bytes(), name
        check = _run_builder("--check")
        assert check.returncode == 0, check.stdout + check.stderr
        report = json.loads(check.stdout)
        assert report["ok"] is True
        assert report["violations"] == []
        for name in (*ARTIFACT_FILES, "SHA256SUMS"):
            assert report["files"][name]["match"] is True
        assert report["record_count"] == 64
        assert report["candidate_count"] == 51
    else:
        # Non-reference CI hosts validate the committed artifact integrity; the
        # host-dependent differential rows are only byte-reproducible on the
        # reference host (strict --check remains the release gate behavior).
        check = _run_builder("--check", "--allow-host-variance")
        assert check.returncode == 0, check.stdout + check.stderr
        report = json.loads(check.stdout)
        assert report["ok"] is True
        assert report["host_variance"]["allowed"] is True
        assert report["record_count"] == 64
        assert report["candidate_count"] == 51
    summary = _run_builder("--json")
    assert summary.returncode == 0, summary.stderr
    payload = json.loads(summary.stdout)
    assert payload["ok"] is True
    assert payload["record_count"] == 64
    assert payload["base_record_count"] == 13
    assert payload["candidate_count"] == 51
    assert [item["mechanism"] for item in payload["mechanisms"]] == list(EXPECTED_MECHANISMS)
    assert payload["validation"]["ok"] is True


def _copy_artifact(tmp_path: Path) -> Path:
    target = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, target)
    return target


def test_check_mode_detects_tampered_gaps_and_candidates(tmp_path):
    target = _copy_artifact(tmp_path)
    payload = json.loads((target / "gaps.json").read_text(encoding="utf-8"))
    payload["record_count"] = payload["record_count"] + 1
    (target / "gaps.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    proc = _run_builder("--check", "--out", str(target))
    assert proc.returncode == 1, proc.stdout
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert report["files"]["gaps.json"]["match"] is False
    assert any("gaps.json" in item for item in report["violations"])

    target2 = tmp_path / "artifact2"
    shutil.copytree(ARTIFACT, target2)
    candidates = json.loads((target2 / "candidates.json").read_text(encoding="utf-8"))
    candidates["mechanisms"][0]["candidate_count"] = 0
    (target2 / "candidates.json").write_text(
        json.dumps(candidates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    proc = _run_builder("--check", "--out", str(target2))
    assert proc.returncode == 1, proc.stdout
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert report["files"]["candidates.json"]["match"] is False


def test_check_mode_detects_tampered_readme_sums_and_missing_file(tmp_path):
    target = _copy_artifact(tmp_path)
    with (target / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    proc = _run_builder("--check", "--out", str(target))
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["files"]["README.md"]["match"] is False

    target2 = tmp_path / "artifact2"
    shutil.copytree(ARTIFACT, target2)
    lines = (target2 / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    digest, name = lines[0].split(None, 1)
    flipped = ("0" if digest[0] != "0" else "1") + digest[1:]
    lines[0] = f"{flipped}  {name.strip()}"
    (target2 / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    proc = _run_builder("--check", "--out", str(target2))
    assert proc.returncode == 1
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert any("SHA256SUMS" in item for item in report["violations"])

    target3 = tmp_path / "artifact3"
    shutil.copytree(ARTIFACT, target3)
    (target3 / "README.md").unlink()
    proc = _run_builder("--check", "--out", str(target3))
    assert proc.returncode == 1
    report = json.loads(proc.stdout)
    assert report["files"]["README.md"]["match"] is False


def test_schema_violations_are_detected_in_memory():
    gaps_payload = _load_json(str(GAPS_PATH.relative_to(ROOT)))
    candidates_payload = _load_json(str(CANDIDATES_PATH.relative_to(ROOT)))
    files = {
        "gaps.json": json.dumps(gaps_payload).encode("utf-8"),
        "candidates.json": json.dumps(candidates_payload).encode("utf-8"),
        "README.md": b"# ok\n",
    }
    assert discovery._schema_violations(files) == []

    broken_candidates = json.loads(json.dumps(candidates_payload))
    broken_candidates["mechanisms"][3]["reason"] = ""  # not_run without reason
    files["candidates.json"] = json.dumps(broken_candidates).encode("utf-8")
    violations = discovery._schema_violations(files)
    assert any("without reason" in item for item in violations)

    broken_candidates = json.loads(json.dumps(candidates_payload))
    broken_candidates["mechanisms"][0]["candidate_count"] = 0
    files["candidates.json"] = json.dumps(broken_candidates).encode("utf-8")
    assert any("produced no candidates" in item for item in discovery._schema_violations(files))

    broken_gaps = json.loads(json.dumps(gaps_payload))
    broken_gaps["records"][0]["status"] = "verified"
    files = {"gaps.json": json.dumps(broken_gaps).encode("utf-8"),
             "candidates.json": json.dumps(candidates_payload).encode("utf-8"),
             "README.md": b"# ok\n"}
    violations = discovery._schema_violations(files)
    assert violations
    assert any("invalid status" in item for item in violations)


# ---------------------------------------------------------------------------
# Cross-host CI mode: committed-integrity validation
# ---------------------------------------------------------------------------

DISCOVERY_SCRIPT = ROOT / "scripts" / "discover_capability_gaps.py"
GAP_ARTIFACT = ROOT / "artifacts" / "gap-registry-2026-11-16"


def _copy_artifact(tmp_path: Path) -> Path:
    target = tmp_path / "gap-registry"
    shutil.copytree(GAP_ARTIFACT, target)
    return target


def _run_discovery_check(artifact: Path, *extra: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(DISCOVERY_SCRIPT), "--check",
         "--out", str(artifact), *extra],
        cwd=ROOT, capture_output=True, text=True, timeout=180, env=env,
    )


def test_host_variance_check_validates_committed_integrity(tmp_path: Path) -> None:
    artifact = _copy_artifact(tmp_path)
    result = _run_discovery_check(artifact, "--allow-host-variance")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["host_variance"]["allowed"] is True
    assert payload["record_count"] == 64
    assert payload["candidate_count"] == 51


def test_host_variance_check_still_rejects_tampering(tmp_path: Path) -> None:
    artifact = _copy_artifact(tmp_path)
    gaps = json.loads((artifact / "gaps.json").read_text())
    gaps["records"][0]["status"] = "verified"
    (artifact / "gaps.json").write_text(json.dumps(gaps, indent=2) + "\n")
    result = _run_discovery_check(artifact, "--allow-host-variance")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["violations"]
