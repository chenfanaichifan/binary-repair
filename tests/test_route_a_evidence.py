"""Unit tests for the Route A host evidence validator (P0 trust boundary).

The host recomputes V0/V1/V2 and validates V3/V4/V5 evidence structure; each
test asserts the precise gate result and reason category, never just "not a
success".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.route_a_evidence import (
    REASON_PREFIXES,
    RouteAEvidenceError,
    validate_route_a_bundle,
    validate_route_a_record,
)
from tests.routea_fixtures import (
    CONTRACT,
    ORIGINAL_ELF,
    build_route_a_bundle,
    change_entry,
    formal_v5_evidence,
)


def _validate(bundle: Path, **kwargs):
    return validate_route_a_bundle(
        bundle,
        original_elf=ORIGINAL_ELF,
        contract_body=CONTRACT,
        contract_file=None,
        **kwargs,
    )


def _assert_reason(detail: str) -> None:
    assert detail.startswith(REASON_PREFIXES), detail


def _statuses(validation) -> dict[str, str]:
    return validation.results


def test_all_six_gates_pass_on_a_consistent_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    meta = build_route_a_bundle(bundle, claims=None)

    validation = _validate(bundle)

    assert _statuses(validation) == {gate: "passed" for gate in ("V0", "V1", "V2", "V3", "V4", "V5")}
    assert validation.candidate_sha256 == meta["candidate_sha256"]
    for detail in validation.details.values():
        _assert_reason(detail)
    # V2 was recomputed by the product check, not copied from the claim file.
    assert validation.findings["V2"].generated is not None
    assert validation.findings["V2"].generated["score"] == {"passed": 5, "total": 5}


def test_bundle_without_candidate_is_fatal(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()

    with pytest.raises(RouteAEvidenceError) as raised:
        _validate(bundle)

    assert "candidate.elf" in str(raised.value)


def test_v0_missing_status_is_not_run(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle, include={"V1", "V2", "V3", "V4", "V5"})

    validation = _validate(bundle)

    assert validation.findings["V0"].status == "not_run"
    assert validation.details["V0"].startswith("missing:")


def test_v0_identity_mismatch_is_a_check_failure(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle)
    status_path = bundle / "route_a" / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["original_sha256"] = "0" * 64
    status_path.write_text(json.dumps(status), encoding="utf-8")

    validation = _validate(bundle)

    assert validation.findings["V0"].status == "failed"
    assert validation.details["V0"].startswith("check_failed:")


def test_v0_accepts_a_reviewed_contract_file_that_is_not_normalised(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle)
    # The reviewed contract file may be pretty-printed; its canonical hash must
    # come from the product rule, not from a plain JSON-dumps digest, otherwise
    # a real bundle can never match the reviewed contract.
    pretty = json.dumps(CONTRACT, indent=2, sort_keys=True) + "\n"
    (bundle / "contract.json").write_text(pretty, encoding="utf-8")
    contract_file = tmp_path / "reviewed-contract.json"
    contract_file.write_text(pretty, encoding="utf-8")

    validation = validate_route_a_bundle(
        bundle,
        original_elf=ORIGINAL_ELF,
        contract_body=CONTRACT,
        contract_file=contract_file,
    )

    assert validation.findings["V0"].status == "passed"
    assert (
        validation.findings["V0"].checks["status_contract_sha256"]
        == validation.contract_canonical_sha256
    )


def test_v1_audit_failure_is_a_check_failure(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle, audit_pass=False)

    validation = _validate(bundle)

    assert validation.findings["V1"].status == "failed"
    assert validation.details["V1"].startswith("check_failed:")


def test_v1_missing_artifacts_is_not_run(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle, include={"V0", "V2", "V3", "V4", "V5"})

    validation = _validate(bundle)

    assert validation.findings["V1"].status == "not_run"
    assert validation.details["V1"].startswith("missing:")


def test_v2_recomputed_failure_ignores_a_passing_claim(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    original = ORIGINAL_ELF.read_bytes()
    build_route_a_bundle(bundle, candidate_bytes=change_entry(original))

    validation = _validate(bundle)

    assert validation.findings["V2"].status == "failed"
    assert validation.details["V2"].startswith("check_failed:")
    # The producer's observation file still says pass; the host must not copy it.
    claim = json.loads((bundle / "evidence" / "v2" / "interface.json").read_text(encoding="utf-8"))
    assert claim["status"] == "pass"


def test_v3_observed_failure_is_a_check_failure(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle, v3_ok=False)

    validation = _validate(bundle)

    assert validation.findings["V3"].status == "failed"
    assert validation.details["V3"].startswith("check_failed:")


def test_v3_manifest_for_another_candidate_is_invalid(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle)
    path = bundle / "evidence" / "v3" / "manifest-repaired.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["candidate_sha256"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")

    validation = _validate(bundle)

    assert validation.findings["V3"].status == "not_run"
    assert validation.details["V3"].startswith("invalid:")


def test_v3_missing_manifest_is_not_run(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle, include={"V0", "V1", "V2", "V4", "V5"})

    validation = _validate(bundle)

    assert validation.findings["V3"].status == "not_run"
    assert validation.details["V3"].startswith("missing:")


def test_v4_producer_marker_without_independent_replay_is_invalid(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle, v4_verified_by=None)

    validation = _validate(bundle)

    assert validation.findings["V4"].status == "not_run"
    assert validation.details["V4"].startswith("invalid:")


def test_v4_missing_marker_is_not_run(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle, include={"V0", "V1", "V2", "V3", "V5"})

    validation = _validate(bundle)

    assert validation.findings["V4"].status == "not_run"
    assert validation.details["V4"].startswith("missing:")


def test_v5_without_independent_replay_is_invalid(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle, v5_independent_replay=False)

    validation = _validate(bundle)

    assert validation.findings["V5"].status == "not_run"
    assert validation.details["V5"].startswith("invalid:")


def test_v5_replay_with_different_bytes_is_a_check_failure(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    meta = build_route_a_bundle(bundle)
    build_route_a_bundle(
        bundle,
        v5_sha256=[meta["candidate_sha256"], "1" * 64],
    )

    validation = _validate(bundle)

    assert validation.findings["V5"].status == "failed"
    assert validation.details["V5"].startswith("check_failed:")


def test_bundle_claim_conflict_is_reported_but_never_promotes(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(
        bundle,
        include={"V0", "V1", "V2", "V3", "V4"},
        claims={gate: "passed" for gate in ("V0", "V1", "V2", "V3", "V4", "V5")},
    )

    validation = _validate(bundle)

    assert validation.findings["V5"].status == "not_run"
    assert "bundle claimed passed" in validation.details["V5"]
    assert "host recomputed not_run" in validation.details["V5"]


def test_host_verification_record_round_trip(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    meta = build_route_a_bundle(bundle)
    validation = _validate(bundle)
    sources = [
        {"artifact_id": "a" * 32, "path": "route_a/audit.json", "sha256": "b" * 64}
    ]
    record = validation.findings["V1"].as_record(
        source_artifacts=sources,
        candidate_sha256=meta["candidate_sha256"],
        original_sha256=meta["original_sha256"],
        contract_canonical_sha256=meta["contract_sha256"],
    )
    record["checks"] = {
        "audit_pass": True,
        "edit_manifest_bound": True,
        "readelf_present": True,
        "lief_present": True,
    }

    validate_route_a_record(
        record,
        gate="V1",
        candidate_sha256=meta["candidate_sha256"],
        original_sha256=meta["original_sha256"],
        contract_canonical_sha256=meta["contract_sha256"],
    )

    record["checks"]["audit_pass"] = False
    with pytest.raises(RouteAEvidenceError) as raised:
        validate_route_a_record(
            record,
            gate="V1",
            candidate_sha256=meta["candidate_sha256"],
            original_sha256=meta["original_sha256"],
        )
    assert "audit_pass" in str(raised.value)


def test_v5_accepts_a_formal_clean_snapshot_record(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle)
    (bundle / "evidence" / "v5").mkdir(parents=True, exist_ok=True)
    (bundle / "evidence" / "v5" / "formal-v5.json").write_text(
        json.dumps(formal_v5_evidence(bundle)), encoding="utf-8"
    )

    validation = _validate(bundle)

    assert validation.findings["V5"].status == "passed"
    assert validation.findings["V5"].checks["formal_v5"] is True
    assert validation.findings["V5"].checks["restore_snapshot"] == "p1-prewindow-20261107"


def test_v5_rejects_a_formal_record_with_a_non_independent_review(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle)
    (bundle / "evidence" / "v5").mkdir(parents=True, exist_ok=True)
    (bundle / "evidence" / "v5" / "formal-v5.json").write_text(
        json.dumps(formal_v5_evidence(bundle, review_independent=False)),
        encoding="utf-8",
    )

    validation = _validate(bundle)

    assert validation.findings["V5"].status == "not_run"
    assert validation.details["V5"].startswith("invalid:")
