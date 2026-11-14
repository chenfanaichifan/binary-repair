"""Tests for the acceptance invariant engine (fail-closed packet invariants)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import acceptance_invariants as inv  # noqa: E402

ACCEPTANCE = ROOT / "artifacts" / "coverage-closure-2026-11-14" / "acceptance.json"

PROFILE_REQUIRED = [
    "format", "candidate.present", "candidate.identity.original",
    "candidate.identity.patched", "container.reparse", "repair.action",
    "runtime.evidence", "runtime.tier", "runtime.contract",
    "poc.native.available", "poc.native.original_failure",
    "poc.native.candidate_pass", "poc.native.regression",
    "poc.native.stdout_signature",
]


def _checks(ids: list[str]) -> list[dict]:
    return [{"id": check_id, "status": "passed", "required": True}
            for check_id in ids]


def _verified_packet(**overrides: object) -> dict:
    packet = {
        "checks": _checks(PROFILE_REQUIRED + ["patch.target_scope",
                                             "patch.rewrite"]),
        "scope": {
            "profile": "native_poc",
            "target_policy": "target_scoped",
            "target_scope": {"name": "heap_bad", "va": 0x401130,
                             "end": 0x40116C},
        },
        "candidate_sha256": "ab" * 32,
        "evidence_sha256": "cd" * 32,
        "gate": {"outcome": "verified", "success": True},
        "actions": [{"kind": "guard", "site_va": 0x40114D}],
        "rewrite_actions": [
            {"offset": 0, "size": 1, "before_hex": "00", "after_hex": "01"},
        ],
        "disposition": "verified_patch",
        "verified": True,
        "download_allowed": True,
        "profile": "native_poc",
        "with_manifest": True,
        "poc": {"schema_version": 1, "status": "pass"},
    }
    packet.update(overrides)
    return packet


def test_verified_packet_is_accepted() -> None:
    result = inv.check_packet(_verified_packet())
    assert result["ok"], result["violations"]
    assert result["checked"]["verified"] is True


def test_failed_required_check_cannot_be_verified() -> None:
    packet = _verified_packet()
    packet["checks"][0]["status"] = "failed"
    result = inv.check_packet(packet)
    assert not result["ok"]
    assert any("failed required checks" in item for item in result["violations"])


def test_not_run_required_check_cannot_verified_or_download() -> None:
    packet = _verified_packet()
    packet["checks"][1]["status"] = "not_run"
    result = inv.check_packet(packet)
    assert not result["ok"]
    assert any("not_run" in item for item in result["violations"])


def test_verified_needs_candidate_and_evidence_sha() -> None:
    packet = _verified_packet(candidate_sha256="", evidence_sha256="")
    result = inv.check_packet(packet)
    assert any("candidate sha256" in item for item in result["violations"])
    assert any("evidence sha256" in item for item in result["violations"])


def test_rejected_needs_reason_or_failed_check() -> None:
    packet = {
        "disposition": "rejected",
        "checks": [{"id": "repair.action", "status": "passed"}],
        "verified": False,
        "download_allowed": False,
    }
    result = inv.check_packet(packet)
    assert not result["ok"]
    packet["error"] = "no reviewed action"
    assert inv.check_packet(packet)["ok"]


def test_analysis_only_and_inconclusive_cannot_download() -> None:
    for packet in (
        {"disposition": "analysis_only", "verified": False,
         "download_allowed": True},
        {"gate_outcome": "inconclusive", "verified": True,
         "download_allowed": True},
    ):
        result = inv.check_packet(packet)
        assert not result["ok"]
        assert any("cannot" in item for item in result["violations"])


def test_target_scope_requires_passed_check_and_inside_actions() -> None:
    packet = _verified_packet()
    packet["checks"] = _checks(PROFILE_REQUIRED)  # no patch.target_scope
    result = inv.check_packet(packet)
    assert any("patch.target_scope" in item for item in result["violations"])

    packet = _verified_packet()
    packet["actions"] = [{"kind": "guard", "site_va": 0x900000}]
    result = inv.check_packet(packet)
    assert any("outside the declared target scope" in item
               for item in result["violations"])

    packet = _verified_packet()
    packet["actions"] = [{"kind": "guard"}]
    result = inv.check_packet(packet)
    assert any("no numeric site_va" in item for item in result["violations"])


def test_target_scope_without_declanation_is_a_violation() -> None:
    packet = _verified_packet()
    packet["scope"] = {"profile": "native_poc"}
    packet["disposition"] = "analysis_only"
    packet["verified"] = False
    packet["download_allowed"] = False
    packet["checks"] = _checks(PROFILE_REQUIRED + ["patch.target_scope"])
    result = inv.check_packet(packet)
    assert any("without a declared target scope" in item
               for item in result["violations"])


def test_target_policy_enum_and_honesty() -> None:
    packet = _verified_packet()
    packet["scope"]["target_policy"] = "whole_image"
    result = inv.check_packet(packet)
    assert any("claims target identity" in item for item in result["violations"])

    packet = _verified_packet()
    packet["scope"]["target_policy"] = "analysis_only"
    result = inv.check_packet(packet)
    assert any("cannot be verified" in item for item in result["violations"])

    packet = _verified_packet()
    packet["scope"]["target_policy"] = "made_up"
    result = inv.check_packet(packet)
    assert any("is not one of" in item for item in result["violations"])


def test_manifest_evidence_cannot_use_legacy_check_ids() -> None:
    packet = _verified_packet()
    packet["checks"] = _checks(PROFILE_REQUIRED + [
        "strict.reviewed_template", "runtime.cases"])
    packet["scope"].pop("target_scope")
    packet["actions"] = []
    packet["disposition"] = "analysis_only"
    packet["verified"] = False
    packet["download_allowed"] = False
    result = inv.check_packet(packet)
    assert any("legacy quick-gate" in item for item in result["violations"])


def test_manifest_evidence_needs_unified_profile() -> None:
    packet = _verified_packet()
    packet.pop("profile")
    packet["scope"].pop("profile")
    result = inv.check_packet(packet)
    assert any("no evidence profile" in item for item in result["violations"])


def test_rewrite_actions_are_validated() -> None:
    packet = _verified_packet()
    packet["rewrite_actions"] = [{"offset": -1, "size": 0,
                                  "before_hex": "zz", "after_hex": "0"}]
    packet["checks"] = [check for check in packet["checks"]
                        if check["id"] not in {"patch.rewrite"}]
    result = inv.check_packet(packet)
    assert any("invalid offset/size" in item for item in result["violations"])
    assert any("not hex bytes" in item for item in result["violations"])
    assert any("no passed patch.rewrite" in item
               for item in result["violations"])


def test_download_requires_verified_candidate() -> None:
    packet = {"disposition": "verified_patch", "verified": False,
              "download_allowed": True, "checks": []}
    result = inv.check_packet(packet)
    assert any("not verified" in item for item in result["violations"])


def test_check_acceptance_handles_committed_summary_records() -> None:
    document = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
    result = inv.check_acceptance(document)
    assert result["packets_checked"] > 0
    assert result["ok"], result["violations"]


def test_check_acceptance_rejects_failed_capture() -> None:
    document = {"passed": False, "failures": ["case x failed"]}
    result = inv.check_acceptance(document)
    assert not result["ok"]
    assert any("passed=false" in item for item in result["violations"])


def test_check_acceptance_validates_packet_list() -> None:
    document = {"passed": True, "failures": [],
                "packets": [_verified_packet()]}
    result = inv.check_acceptance(document)
    assert result["ok"], result["violations"]
    assert result["packets_checked"] == 1

    document["packets"] = [_verified_packet(verified=True,
                                            candidate_sha256="")]
    result = inv.check_acceptance(document)
    assert not result["ok"]
    assert any("packets[0]" in item for item in result["violations"])
