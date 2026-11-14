"""Validate the provider-coverage artifact and its deterministic builder.

Offline and deterministic: no provider calls, no network.  The tests check the
committed artifact, re-derive its values from the cited source artifacts, verify
every SHA-256, and exercise ``scripts/build_provider_coverage.py``:

* a fresh build is byte-identical across runs (deterministic, no wall clock);
* a fresh build equals the committed artifact (``--check`` exit 0);
* ``--check`` fails on a tampered summary, README or SHA256SUMS;
* per-provider/model statistics expose honest rates with Wilson 95% intervals,
  a separate deterministic-target-strict section, and never combine served-model
  evidence with requested-model identity evidence.
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
ARTIFACT = ROOT / "artifacts" / "provider-coverage-2026-11-14"
SUMMARY_PATH = ARTIFACT / "summary.json"
README_PATH = ARTIFACT / "README.md"
SUMS_PATH = ARTIFACT / "SHA256SUMS"
BUILDER = ROOT / "scripts" / "build_provider_coverage.py"
PYTHON = sys.executable

VALID_STATUSES = {
    "identity_verified_completed",
    "served_model_mismatch_completed",
    "probe_only_identity_mismatch",
    "blocked_unavailable",
    "unavailable_no_artifact",
}
ROW_REQUIRED_FIELDS = {
    "provider", "model_requested", "model_served", "identity_ok",
    "identity_verified", "status", "cases", "source",
}
STAT_REQUIRED_FIELDS = {
    "verified", "cases", "verified_rate", "wilson_ci95", "inconclusive",
}
COMPLETED_STATUSES = {"identity_verified_completed", "served_model_mismatch_completed"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_builder(*args: str, env_extra: dict[str, str] | None = None,
                 cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.pop("BINARYREPAIR_ASSISTANT_PROVIDER_KEY", None)
    env.pop("SILICONFLOW_API_KEY", None)
    env.pop("DASHSCOPE_API_KEY", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [PYTHON, str(BUILDER), *args],
        cwd=str(cwd or ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )


@lru_cache(maxsize=None)
def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def summary() -> dict:
    if not SUMMARY_PATH.is_file():
        pytest.fail(
            f"missing provider-coverage artifact: {SUMMARY_PATH} "
            "(run scripts/build_provider_coverage.py)"
        )
    return _load_json(str(SUMMARY_PATH.relative_to(ROOT)))


def _rows(summary: dict) -> list[dict]:
    return summary["evidence_rows"]


def _rows_by_id(summary: dict) -> dict[str, dict]:
    return {row["row_id"]: row for row in _rows(summary)}


def _stat_entries(summary: dict) -> list[dict]:
    return summary["statistics"]["by_provider_model"]


def _wilson_reference(verified: int, cases: int, z: float = 1.96) -> list[float]:
    """Independent Wilson 95% interval implementation for the tests."""
    import math

    if cases <= 0:
        return [0.0, 1.0]
    p = verified / cases
    denominator = 1.0 + z * z / cases
    centre = (p + z * z / (2.0 * cases)) / denominator
    margin = (
        z * math.sqrt(p * (1.0 - p) / cases + z * z / (4.0 * cases * cases))
    ) / denominator
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def _verify_sha256sums_dir(artifact_dir: str) -> int:
    base = ROOT / artifact_dir
    sums = base / "SHA256SUMS"
    assert sums.is_file(), f"{artifact_dir}/SHA256SUMS is missing"
    entries = 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, relative = line.split(None, 1)
        relative = relative.strip().lstrip("*")
        target = base / relative
        assert target.is_file(), f"{artifact_dir}: missing listed file {relative}"
        assert _sha256(target) == digest, f"{artifact_dir}: SHA256 mismatch for {relative}"
        entries += 1
    assert entries > 0
    return entries


# ---------------------------------------------------------------------------
# Artifact files and integrity
# ---------------------------------------------------------------------------


def test_artifact_files_and_own_sha256sums():
    for path in (SUMMARY_PATH, README_PATH, SUMS_PATH):
        assert path.is_file(), f"artifact file missing: {path}"
    entries: dict[str, str] = {}
    for line in SUMS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, relative = line.split(None, 1)
        entries[relative.strip()] = digest
    assert set(entries) == {"README.md", "summary.json"}, entries
    assert "SHA256SUMS" not in entries
    for relative, digest in entries.items():
        assert _sha256(ARTIFACT / relative) == digest
    for name in ("README.md", "summary.json"):
        data = (ARTIFACT / name).read_bytes()
        assert data.decode("ascii")  # ASCII-only evidence files
    text = README_PATH.read_text(encoding="utf-8")
    assert "wilson_ci95" in text
    assert "identity_ok" in text
    assert "not satisfied" in text.lower()


def test_schema_matches_release_gate_contract(summary):
    assert summary["schema_version"] == 1
    assert summary["kind"] == "provider_coverage"
    assert isinstance(summary["generated_at"], str)
    assert summary["generated_at"].endswith("Z")
    policy = summary["identity_policy"]
    assert policy["applied_in_this_artifact"] is True
    assert isinstance(policy["rule"], str) and policy["rule"]
    rows = _rows(summary)
    assert rows, "evidence_rows must be non-empty"
    for row in rows:
        missing = ROW_REQUIRED_FIELDS - set(row)
        assert not missing, f"{row.get('row_id')}: missing fields {sorted(missing)}"
        assert row["status"] in VALID_STATUSES, row["status"]
        assert isinstance(row["identity_ok"], (bool, type(None)))
        assert isinstance(row["cases"], int)
        for key in ("artifact_dir", "files", "sha256sums",
                    "corroborating_files", "reference_docs"):
            assert key in row["source"], f"{row['row_id']}: source.{key} missing"

    aggregate = summary["aggregate"]
    assert isinstance(aggregate["providers_completed_12case"], int)
    assert isinstance(aggregate["models_completed_12case"], int)
    assert aggregate["providers_completed_12case"] == 2
    assert aggregate["models_completed_12case"] == 4
    assert isinstance(aggregate["not_satisfied"], list) and aggregate["not_satisfied"]
    assert all(isinstance(item, str) for item in aggregate["not_satisfied"])
    assert any("5-6" in item for item in aggregate["not_satisfied"])
    assert isinstance(aggregate["blocked_reasons"], list) and aggregate["blocked_reasons"]

    assert summary["cost"]["available"] is False
    assert summary["cost"]["value"] is None
    assert summary["seed"]["available"] is False
    assert summary["seed"]["value"] is None


def test_every_cited_sha256_matches_disk_and_source_sums_validate(summary):
    checked_files = 0
    for row in _rows(summary):
        source = row["source"]
        for group in ("files", "corroborating_files", "reference_docs"):
            for entry in source[group]:
                path = ROOT / entry["path"]
                assert path.is_file(), f"{row['row_id']}: missing {entry['path']}"
                assert _sha256(path) == entry["sha256"], (
                    f"{row['row_id']}: SHA256 mismatch for {entry['path']}"
                )
                checked_files += 1
        sums = source["sha256sums"]
        if sums is None:
            continue
        sums_path = ROOT / sums["sha256sums"]
        assert sums_path.is_file(), f"{row['row_id']}: missing {sums['sha256sums']}"
        assert _sha256(sums_path) == sums["sha256sums_sha256"]
        assert sums["valid"] is True, (
            f"{row['row_id']}: source artifact SHA256SUMS is not valid: {sums}"
        )
        assert sums["entries"] == _verify_sha256sums_dir(source["artifact_dir"])
    assert checked_files >= 30, checked_files

    for artifact_dir in (
        "artifacts/deepseek-matrix-2026-11-14",
        "artifacts/multi-model-matrix-2026-11-14",
        "artifacts/multi-model-matrix-intl-2026-11-14",
        "artifacts/multi-model-matrix-cn-2026-11-14",
        "artifacts/provider-matrix-2026-11-14",
        "artifacts/multi-model-probe-2026-11-14",
    ):
        assert _verify_sha256sums_dir(artifact_dir) > 0


def test_provenance_is_deterministic_and_source_derived(summary):
    provenance = summary["provenance"]
    assert provenance["builder"] == "scripts/build_provider_coverage.py"
    digest = provenance["source_digest_sha256"]
    assert isinstance(digest, str) and len(digest) == 64
    assert provenance["cited_source_count"] > 0
    provider_matrix = _load_json("artifacts/provider-matrix-2026-11-14/summary.json")
    # generated_at must be the source-recorded timestamp, not the build clock.
    assert summary["generated_at"] == provider_matrix["generated_at"]
    assert "generated_at" in provenance["generated_at_source"]


# ---------------------------------------------------------------------------
# Identity policy
# ---------------------------------------------------------------------------


def test_identity_policy_is_enforced_on_every_row(summary):
    rows = _rows(summary)
    completed = [r for r in rows if r["status"] == "identity_verified_completed"]
    mismatch = [
        r for r in rows
        if r["status"] in {"served_model_mismatch_completed",
                           "probe_only_identity_mismatch"}
    ]
    for row in rows:
        if row["identity_ok"] is False:
            assert row["identity_verified"] is False, row["row_id"]
            assert row["status"] in {
                "served_model_mismatch_completed", "probe_only_identity_mismatch",
            }, row["row_id"]
        if row["status"] == "identity_verified_completed":
            assert row["identity_ok"] is True
            assert row["identity_verified"] is True
            assert row["ai_verified_attributed_to"] == row["model_served"]
        if row["status"] == "served_model_mismatch_completed":
            assert row["model_served"] != row["model_requested"]
            assert row["ai_verified_attributed_to"] == row["model_served"]
            text = " ".join(row["limitations"]).lower()
            assert "must not be presented" in text
            assert "served" in text
    assert len(completed) == 4
    assert len(mismatch) == summary["aggregate"]["identity_mismatch_rows"] == 2
    assert "deepseek-chat" not in summary["aggregate"]["identity_verified_models"]
    assert summary["aggregate"]["served_model_only_completed_rows"] == 1
    served = next(
        row for row in rows
        if row["status"] == "served_model_mismatch_completed"
    )
    assert served["model_requested"] == "deepseek-chat"
    assert served["model_served"] == "deepseek-flash"
    assert served["identity_ok"] is False and served["identity_verified"] is False


def test_statistics_follow_identity_policy(summary):
    statistics = summary["statistics"]
    by_model = {entry["model_requested"]: entry
                for entry in statistics["by_provider_model"]
                if entry["status"] == "identity_verified_completed"}
    assert set(by_model) == {
        "deepseek-flash", "deepseek-v4-pro",
        "Qwen/Qwen3-8B", "Qwen/Qwen2.5-7B-Instruct",
    }
    for entry in by_model.values():
        assert entry["identity_ok"] is True
        assert entry["identity_verified"] is True
        assert entry["attributed_to"] == entry["model_served"]
    served = statistics["ai_target"]["served_model_only"]
    assert served["status"] == "served_model_mismatch_completed"
    assert served["identity_ok"] is False
    assert served["identity_verified"] is False
    assert served["model_served"] == "deepseek-flash"
    assert served["attributed_to"] == "deepseek-flash"
    assert served["verified_rate"] == 0.5
    pooled = statistics["ai_target"]["pooled_identity_verified"]
    # The served-model-only run is never pooled with requested-model evidence.
    assert pooled["models"] == 4
    assert pooled["runs"] == 8
    assert pooled["cases"] == 96
    assert pooled["verified"] == 36
    assert pooled["verified_rate"] == 0.375
    assert pooled["inconclusive"] == 60
    assert pooled["wilson_ci95"] == pytest.approx(
        [round(lo, 6) for lo in _wilson_reference(36, 96)]
    )


# ---------------------------------------------------------------------------
# Statistics / Wilson interval sanity
# ---------------------------------------------------------------------------


def test_statistics_schema_and_wilson_sanity(summary):
    statistics = summary["statistics"]
    assert statistics["confidence_level"] == 0.95
    assert statistics["z_score"] == 1.96
    assert isinstance(statistics["deterministic_target_strict"], dict)
    assert isinstance(statistics["ai_target"], dict)
    entries = _stat_entries(summary)
    assert entries
    for entry in entries:
        for field in STAT_REQUIRED_FIELDS:
            assert field in entry, f"{entry['model_requested']}: missing {field}"
        assert isinstance(entry["verified"], int)
        assert isinstance(entry["cases"], int)
        assert isinstance(entry["verified_rate"], float)
        assert isinstance(entry["inconclusive"], int)
        ci = entry["wilson_ci95"]
        assert isinstance(ci, list) and len(ci) == 2
        assert 0.0 <= ci[0] <= entry["verified_rate"] <= ci[1] <= 1.0
        assert entry["cases_pooled"] == entry["cases"] * entry["runs"]
        assert entry["verified"] <= entry["cases_pooled"]
        assert entry["inconclusive"] == entry["cases_pooled"] - entry["verified"]
        if entry["cases_pooled"] > 0:
            assert entry["verified_rate"] == pytest.approx(
                entry["verified"] / entry["cases_pooled"], abs=1e-9
            )
            expected = _wilson_reference(entry["verified"], entry["cases_pooled"])
            assert ci == pytest.approx(
                [round(expected[0], 6), round(expected[1], 6)], abs=1e-6
            )
        else:
            assert entry["verified"] == 0
            assert entry["verified_rate"] == 0.0
            assert ci == [0.0, 1.0]
    completed = [entry for entry in entries
                 if entry["status"] == "identity_verified_completed"]
    assert len(completed) == 4
    for entry in completed:
        assert entry["cases"] == 12
        assert entry["runs"] >= 1


def test_deterministic_target_strict_is_separate(summary):
    deterministic = summary["statistics"]["deterministic_target_strict"]
    assert deterministic["available"] is True
    assert deterministic["metric"] == "deterministic_target_strict"
    assert deterministic["cases"] == 12
    assert deterministic["verified"] == 0
    assert deterministic["verified_rate"] == 0.0
    assert deterministic["inconclusive"] == 12
    assert deterministic["expected_matches"] == 12
    assert deterministic["expected_match_rate"] == 1.0
    assert deterministic["wilson_ci95"] == pytest.approx(
        [round(lo, 6) for lo in _wilson_reference(0, 12)], abs=1e-6
    )
    assert deterministic["target_scope_resolved"] == 12
    assert deterministic["dispositions"] == {"analysis_only": 12}
    # The deterministic measurement is not pooled into the AI target metric.
    pooled_cases = summary["statistics"]["ai_target"]["pooled_identity_verified"]["cases"]
    assert pooled_cases != deterministic["cases"]


def test_aggregate_requests_and_not_satisfied_are_honest(summary):
    aggregate = summary["aggregate"]
    requirements = aggregate["requirements"]
    assert requirements["at_least_2_models_12case"]["satisfied"] is True
    assert requirements["at_least_2_providers_12case"]["satisfied"] is True
    five = requirements["five_model_international_matrix"]
    assert five["satisfied"] is False
    assert "402" in five["reason"]
    assert requirements["identity_policy_applied"]["satisfied"] is True
    assert requirements["at_least_2_providers_12case"]["evidence"] == [
        "deepseek-official", "siliconflow-cn",
    ]
    blocked_providers = {item["provider"] for item in aggregate["blocked_reasons"]}
    assert {"siliconflow-intl", "dashscope"} <= blocked_providers
    assert summary["next_steps"]
    assert summary["limitations"]
    assert summary["aggregate"]["not_satisfied"]


# ---------------------------------------------------------------------------
# Evidence values re-derived from the cited source artifacts
# ---------------------------------------------------------------------------


def test_deepseek_matrix_rows_match_source_artifact(summary):
    rows = _rows_by_id(summary)
    aggregate = _load_json("artifacts/multi-model-matrix-2026-11-14/aggregate.json")
    probe = _load_json("artifacts/deepseek-matrix-2026-11-14/summary.json")
    assert aggregate["models"] == ["deepseek-flash", "deepseek-v4-pro"]
    assert aggregate["model_identity_all_runs"] is True
    assert aggregate["cases"] == 12
    assert probe["ok"] == 2 and probe["identity_mismatch"] == 0
    for model in ("deepseek-flash", "deepseek-v4-pro"):
        row = rows[f"deepseek-official/{model}"]
        runs = [item for item in aggregate["runs_detail"] if item["model"] == model]
        assert len(runs) == row["runs"] == 3
        assert [item["ai_verified"] for item in runs] == row["runs_ai_verified"]
        assert all(item["identity_ok"] for item in runs) is True
        assert row["identity_ok"] is True and row["identity_verified"] is True
        probe_record = next(
            item for item in probe["records"] if item["spec"] == f"deepseek:{model}"
        )
        assert probe_record["model_identity_ok"] is True
        assert probe_record["model_returned"] == model


def test_siliconflow_cn_rows_match_source_artifacts(summary):
    rows = _rows_by_id(summary)
    matrix = _load_json("artifacts/multi-model-matrix-cn-2026-11-14/summary.json")
    aggregate = _load_json("artifacts/multi-model-matrix-cn-2026-11-14/aggregate.json")
    assert aggregate["completed_models"] == 4
    assert aggregate["identity_mismatch"] == 0
    for model, slug in (
        ("Qwen/Qwen3-8B", "Qwen_Qwen3-8B"),
        ("Qwen/Qwen2.5-7B-Instruct", "Qwen_Qwen2.5-7B-Instruct"),
    ):
        row = rows[f"siliconflow-cn/{model}"]
        record = next(
            item for item in matrix["records"] if item["model_requested"] == model
        )
        assert record["status"] == "ok"
        assert record["model_identity_ok"] is True
        assert record["benchmark"]["cases"] == 12
        benchmark = _load_json(
            "artifacts/multi-model-matrix-cn-2026-11-14/benchmarks/"
            f"siliconflow-{slug}/summary.json"
        )
        assert len(benchmark["cases"]) == row["cases"] == 12
        assert benchmark["ai_verified"] == row["ai_verified"] == 0


def test_siliconflow_intl_blocked_rows_match_source_artifact(summary):
    rows = _rows_by_id(summary)
    matrix = _load_json("artifacts/multi-model-matrix-intl-2026-11-14/summary.json")
    identity = _load_json(
        "artifacts/multi-model-matrix-intl-2026-11-14/identity-probe/summary.json"
    )
    for model in (
        "Qwen/Qwen3.8-27B",
        "moonshotai/Kimi-K3.1-Pro",
        "deepseek-ai/DeepSeek-V4.1-Flash",
    ):
        row = rows[f"siliconflow-intl/{model}"]
        record = next(
            item for item in matrix["records"] if item["model_requested"] == model
        )
        assert record["status"] == "error"
        assert "402" in record["error"]
        probe_record = next(
            item for item in identity["records"] if item["model_requested"] == model
        )
        assert probe_record["status"] == "ok"
        assert probe_record["model_identity_ok"] is True
        assert row["status"] == "blocked_unavailable"
        assert row["cases"] == 0 and row["ai_verified"] is None


def test_provider_matrix_mismatch_row_matches_source_artifact(summary):
    rows = _rows_by_id(summary)
    row = rows["deepseek-official/provider-matrix/deepseek-chat->deepseek-flash"]
    matrix = _load_json("artifacts/provider-matrix-2026-11-14/summary.json")
    provider = matrix["provider"]
    assert provider["model_requested"] == row["model_requested"] == "deepseek-chat"
    assert provider["model_returned"] == row["model_served"] == "deepseek-flash"
    assert provider["model_identity_ok"] is False
    assert matrix["aggregate"]["ai_target_verified"] == row["ai_verified"] == 6
    assert matrix["aggregate"]["cases"] == row["cases"] == 12
    assert row["status"] == "served_model_mismatch_completed"


def test_probe_and_glm_rows_match_source_artifacts(summary):
    rows = _rows_by_id(summary)
    probe_row = rows["deepseek-official/probe/deepseek-chat"]
    probe = _load_json("artifacts/multi-model-probe-2026-11-14/summary.json")
    record = next(
        item for item in probe["records"] if item["spec"] == "deepseek:deepseek-chat"
    )
    assert record["status"] == "identity_mismatch"
    assert record["model_returned"] == probe_row["model_served"] == "deepseek-flash"
    assert probe_row["status"] == "probe_only_identity_mismatch"

    glm_row = rows["siliconflow-cn/THUDM/GLM-Z1-9B-0414"]
    cn_identity = _load_json(
        "artifacts/multi-model-matrix-cn-2026-11-14/identity-probe/summary.json"
    )
    glm = next(
        item for item in cn_identity["records"]
        if item["model_requested"] == "THUDM/GLM-Z1-9B-0414"
    )
    assert glm["status"] == "error"
    assert "TimeoutError" in glm["error"]
    assert glm_row["identity_ok"] is None
    assert glm_row["identity_verified"] is False


# ---------------------------------------------------------------------------
# Builder: determinism, reproducibility and --check tamper detection
# ---------------------------------------------------------------------------


def test_builder_is_deterministic_across_hash_seeds(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    proc_a = _run_builder("--out", str(first), env_extra={"PYTHONHASHSEED": "0"})
    assert proc_a.returncode == 0, proc_a.stderr
    proc_b = _run_builder("--out", str(second), env_extra={"PYTHONHASHSEED": "12345"})
    assert proc_b.returncode == 0, proc_b.stderr
    for name in ("summary.json", "README.md", "SHA256SUMS"):
        assert (first / name).is_file(), name
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    fresh = json.loads((first / "summary.json").read_text(encoding="utf-8"))
    provider_matrix = _load_json("artifacts/provider-matrix-2026-11-14/summary.json")
    # The source-derived timestamp, not a wall clock: identical across builds.
    assert fresh["generated_at"] == provider_matrix["generated_at"]


def test_builder_reproduces_committed_artifact(tmp_path):
    built = tmp_path / "built"
    proc = _run_builder("--out", str(built))
    assert proc.returncode == 0, proc.stderr
    for name in ("summary.json", "README.md", "SHA256SUMS"):
        assert (built / name).read_bytes() == (ARTIFACT / name).read_bytes(), name
    check = _run_builder("--check")
    assert check.returncode == 0, check.stdout + check.stderr
    report = json.loads(check.stdout)
    assert report["ok"] is True
    assert report["violations"] == []
    for name, item in report["files"].items():
        assert item["match"] is True, name
        assert item["fresh_sha256"] == item["actual_sha256"]
    assert len(report["fresh_source_digest_sha256"]) == 64


def _copy_artifact(tmp_path: Path) -> Path:
    target = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, target)
    return target


def test_check_mode_detects_tampered_summary(tmp_path):
    target = _copy_artifact(tmp_path)
    payload = json.loads((target / "summary.json").read_text(encoding="utf-8"))
    payload["purpose"] = payload["purpose"] + " tampered"
    (target / "summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    proc = _run_builder("--check", "--out", str(target))
    assert proc.returncode == 1, proc.stdout
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert report["files"]["summary.json"]["match"] is False
    assert any("summary.json" in item for item in report["violations"])


def test_check_mode_detects_tampered_readme(tmp_path):
    target = _copy_artifact(tmp_path)
    with (target / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    proc = _run_builder("--check", "--out", str(target))
    assert proc.returncode == 1, proc.stdout
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert report["files"]["README.md"]["match"] is False
    assert any("README.md" in item for item in report["violations"])


def test_check_mode_detects_tampered_sha256sums(tmp_path):
    target = _copy_artifact(tmp_path)
    text = (target / "SHA256SUMS").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    digest, name = lines[0].split(None, 1)
    flipped = ("0" if digest[0] != "0" else "1") + digest[1:]
    lines[0] = f"{flipped}  {name.strip()}"
    (target / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")
    proc = _run_builder("--check", "--out", str(target))
    assert proc.returncode == 1, proc.stdout
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert any("SHA256SUMS" in item for item in report["violations"])


def test_check_mode_fails_on_missing_artifact(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    proc = _run_builder("--check", "--out", str(empty))
    assert proc.returncode == 1, proc.stdout
    report = json.loads(proc.stdout)
    assert report["ok"] is False
    assert len(report["violations"]) >= 3
