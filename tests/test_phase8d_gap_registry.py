"""Phase-8D additive gap registry tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app.services import phase8d_gap_registry as registry  # noqa: E402
import build_phase8d_gap_registry as builder  # noqa: E402

ARTIFACT = ROOT / "artifacts/phase8d-gap-registry-2026-11-17"
HISTORICAL = ROOT / registry.HISTORICAL_REGISTRY


def _historical_ids() -> list[str]:
    return [str(record.get("gap_id") or "") for record in
            json.loads(HISTORICAL.read_text(encoding="utf-8"))["records"]]


def test_eight_audit_records_validate_and_link_existing_gaps():
    records = registry.make_records()
    ids = _historical_ids()
    result = registry.validate_registry(records, historical_ids=ids)
    assert result["ok"] is True, result["violations"]
    assert result["record_count"] == 8
    assert result["audit_ids"] == list(registry.AUDIT_IDS)
    assert result["auto_promotion"] is False
    assert result["historical_registry_rewritten"] is False
    assert {"D02", "D09", "D10"}.issubset(set(result["dimensions"]))
    for record in records:
        assert record["status"] in {"open", "blocked", "not_run"}
        assert record["false_verified_risk"] in {"high", "critical"}
        assert record["proposed_experiment"]["status"] == "proposed"
        assert set(record["lineage"]["derived_from"]).issubset(set(ids))


def test_registry_has_all_required_fields_and_no_capability_status():
    records = registry.make_records()
    for record in records:
        for field in registry.REQUIRED_FIELDS:
            assert field in record
        assert record["gap_id"].startswith("GAP-8D-AUDIT-")
        assert record["kind"] == "phase8d_gap_record"
        assert record["discovery_source"] == "phase8d_audit"
        assert record["verification_required"] is True
        assert record["limitations"]
        assert record["status"] != "candidate"


def test_unknown_historical_lineage_is_rejected():
    records = registry.make_records()
    broken = json.loads(json.dumps(records[0]))
    broken["lineage"]["derived_from"] = ["GAP-NOT-A-REAL-ID"]
    problems = registry.validate_record(broken, historical_ids=set(_historical_ids()))
    assert any("unknown historical lineage" in item for item in problems)


def test_skipping_dimensions_or_duplicate_ids_is_rejected():
    records = registry.make_records()
    duplicate = [*records, json.loads(json.dumps(records[0]))]
    result = registry.validate_registry(duplicate, historical_ids=_historical_ids())
    assert result["ok"] is False
    assert any("duplicate" in item for item in result["violations"])


def test_builder_artifact_is_deterministic_and_historical_registry_unchanged():
    before = hashlib.sha256(HISTORICAL.read_bytes()).hexdigest()
    first = subprocess.run([sys.executable, str(ROOT / "scripts/build_phase8d_gap_registry.py"), "--json"],
                           cwd=ROOT, capture_output=True, text=True, timeout=60)
    second = subprocess.run([sys.executable, str(ROOT / "scripts/build_phase8d_gap_registry.py"), "--json"],
                            cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
    summary = json.loads(first.stdout)
    assert summary["ok"] is True
    assert summary["record_count"] == 8
    assert summary["capability_promotion"] is False
    assert summary["historical_registry_rewritten"] is False
    assert summary["phase8d_dimensions_covered"] == ["D02", "D09", "D10"]
    after = hashlib.sha256(HISTORICAL.read_bytes()).hexdigest()
    assert before == after


def test_committed_artifact_checks_and_has_all_audits():
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/build_phase8d_gap_registry.py"), "--check", "--json"],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["ok"] is True
    payload = json.loads((ARTIFACT / "gaps.json").read_text(encoding="utf-8"))
    assert payload["kind"] == registry.KIND
    assert payload["record_count"] == 8
    assert payload["audit_ids"] == list(registry.AUDIT_IDS)
    assert payload["historical_registry"]["rewritten"] is False
    assert payload["historical_registry"]["sha256"] == hashlib.sha256(HISTORICAL.read_bytes()).hexdigest()
    assert payload["capability_promotion"] is False
    assert payload["no_auto_promotion"] is True
    assert len({r["gap_id"] for r in payload["records"]}) == 8
    assert (ARTIFACT / "SHA256SUMS").is_file()


def test_tampered_artifact_is_rejected(tmp_path: Path):
    import shutil

    target = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, target)
    payload = json.loads((target / "gaps.json").read_text(encoding="utf-8"))
    payload["records"][0]["status"] = "resolved"
    (target / "gaps.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                                      encoding="utf-8")
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/build_phase8d_gap_registry.py"),
                           "--check", "--out", str(target), "--json"],
                          cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["ok"] is False
