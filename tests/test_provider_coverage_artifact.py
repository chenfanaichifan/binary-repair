"""Validate the provider-coverage evidence artifact (frozen release worktree).

The artifact `artifacts/provider-coverage-2026-11-14/` is a machine-readable
consolidation of the provider/model evidence already present in the frozen
release tree.  These tests are offline and deterministic: they never call a
provider.  They fail closed if the artifact claims evidence that is missing,
tampered (SHA-256 mismatch), not re-derivable from the cited source artifacts, or
that violates the strict model-identity policy.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "provider-coverage-2026-11-14"
SUMMARY_PATH = ARTIFACT / "summary.json"
README_PATH = ARTIFACT / "README.md"
SUMS_PATH = ARTIFACT / "SHA256SUMS"

VALID_STATUSES = {
    "identity_verified_completed",
    "served_model_mismatch_completed",
    "probe_only_identity_mismatch",
    "blocked_unavailable",
    "unavailable_no_artifact",
}
COMPLETED_STATUSES = {"identity_verified_completed", "served_model_mismatch_completed"}
ROW_REQUIRED_FIELDS = {
    "row_id", "provider", "model_requested", "identity_ok", "identity_verified",
    "status", "cases", "runs", "ai_verified", "ai_verified_attributed_to",
    "source", "limitations",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=None)
def _load_json(relative_path: str) -> dict:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def summary() -> dict:
    if not SUMMARY_PATH.is_file():
        pytest.fail(
            f"missing provider-coverage artifact: {SUMMARY_PATH} "
            "(the frozen release worktree must carry the provider evidence)"
        )
    return _load_json(str(SUMMARY_PATH.relative_to(ROOT)))


def _rows(summary: dict) -> list[dict]:
    return summary["evidence_rows"]


def _rows_by_id(summary: dict) -> dict[str, dict]:
    return {row["row_id"]: row for row in _rows(summary)}


def _verify_sha256sums_dir(artifact_dir: str) -> int:
    """Verify an evidence directory's own SHA256SUMS and return its entry count."""
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
        assert _sha256(target) == digest, (
            f"{artifact_dir}: SHA256 mismatch for {relative}"
        )
        entries += 1
    assert entries > 0, f"{artifact_dir}/SHA256SUMS has no entries"
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


def test_schema_and_identity_policy_contract(summary):
    assert summary["schema_version"] == 1
    assert summary["kind"] == "provider_coverage"
    assert summary["worktree"]["commit"].startswith("725e7bb")
    rows = _rows(summary)
    assert len(rows) >= 8
    for row in rows:
        missing = ROW_REQUIRED_FIELDS - set(row)
        assert not missing, f"{row.get('row_id')}: missing fields {sorted(missing)}"
        assert row["status"] in VALID_STATUSES, row["status"]
        assert isinstance(row["limitations"], list)
        source = row["source"]
        for key in ("artifact_dir", "files", "sha256sums",
                    "corroborating_files", "reference_docs"):
            assert key in source, f"{row['row_id']}: source.{key} missing"

    policy = summary["identity_policy"]
    assert policy["served_model_attribution"] is True
    assert policy["applied_in_this_artifact"] is True
    assert "identity_ok=true" in policy["rule"]
    assert "identity_ok=false" in policy["identity_ok_false"]
    assert "BINARYREPAIR_STRICT_MODEL_IDENTITY=1" == policy["strict_identity_env"]


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
        entries = _verify_sha256sums_dir(source["artifact_dir"])
        assert sums["entries"] == entries
    assert checked_files >= 30, checked_files

    # The frozen evidence directories themselves still validate end to end.
    for artifact_dir in (
        "artifacts/multi-model-matrix-2026-11-14",
        "artifacts/multi-model-matrix-intl-2026-11-14",
        "artifacts/multi-model-matrix-cn-2026-11-14",
        "artifacts/provider-matrix-2026-11-14",
        "artifacts/multi-model-probe-2026-11-14",
    ):
        assert _verify_sha256sums_dir(artifact_dir) > 0


# ---------------------------------------------------------------------------
# Identity policy and honest status invariants
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
        if row["status"].startswith("identity_verified"):
            assert row["identity_ok"] is True and row["identity_verified"] is True
            assert row["cases"] == 12
            assert row["ai_verified_attributed_to"] == row["model_served"]
        if row["status"] == "served_model_mismatch_completed":
            assert row["model_served"] != row["model_requested"]
            assert row["ai_verified"] is not None
            assert row["ai_verified_attributed_to"] == row["model_served"]
            text = " ".join(row["limitations"]).lower()
            assert "must not be presented" in text or "not be presented" in text
            assert "served" in text
    assert completed, "no identity-verified completed rows"
    assert len(mismatch) == summary["aggregate"]["identity_mismatch_rows"] == 2
    # A served-model alias is never listed as requested-model coverage.
    assert "deepseek-chat" not in summary["aggregate"]["identity_verified_models"]
    assert summary["aggregate"]["served_model_only_completed_rows"] == 1


def test_no_provider_claim_without_artifact(summary):
    for row in _rows(summary):
        source = row["source"]
        if row["status"] == "unavailable_no_artifact":
            assert source["artifact_dir"] is None
            assert source["files"] == []
            assert row["cases"] == 0
            assert row["ai_verified"] is None
            continue
        assert source["artifact_dir"], row["row_id"]
        assert source["files"], row["row_id"]
        if row["status"] == "blocked_unavailable":
            assert row["benchmark_executed"] is False
            assert row["cases"] == 0
            assert row["ai_verified"] is None
            assert row.get("blocked_reason"), row["row_id"]
        elif row["status"] == "probe_only_identity_mismatch":
            assert row["benchmark_executed"] is False
            assert row["cases"] == 0
            assert row["ai_verified"] is None
        else:
            assert row["benchmark_executed"] is True
            assert row["cases"] == 12
        if row["ai_verified"] is not None:
            assert row["status"] in COMPLETED_STATUSES, row["row_id"]


def test_referenced_but_unavailable_providers_are_explicit(summary):
    rows = _rows(summary)
    blocked = [r for r in rows if r["status"] == "blocked_unavailable"]
    assert blocked
    for row in blocked:
        assert row["benchmark_executed"] is False
        assert row["ai_verified"] is None
        assert row["blocked_reason"]
    intl = [r for r in blocked if r["provider"] == "siliconflow-intl"]
    assert len(intl) == 3
    assert all(r.get("http_status") == 402 for r in intl)
    assert all("402" in r["blocked_reason"] for r in intl)
    glm = [r for r in blocked if r["model_requested"] == "THUDM/GLM-Z1-9B-0414"]
    assert len(glm) == 1 and "timed out" in glm[0]["blocked_reason"].lower()
    no_artifact = [r for r in rows if r["status"] == "unavailable_no_artifact"]
    assert len(no_artifact) == 1
    assert no_artifact[0]["provider"] == "dashscope"
    assert no_artifact[0]["cases"] == 0


# ---------------------------------------------------------------------------
# Evidence values are re-derived from the cited source artifacts
# ---------------------------------------------------------------------------


def test_deepseek_matrix_rows_match_source_artifact(summary):
    rows = _rows_by_id(summary)
    aggregate = _load_json("artifacts/multi-model-matrix-2026-11-14/aggregate.json")
    probe = _load_json(
        "artifacts/multi-model-matrix-2026-11-14/provider-probe.json"
    )
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
        assert row["cases"] == aggregate["cases"] == 12
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
            item for item in matrix["records"]
            if item["model_requested"] == model
        )
        assert record["status"] == "ok"
        assert record["model_identity_ok"] is True
        assert record["model_returned"] == model
        assert record["benchmark"]["cases"] == 12
        benchmark = _load_json(
            f"artifacts/multi-model-matrix-cn-2026-11-14/benchmarks/"
            f"siliconflow-{slug}/summary.json"
        )
        assert len(benchmark["cases"]) == row["cases"] == 12
        assert benchmark["ai_verified"] == row["ai_verified"] == 0
        assert benchmark["baseline_verified"] == 0
        assert row["status"] == "identity_verified_completed"


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
            item for item in matrix["records"]
            if item["model_requested"] == model
        )
        assert record["status"] == "error"
        assert "402" in record["error"]
        probe_record = next(
            item for item in identity["records"]
            if item["model_requested"] == model
        )
        assert probe_record["status"] == "ok"
        assert probe_record["model_identity_ok"] is True
        assert row["status"] == "blocked_unavailable"
        assert row["http_status"] == 402
        assert row["cases"] == 0 and row["ai_verified"] is None


def test_provider_matrix_mismatch_row_matches_source_artifact(summary):
    rows = _rows_by_id(summary)
    row = next(
        item for item in rows.values()
        if item["status"] == "served_model_mismatch_completed"
    )
    matrix = _load_json("artifacts/provider-matrix-2026-11-14/summary.json")
    provider = matrix["provider"]
    assert provider["model_requested"] == row["model_requested"] == "deepseek-chat"
    assert provider["model_returned"] == row["model_served"] == "deepseek-flash"
    assert provider["model_identity_ok"] is False
    assert matrix["provider_status"] == "ok"
    assert matrix["aggregate"]["ai_target_verified"] == row["ai_verified"] == 6
    assert matrix["aggregate"]["cases"] == row["cases"] == 12
    assert row["identity_ok"] is False and row["identity_verified"] is False
    assert row["ai_verified_attributed_to"] == "deepseek-flash"


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
    assert probe_row["cases"] == 0 and probe_row["ai_verified"] is None

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
# Aggregate math and requirement claims
# ---------------------------------------------------------------------------


def test_aggregate_counts_are_re_derived_from_rows(summary):
    rows = _rows(summary)
    aggregate = summary["aggregate"]
    completed = [r for r in rows if r["status"] == "identity_verified_completed"]
    served_mismatch = [
        r for r in rows if r["status"] == "served_model_mismatch_completed"
    ]
    blocked = [r for r in rows if r["status"] == "blocked_unavailable"]
    completed_providers = sorted({r["provider"] for r in completed})
    blocked_providers = sorted(
        {r["provider"] for r in blocked} - set(completed_providers)
    )
    assert aggregate["providers_completed_12case"] == len(completed_providers) == 2
    assert aggregate["providers_completed"] == completed_providers
    assert aggregate["providers_blocked"] == len(blocked_providers) == 1
    assert aggregate["providers_blocked_list"] == blocked_providers
    assert aggregate["models_completed_12case"] == len(completed) == 4
    assert sorted(aggregate["identity_verified_models"]) == sorted(
        r["model_served"] for r in completed
    )
    assert aggregate["identity_verified_models_count"] == len(completed)
    assert aggregate["identity_mismatch_rows"] == (
        len(served_mismatch)
        + sum(1 for r in rows if r["status"] == "probe_only_identity_mismatch")
    )
    assert aggregate["served_model_only_completed_rows"] == len(served_mismatch) == 1
    assert aggregate["no_overclaim"] is True
    by_model = aggregate["ai_verified_by_completed_model"]
    for row in completed:
        info = by_model[row["model_served"]]
        assert info["runs"] == row["runs"]
        assert info["per_run_ai_verified"] == row["runs_ai_verified"]
        assert info["provider"] == row["provider"]
    assert aggregate["served_model_attribution_runs"][0]["served_model"] == (
        "deepseek-flash"
    )


def test_requirement_claims_are_honest(summary):
    aggregate = summary["aggregate"]
    requirements = aggregate["requirements"]
    assert requirements["at_least_2_models_12case"]["satisfied"] is True
    assert requirements["at_least_2_models_12case"]["observed"] == 4
    assert requirements["at_least_2_providers_12case"]["satisfied"] is True
    assert requirements["at_least_2_providers_12case"]["observed"] == 2
    assert sorted(requirements["at_least_2_providers_12case"]["evidence"]) == [
        "deepseek-official", "siliconflow-cn",
    ]
    five = requirements["five_model_international_matrix"]
    assert five["satisfied"] is False
    assert "402" in five["reason"]
    assert requirements["identity_policy_applied"]["satisfied"] is True

    # Transparent reconciliation with the phase-4 brief expectation.
    check = aggregate["brief_expectation_check"]
    assert check["brief_expected"] == {
        "providers_completed": 1, "providers_blocked": 1,
    }
    assert check["observed"] == {
        "providers_completed": aggregate["providers_completed_12case"],
        "providers_blocked": aggregate["providers_blocked"],
    }
    assert "siliconflow-cn" in check["explanation"].lower()
    assert "limitations" in check["explanation"].lower()

    assert summary["blocked_reasons"]
    blocked_providers = {item["provider"] for item in summary["blocked_reasons"]}
    assert {"siliconflow-intl", "dashscope"} <= blocked_providers
    assert summary["next_steps"]
    assert summary["limitations"]


def test_readme_documents_policy_and_blockers():
    text = README_PATH.read_text(encoding="utf-8")
    assert "identity_ok=false" in text
    assert "HTTP 402" in text
    assert "providers_completed" in text
    assert "not satisfied" in text.lower()
    assert "SHA-256" in text or "sha256" in text.lower()
    assert "Limitations" in text or "limitations" in text
