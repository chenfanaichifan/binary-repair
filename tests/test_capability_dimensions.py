"""Tests for the Phase-7 20-dimension capability universe registry.

Offline and deterministic: no network, no provider calls.  The tests validate
the module registry (D01-D20 ids/titles verbatim, statuses, old-11 mapping),
the deterministic artifact builder (240/240 cell mapping, counts cross-checked
against the committed coverage matrix, 12 out-of-universe candidates,
unknown_within_universe=0, undiscovered_space=not_measurable), and the
``--check`` mode including tamper detection.
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import capability_dimensions as dimensions  # noqa: E402

BUILDER = ROOT / "scripts" / "build_universe_dimension_registry.py"
ARTIFACT = ROOT / "artifacts" / "capability-universe-2026-11-16"
REGISTRY_PATH = ARTIFACT / "dimension-registry.json"
README_PATH = ARTIFACT / "README.md"
SUMS_PATH = ARTIFACT / "SHA256SUMS"
ARTIFACT_FILES = ("dimension-registry.json", "README.md")
MATRIX_PATH = "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json"
CLAIMS_PATH = "docs/status/claims.json"
PYTHON = sys.executable

EXPECTED_TITLES = (
    "Binary formats",
    "CPU architectures",
    "ABI and calling conventions",
    "Compiler ecosystems",
    "Vulnerability classes",
    "Memory safety",
    "Arithmetic safety",
    "Control-flow safety",
    "Data-flow analysis",
    "Control-flow analysis",
    "Interprocedural analysis",
    "Binary structure",
    "Runtime environments",
    "Exploitability assessment",
    "Repair strategies",
    "Patch generation",
    "Patch application",
    "Semantic preservation",
    "Verification",
    "AI model intelligence",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=None)
def _load_json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry() -> dict:
    assert REGISTRY_PATH.is_file(), (
        f"missing universe artifact {REGISTRY_PATH}; run "
        "scripts/build_universe_dimension_registry.py"
    )
    return _load_json(str(REGISTRY_PATH.relative_to(ROOT)))


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
        timeout=180,
        env=env,
    )


# ---------------------------------------------------------------------------
# Module registry
# ---------------------------------------------------------------------------


def test_dimension_ids_and_titles_are_authoritative():
    assert len(dimensions.DIMENSIONS) == 20
    ids = [dimension["id"] for dimension in dimensions.DIMENSIONS]
    assert ids == [f"D{index:02d}" for index in range(1, 21)]
    assert len(set(ids)) == 20
    assert tuple(dimensions.AUTHORITATIVE_TITLES) == EXPECTED_TITLES
    titles = [dimension["title"] for dimension in dimensions.DIMENSIONS]
    assert tuple(titles) == EXPECTED_TITLES
    # Specific titles called out by the task/Lead must be exact.
    assert dimensions.get_dimension("D01")["title"] == "Binary formats"
    assert dimensions.get_dimension("D03")["title"] == "ABI and calling conventions"


def test_dimension_schema_and_evidence_paths():
    for dimension in dimensions.DIMENSIONS:
        assert dimension["status"] in dimensions.STATUSES
        assert dimension["description"].strip()
        assert dimension["owner"].strip()
        assert dimension["review_by"].startswith("20")
        assert isinstance(dimension["source_registries"], list)
        assert isinstance(dimension["related_non_goal_ids"], list)
        assert dimension["evidence_refs"], dimension["id"]
        for ref in dimension["evidence_refs"]:
            assert set(ref) == {"path", "fragment", "kind"}
            assert (ROOT / ref["path"]).is_file(), (dimension["id"], ref["path"])
        mapping = dimension["old_11dim_mapping"]
        assert mapping["mapping_strength"] in {"none", "partial", "full"}
        assert set(mapping["old_dimensions"]) <= set(dimensions.OLD_11_DIMS)
        if mapping["mapping_strength"] == "none":
            assert mapping["old_dimensions"] == []
        if dimension["status"] == "covered":
            assert mapping["mapping_strength"] == "full"
        if dimension["status"] == "not_started":
            assert mapping["old_dimensions"] == []
        if dimension["status"] == "non_goal":
            assert dimension["related_non_goal_ids"]


def test_old_11_mapping_is_complete_and_bidirectional():
    assert len(dimensions.OLD_11_DIMS) == 11
    assert len(set(dimensions.OLD_11_DIMS)) == 11
    assert set(dimensions.OLD_TO_NEW) == set(dimensions.OLD_11_DIMS)
    valid_ids = {dimension["id"] for dimension in dimensions.DIMENSIONS}
    referenced: set[str] = set()
    for old, targets in dimensions.OLD_TO_NEW.items():
        assert targets, f"old dimension {old} not mapped"
        assert all(target in valid_ids for target in targets)
        referenced.update(targets)
    expected_referenced = {
        dimension["id"] for dimension in dimensions.DIMENSIONS
        if dimension["old_11dim_mapping"]["old_dimensions"]
    }
    assert referenced == expected_referenced
    assert referenced <= valid_ids
    unmapped = valid_ids - referenced
    assert unmapped == {"D03", "D04", "D07", "D08", "D09", "D10", "D11", "D14", "D18"}
    for new, olds in dimensions.NEW_TO_OLD.items():
        assert new in valid_ids
        for old in olds:
            assert old in dimensions.OLD_11_DIMS
            assert new in dimensions.OLD_TO_NEW[old]
    # documented no-mapping dimensions
    assert dimensions.NEW_TO_OLD["D03"] == ()
    assert dimensions.NEW_TO_OLD["D04"] == ()
    assert dimensions.NEW_TO_OLD["D14"] == ()
    assert dimensions.NEW_TO_OLD["D18"] == ()
    assert dimensions.NEW_TO_OLD["D12"] == ("bits", "endian")


def test_registry_digest_is_deterministic_and_validation_ok():
    first = dimensions.registry_digest()
    second = dimensions.registry_digest()
    assert first == second
    assert len(first) == 64
    validation = dimensions.validate()
    assert validation["ok"] is True, validation["violations"]
    assert validation["dimension_count"] == 20
    payload = dimensions.registry_payload()
    assert payload["dimension_count"] == 20
    # digest changes when the registry changes
    payload["dimensions"][0]["status"] = "not_started"
    assert dimensions.registry_digest(payload) != first


def test_validate_rejects_invalid_registries():
    payload = json.loads(json.dumps(dimensions.registry_payload()))

    corrupted = json.loads(json.dumps(payload))
    corrupted["dimensions"][0]["status"] = "verified"  # not an allowed status
    result = dimensions.validate(corrupted)
    assert result["ok"] is False
    assert any("invalid status" in item for item in result["violations"])

    duplicated = json.loads(json.dumps(payload))
    duplicated["dimensions"][1]["id"] = duplicated["dimensions"][0]["id"]
    assert dimensions.validate(duplicated)["ok"] is False

    missing_title = json.loads(json.dumps(payload))
    missing_title["dimensions"][2]["title"] = ""
    assert dimensions.validate(missing_title)["ok"] is False

    unmapped_old = json.loads(json.dumps(payload))
    for dimension in unmapped_old["dimensions"]:
        dimension["old_11dim_mapping"]["old_dimensions"] = []
        dimension["old_11dim_mapping"]["mapping_strength"] = "none"
    result = dimensions.validate(unmapped_old)
    assert result["ok"] is False
    assert any("not mapped" in item for item in result["violations"])


# ---------------------------------------------------------------------------
# Artifact content
# ---------------------------------------------------------------------------


def test_artifact_cell_mapping_and_counts(registry):
    assert registry["schema_version"] == 1
    assert registry["kind"] == "universe_dimension_registry"
    assert registry["dimension_count"] == 20
    assert registry["cell_count"] == 240
    assert registry["mapped_cells"] == 240
    assert registry["cell_mapping"]["mapped_cells"] == 240
    assert registry["cell_mapping"]["total_cells"] == 240
    assert registry["cell_mapping"]["unmapped_cells"] == []
    assert len(registry["cell_mapping"]["mapping_digest_sha256"]) == 64
    matrix = _load_json(MATRIX_PATH)
    universe_counts = matrix["universe"]["counts"]
    assert registry["cell_counts"]["verified"] == universe_counts["verified"] == 36
    assert registry["cell_counts"]["supported"] == universe_counts["supported"] == 51
    assert registry["cell_counts"]["non_goal"] == universe_counts["non_goal"] == 129
    assert registry["cell_counts"]["unavailable"] == universe_counts["unavailable"] == 24
    assert registry["cell_counts"]["unknown"] == universe_counts["unknown"] == 0
    assert registry["cell_counts"]["total"] == 240
    assert registry["counts_match_coverage_matrix"] is True
    assert registry["coverage_matrix_counts"]["cell_count"] == 240
    assert sum(
        registry["cell_counts"][status]
        for status in ("verified", "supported", "non_goal", "unavailable", "unknown")
    ) == 240


def test_artifact_dimensions_and_old_mapping(registry):
    entries = registry["dimensions"]
    assert [entry["id"] for entry in entries] == [f"D{index:02d}" for index in range(1, 21)]
    assert [entry["title"] for entry in entries] == list(EXPECTED_TITLES)
    statuses = {entry["id"]: entry["status"] for entry in entries}
    assert set(statuses.values()) <= set(dimensions.STATUSES)
    covered = [entry["id"] for entry in entries if entry["status"] == "covered"]
    partial = [entry["id"] for entry in entries if entry["status"] == "partial"]
    non_goal = [entry["id"] for entry in entries if entry["status"] == "non_goal"]
    not_started = [entry["id"] for entry in entries if entry["status"] == "not_started"]
    assert registry["covered_dimensions"] == covered
    assert registry["partial_dimensions"] == partial
    assert registry["non_goal_dimensions"] == non_goal
    assert registry["not_started_dimensions"] == not_started
    assert len(covered) == 5
    assert len(partial) == 6
    assert len(non_goal) == 2
    assert len(not_started) == 7
    assert registry["dimension_status_counts"] == {
        "covered": 5, "partial": 6, "non_goal": 2, "unavailable": 0, "not_started": 7,
    }
    for entry in entries:
        assert entry["status_reason"].strip()
        assert entry["universe_evidence"]["mapped_cells"] >= 0
        if entry["status"] == "covered":
            assert entry["universe_evidence"]["mapped_cells"] > 0
    old = registry["old_11_dimensions"]
    assert set(old) == set(dimensions.OLD_11_DIMS)
    for old_dim, payload in old.items():
        assert payload["values"]
        assert payload["mapped_to_new_dimensions"] == list(dimensions.OLD_TO_NEW[old_dim])
        assert sum(payload["cell_counts"].values()) == 240
    assert registry["old_to_new_mapping"] == {
        key: list(value) for key, value in dimensions.OLD_TO_NEW.items()
    }


def test_artifact_out_of_universe_and_unknown_semantics(registry):
    claims = _load_json(CLAIMS_PATH)
    expected_ids = [item["id"] for item in claims["non_goals"]]
    candidates = registry["out_of_universe_candidates"]
    assert registry["out_of_universe_count"] == 12
    assert [item["candidate_id"] for item in candidates] == expected_ids
    for item in candidates:
        assert item["source"] == "claims_non_goal"
        assert item["claim"].strip()
        assert item["owner"].strip()
        assert item["review_by"]
        assert item["reason_out_of_universe"]
        assert len(item["evidence_refs"]) == 2
        assert item["evidence_refs"][0].startswith(CLAIMS_PATH)
        assert item["evidence_refs"][1].startswith(MATRIX_PATH)
    assert registry["unknown_within_universe"] == 0
    assert registry["unknown_within_universe_detail"]["count"] == 0
    assert registry["unknown_within_universe_detail"]["cells"] == []
    assert registry["undiscovered_space"] == "not_measurable"
    assert "not_measurable" in registry["undiscovered_space_note"]
    assert "no count" in registry["undiscovered_space_note"].lower() or (
        "no number" in registry["undiscovered_space_note"].lower()
    )
    assert registry["assumptions"]
    assert isinstance(registry["provenance"]["source_digest_sha256"], str)
    assert len(registry["provenance"]["source_digest_sha256"]) == 64
    for source in registry["provenance"]["sources"]:
        assert _sha256(ROOT / source["path"]) == source["sha256"]


def test_artifact_files_and_sha256sums():
    for path in (REGISTRY_PATH, README_PATH, SUMS_PATH):
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
    assert "D01" in readme and "D20" in readme
    assert "240" in readme
    assert "not_measurable" in readme


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
        assert (first / name).read_bytes() == (ARTIFACT / name).read_bytes(), name
    check = _run_builder("--check")
    assert check.returncode == 0, check.stdout + check.stderr
    report = json.loads(check.stdout)
    assert report["ok"] is True
    assert report["violations"] == []
    for name in (*ARTIFACT_FILES, "SHA256SUMS"):
        assert report["files"][name]["match"] is True
    assert len(report["fresh_source_digest_sha256"]) == 64
    summary = _run_builder("--json")
    assert summary.returncode == 0, summary.stderr
    payload = json.loads(summary.stdout)
    assert payload["ok"] is True
    assert payload["dimension_count"] == 20
    assert payload["mapped_cells"] == 240
    assert payload["unknown_within_universe"] == 0
    assert payload["undiscovered_space"] == "not_measurable"
    assert payload["out_of_universe_count"] == 12


def _copy_artifact(tmp_path: Path) -> Path:
    target = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, target)
    return target


def test_check_mode_detects_tampered_registry(tmp_path):
    target = _copy_artifact(tmp_path)
    payload = json.loads((target / "dimension-registry.json").read_text(encoding="utf-8"))
    payload["mapped_cells"] = 239
    (target / "dimension-registry.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    proc = _run_builder("--check", "--out", str(target))
    assert proc.returncode == 1, proc.stdout
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert report["files"]["dimension-registry.json"]["match"] is False
    assert any("dimension-registry.json" in item for item in report["violations"])


def test_check_mode_detects_tampered_readme_and_sha256sums(tmp_path):
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


def test_check_mode_fails_on_missing_artifact(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = _run_builder("--check", "--out", str(empty))
    assert proc.returncode == 1
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert len(report["violations"]) >= 2
