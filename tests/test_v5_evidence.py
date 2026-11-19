"""Tests for the formal V5 clean-snapshot replay schema (2026-11-19 spec)."""

from __future__ import annotations

import pytest

from app.domain.v5 import (
    V5EvidenceError,
    manifest_files,
    manifest_sha256,
    validate_v5_evidence,
)
from tests.routea_fixtures import build_route_a_bundle, formal_v5_evidence


def _bundle(tmp_path):
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle)
    return bundle, formal_v5_evidence(bundle)


def _validate(data, bundle, **kwargs):
    return validate_v5_evidence(
        data,
        candidate_sha256=data["candidate_sha256"],
        original_sha256=data["original_sha256"],
        test_manifest_sha256=manifest_sha256(manifest_files(bundle / "tests")),
        **kwargs,
    )


def test_a_consistent_record_is_accepted(tmp_path) -> None:
    bundle, data = _bundle(tmp_path)

    evidence = _validate(data, bundle)

    assert evidence.state == "passed"
    assert evidence.restore_receipt.snapshot_name == "p1-prewindow-20261107"
    assert evidence.review.independent is True
    assert evidence.behavior[0].ok is True


def test_missing_restore_receipt_is_rejected(tmp_path) -> None:
    bundle, data = _bundle(tmp_path)
    del data["restore_receipt"]

    with pytest.raises(V5EvidenceError):
        _validate(data, bundle)


def test_nonzero_restore_exit_is_rejected(tmp_path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle)
    data = formal_v5_evidence(bundle, revert_exit_code=1)

    with pytest.raises(V5EvidenceError):
        _validate(data, bundle)


def test_non_independent_review_is_rejected(tmp_path) -> None:
    bundle = tmp_path / "bundle"
    build_route_a_bundle(bundle)
    data = formal_v5_evidence(bundle, review_independent=False)

    with pytest.raises(V5EvidenceError):
        _validate(data, bundle)


def test_a_case_mismatch_is_rejected(tmp_path) -> None:
    bundle, data = _bundle(tmp_path)
    data["behavior"][0]["observed_return_code"] = 1
    data["behavior"][0]["ok"] = False

    with pytest.raises(V5EvidenceError):
        _validate(data, bundle)


def test_a_wrong_manifest_hash_is_rejected(tmp_path) -> None:
    bundle, data = _bundle(tmp_path)

    with pytest.raises(V5EvidenceError):
        validate_v5_evidence(
            data,
            candidate_sha256=data["candidate_sha256"],
            original_sha256=data["original_sha256"],
            test_manifest_sha256="0" * 64,
        )


def test_a_wrong_candidate_binding_is_rejected(tmp_path) -> None:
    bundle, data = _bundle(tmp_path)

    with pytest.raises(V5EvidenceError):
        validate_v5_evidence(
            data,
            candidate_sha256="0" * 64,
            original_sha256=data["original_sha256"],
            test_manifest_sha256=manifest_sha256(manifest_files(bundle / "tests")),
        )


def test_an_incomplete_isolation_attestation_is_rejected(tmp_path) -> None:
    bundle, data = _bundle(tmp_path)
    data["isolation"]["no_new_privs"] = "0"

    with pytest.raises(V5EvidenceError):
        _validate(data, bundle)
