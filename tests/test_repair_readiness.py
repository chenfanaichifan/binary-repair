"""Tests for the Phase-8A 30-item repair readiness audit (G01-G30)."""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for entry in (ROOT, SCRIPTS):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from app.services import repair_readiness as readiness  # noqa: E402

ARTIFACT_DIR = ROOT / "artifacts" / "phase8-readiness-2026-11-16"
AUDIT = SCRIPTS / "audit_repair_readiness.py"


@pytest.fixture(scope="module")
def document() -> dict:
    return readiness.build_readiness(ROOT)


def test_registry_has_30_ordered_unique_items() -> None:
    items = readiness.READINESS_ITEMS
    assert len(items) == 30
    ids = [item["gap_id"] for item in items]
    assert ids == [f"G{index:02d}" for index in range(1, 31)]
    assert len(set(ids)) == 30
    assert ids == list(readiness.GAP_IDS)
    for item in items:
        for field in ("gap_id", "title", "user_requirement", "phase",
                      "priority", "dependencies", "required_deliverable",
                      "probe_spec", "blocker_if_missing"):
            assert field in item, (item.get("gap_id"), field)
        assert item["title"]
        assert item["title_en"]
        assert all(ord(ch) < 127 for ch in item["title_en"])
        assert item["user_requirement"]
        assert item["phase"] in readiness.PHASES
        assert item["priority"] in readiness.PRIORITIES
        assert isinstance(item["dependencies"], list)
        probe = item["probe_spec"]
        for field in ("code_paths", "test_paths", "test_markers",
                      "artifact_paths", "cli", "source_scope",
                      "ground_truth_paths", "independent_verifier_paths"):
            assert isinstance(probe[field], list), (item["gap_id"], field)


def test_build_produces_30_items_with_summary(document: dict) -> None:
    assert document["kind"] == readiness.KIND
    assert document["schema_version"] == readiness.SCHEMA_VERSION
    assert document["audit_date"] == "2026-11-16"
    assert document["capability_claims"] == []
    assert len(document["items"]) == 30
    summary = document["summary"]
    assert summary["total"] == 30
    assert sum(summary[status] for status in readiness.STATUSES) == 30
    for item in document["items"]:
        assert item["measured_status"] in readiness.STATUSES
        assert item["capability_claim"] is False
        assert item["next_action"]
        assert item["phase"] in readiness.PHASES
        assert item["priority"] in readiness.PRIORITIES
        assert isinstance(item["evidence_refs"], list)
        assert isinstance(item["test_refs"], list)
        assert item["ground_truth_status"] in {
            "present", "absent", "not_applicable"}
        assert item["independent_verifier"]["status"] in {"present", "absent"}
        if item["measured_status"] in {"partial", "missing", "not_run"}:
            assert item["blocker"], item["gap_id"]
    assert readiness.validate_document(document, ROOT) == []


def test_implemented_requires_code_and_test_evidence(document: dict) -> None:
    implemented = [item for item in document["items"]
                   if item["measured_status"] == "implemented"]
    assert implemented, "expected at least one implemented item"
    for item in implemented:
        assert item["code_probe"] is True or item["import_probe"] is True
        assert item["test_probe"] is True
        spec = readiness.item_by_id(item["gap_id"])["probe_spec"]
        if spec["artifact_paths"]:
            assert item["artifact_probe"] is True
        if spec["ground_truth_paths"]:
            assert item["ground_truth_status"] == "present"


def test_non_goal_items_map_to_claims_non_goals(document: dict) -> None:
    claims_ids = readiness.load_claims_non_goal_ids(ROOT)
    assert len(claims_ids) == 12
    non_goals = [item for item in document["items"]
                 if item["measured_status"] == "non_goal"]
    assert non_goals
    mapped_ids: set[str] = set()
    for item in non_goals:
        assert item["non_goal_ids"]
        assert set(item["non_goal_ids"]) <= claims_ids
        assert not item["unresolved_non_goal_ids"]
        mapped_ids.update(item["non_goal_ids"])
    assert mapped_ids


def test_hidden_benchmark_is_not_run_with_hidden_flag(document: dict) -> None:
    g29 = next(item for item in document["items"]
               if item["gap_id"] == "G29")
    assert g29["measured_status"] == "not_run"
    assert "hidden_available=false" in g29["blocker"]
    assert any(entry["gap_id"] == "G29" for entry in document["not_run"])


def test_fabricated_implemented_is_rejected(document: dict) -> None:
    fabricated = copy.deepcopy(document)
    target = None
    for item in fabricated["items"]:
        if item["measured_status"] == "missing":
            target = item
            break
    assert target is not None
    target["measured_status"] = "implemented"
    # keep the summary consistent so only the hard-evidence rule can catch it
    fabricated["summary"]["missing"] -= 1
    fabricated["summary"]["implemented"] += 1
    violations = readiness.validate_document(fabricated, ROOT)
    assert any("fabricated implemented" in item for item in violations), violations


def test_implemented_without_artifact_is_rejected(document: dict) -> None:
    fabricated = copy.deepcopy(document)
    target = next(item for item in fabricated["items"]
                  if item["measured_status"] == "implemented"
                  and item["artifact_probe"] is True
                  and (readiness.item_by_id(item["gap_id"])["probe_spec"]
                       ["artifact_paths"]))
    target["artifact_probe"] = False
    violations = readiness.validate_document(fabricated, ROOT)
    assert any("implemented requires artifact evidence" in item
               for item in violations), violations


def test_build_is_deterministic(document: dict) -> None:
    second = readiness.build_readiness(ROOT)
    assert document == second
    assert json.dumps(document, sort_keys=True) == json.dumps(
        second, sort_keys=True)


def test_cli_json_summary() -> None:
    result = subprocess.run(
        [sys.executable, str(AUDIT), "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert len(payload["items"]) == 30
    assert payload["summary"]["total"] == 30
    assert payload["capability_claims"] == []
    assert any(entry["gap_id"] == "G29" for entry in payload["not_run"])


def test_cli_write_check_roundtrip_and_hashseed_independence(
        tmp_path: Path) -> None:
    first = tmp_path / "seed-1"
    second = tmp_path / "seed-2"
    for target, seed in ((first, "1"), (second, "999")):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        result = subprocess.run(
            [sys.executable, str(AUDIT), "--write",
             "--artifact-dir", str(target)],
            cwd=ROOT, capture_output=True, text=True, timeout=240, env=env,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    for name in ("readiness.json", "README.md", "SHA256SUMS"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    check = subprocess.run(
        [sys.executable, str(AUDIT), "--check",
         "--artifact-dir", str(first)],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert check.returncode == 0, check.stdout + check.stderr
    assert "check OK" in check.stdout


def test_committed_artifacts_check_ok() -> None:
    result = subprocess.run(
        [sys.executable, str(AUDIT), "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ("readiness.json", "README.md", "SHA256SUMS"):
        assert (ARTIFACT_DIR / name).is_file(), name


@pytest.mark.parametrize("mutate", ["readiness", "readme", "sums"])
def test_check_detects_tampering(tmp_path: Path, mutate: str) -> None:
    target = tmp_path / "audit"
    shutil.copytree(ARTIFACT_DIR, target)
    if mutate == "readiness":
        path = target / "readiness.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["items"][0]["measured_status"] = "implemented"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    elif mutate == "readme":
        path = target / "README.md"
        path.write_text(path.read_text(encoding="utf-8") + "tamper\n",
                        encoding="utf-8")
    else:
        path = target / "SHA256SUMS"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("0" * 64 + "  readiness.json\n" + "\n".join(lines[1:]) + "\n",
                        encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(AUDIT), "--check",
         "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=240,
    )
    assert result.returncode != 0, result.stdout
    assert "READINESS-VIOLATION" in result.stdout


def test_check_accepts_committed_base_sha_ancestor(tmp_path):
    """A later commit may add files/tests; the recorded base SHA is allowed."""
    import subprocess
    from pathlib import Path as _Path
    result = subprocess.run(
        [sys.executable, str(AUDIT), "--write", "--artifact-dir", str(tmp_path)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    committed = json.loads((_Path(tmp_path) / "readiness.json").read_text())
    base = committed["generated_from_sha"]
    # A committed artifact with the same base SHA and current tree must pass
    # even when the checked-out HEAD has moved (the checker verifies ancestry).
    check = subprocess.run(
        [sys.executable, str(AUDIT), "--check", "--artifact-dir", str(tmp_path)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    assert check.returncode == 0, check.stdout + check.stderr
    assert base in check.stdout or "check OK" in check.stdout
