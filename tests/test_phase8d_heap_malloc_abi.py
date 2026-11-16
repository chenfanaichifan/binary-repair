"""D04 heap-malloc ABI root-cause artifact tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/phase8d-heap-malloc-abi-2026-11-17"
SCRIPT = ROOT / "scripts/analyze_phase8d_heap_malloc_abi.py"
EXPECTED_CANDIDATE = "ea22260535efca37dca19404c700ce29e6da1f45b3af24d3903c8d27fdf6fb73"
EXPECTED_ORIGINAL = "0f65a2d2ffe1ebf91f717d5edc78928cb8ee219e3f73e623b256f87bdcc4381f"


def _analysis() -> dict:
    return json.loads((ARTIFACT / "abi-analysis.json").read_text(encoding="utf-8"))


def test_artifact_checks_clean_offline() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"], cwd=str(ROOT),
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is True


def test_candidate_and_original_hashes_are_stable() -> None:
    analysis = _analysis()
    assert analysis["fixture"]["sha256"] == EXPECTED_ORIGINAL
    assert analysis["candidate"]["sha256"] == EXPECTED_CANDIDATE
    assert analysis["candidate"]["matches_phase8c_candidate"] is True
    assert (ARTIFACT / "candidate.bin").read_bytes()


def test_verifier_remains_rejected_and_abi_is_the_failed_check() -> None:
    analysis = _analysis()
    verifier = analysis["verifier"]
    assert verifier["decision"] == "rejected"
    assert verifier["abi_status"] == "failed"
    assert verifier["runtime_oracle_status"] == "passed"
    assert verifier["layout_passed"] is True
    assert verifier["target_scope_passed"] is True
    assert verifier["decision"] != "verified"


def test_declared_function_block_is_not_the_injected_cave() -> None:
    analysis = _analysis()
    plan = analysis["plan"]
    block = plan["abi_blocks"][0]
    cave = plan["cave"]
    assert int(block["va"]) != int(cave["va"])
    assert block["evidence_sha256"] == analysis["function_abi"]["block_sha256"]
    assert cave["size"] > 0
    assert analysis["cave_abi"]["ok"] is True
    assert analysis["cave_abi"]["fatal"] == 0


def test_control_flow_targets_are_resolved_to_imported_symbols() -> None:
    analysis = _analysis()
    by_symbol = {
        item.get("slot_symbol"): item for item in analysis["control_flow_resolution"]
        if item.get("slot_symbol")
    }
    assert set(by_symbol) == {"malloc", "puts", "free"}
    assert by_symbol["malloc"]["mnemonic"] == "call"
    assert by_symbol["puts"]["mnemonic"] == "call"
    assert by_symbol["free"]["mnemonic"] == "jmp"
    assert by_symbol["free"]["tail_call"] is True
    assert by_symbol["malloc"]["slot_va"] == "0x403fe0"
    assert by_symbol["puts"]["slot_va"] == "0x403fd0"
    assert by_symbol["free"]["slot_va"] == "0x403fb8"


def test_classifications_are_explicit_and_exclude_invalid_candidate() -> None:
    analysis = _analysis()
    rows = {item["root"]: item for item in analysis["classifications"]}
    assert rows["generator_plan_incorrect"]["primary"] is True
    assert rows["abi_proof_insufficient"]["primary"] is True
    assert rows["verifier_rule_incorrect"]["primary"] is False
    assert rows["analysis_evidence_insufficient"]["primary"] is False
    assert rows["generator_patch_invalid"]["excluded"] is True
    assert rows["root_cause_inconclusive"]["excluded"] is True
    assert analysis["rule_modifications"] == []
    assert analysis["cave_abi"]["ok"] is True
    assert analysis["function_abi"]["ok"] is False


def test_artifact_has_no_hidden_material_or_hidden_paths() -> None:
    analysis = _analysis()
    text = json.dumps(analysis, sort_keys=True).lower()
    assert "phase8c-hidden" not in text
    assert "/.binaryrepair/" not in text
    readme = (ARTIFACT / "README.md").read_text(encoding="utf-8").lower()
    assert "hidden" not in readme


def test_tampered_artifact_is_detected(tmp_path: Path) -> None:
    target = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, target)
    analysis_path = target / "abi-analysis.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    analysis["candidate"]["sha256"] = "0" * 64
    analysis_path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    # The copied SHA256SUMS is now stale and the check must fail.
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check", "--artifact-dir", str(target)],
        cwd=str(ROOT), capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 1
    assert "sha256 mismatch" in result.stdout or "candidate hash" in result.stdout


def test_cave_branches_are_internal_and_do_not_resolve_outside() -> None:
    analysis = _analysis()
    rows = analysis["cave_block"]["control_flow_resolution"]
    assert [row["mnemonic"] for row in rows] == ["jae", "jne"]
    assert [row["target_va"] for row in rows] == [0x40501B, 0x405002]
    assert all(row["kind"] == "direct" for row in rows)
