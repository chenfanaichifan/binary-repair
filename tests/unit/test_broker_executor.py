"""Tests for the host-safe guest broker executor (T6.2).

These tests assert the *host side* never executes, never builds a shell
string, never accepts a path or an argv array, and fails closed on any
unregistered artifact id or hash gap. They do not require the guest.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from workers.broker import (
    Operation,
    build_task_request,
    validate_operation,
)

SHA = "aa" * 32


def _verify_op(candidate_id="cand-1", evidence_id="ev-1"):
    return {
        "kind": "verify",
        "candidate": {"artifact_id": candidate_id, "sha256": SHA},
        "obligation": "behaviour",
        "evidence_artifact_id": evidence_id,
    }


# ---- fixed operation list is closed ---------------------------------------


def test_all_six_operations_parse():
    samples = {
        "analyze": {"kind": "analyze", "binary": {"artifact_id": "b", "sha256": SHA},
                    "target_entry": "badSink"},
        "assemble": {"kind": "assemble", "base_binary": {"artifact_id": "b", "sha256": SHA},
                     "edits": [(0x4012C0, "e93b4d0000909090")], "out_artifact_id": "o"},
        "compile": {"kind": "compile", "source_artifact_id": "s", "out_artifact_id": "o"},
        "apply": {"kind": "apply", "base_binary": {"artifact_id": "b", "sha256": SHA},
                  "candidate_artifact_id": "c", "out_artifact_id": "o",
                  "scope_authorized": True},
        "test": {"kind": "test", "candidate": {"artifact_id": "c", "sha256": SHA},
                 "manifest_artifact_id": "m", "mode": "repaired"},
        "verify": _verify_op(),
    }
    for kind, payload in samples.items():
        op = validate_operation(payload)
        assert op.kind == kind


def test_unknown_operation_rejected():
    with pytest.raises(ValueError, match="unknown operation"):
        validate_operation({"kind": "rm -rf", "path": "/etc"})


def test_operation_enum_is_closed():
    assert {o.value for o in Operation} == {
        "analyze", "assemble", "compile", "apply", "test", "verify",
    }


# ---- no path, no shell, no argv -------------------------------------------


def test_artifact_id_cannot_be_a_path():
    with pytest.raises(ValidationError):
        validate_operation(_verify_op(candidate_id="../../etc/passwd"))


def test_artifact_id_requires_sha256():
    payload = _verify_op()
    del payload["candidate"]["sha256"]
    with pytest.raises(ValidationError):
        validate_operation(payload)


def test_sha256_must_be_64_hex():
    payload = _verify_op()
    payload["candidate"]["sha256"] = "not-a-hash"
    with pytest.raises(ValidationError):
        validate_operation(payload)


def test_assemble_edits_must_be_even_hex():
    with pytest.raises(ValidationError):
        validate_operation({
            "kind": "assemble",
            "base_binary": {"artifact_id": "b", "sha256": SHA},
            "edits": [(0x4012C0, "zz")],
            "out_artifact_id": "o",
        })


def test_assemble_edits_vaddr_nonnegative():
    with pytest.raises(ValidationError):
        validate_operation({
            "kind": "assemble",
            "base_binary": {"artifact_id": "b", "sha256": SHA},
            "edits": [(-1, "90")],
            "out_artifact_id": "o",
        })


def test_apply_scope_authorized_defaults_false():
    op = validate_operation({
        "kind": "apply",
        "base_binary": {"artifact_id": "b", "sha256": SHA},
        "candidate_artifact_id": "c",
        "out_artifact_id": "o",
    })
    assert op.scope_authorized is False


# ---- fail closed on unregistered artifacts ---------------------------------


def test_unregistered_artifact_rejected():
    with pytest.raises(ValueError, match="unregistered"):
        build_task_request(
            job_id="j1", run_id="r1", idempotency_key="k" * 16,
            operations=[_verify_op()],
            allowed_artifact_ids=frozenset(),
        )


def test_registered_artifact_accepted():
    req = build_task_request(
        job_id="j1", run_id="r1", idempotency_key="k" * 16,
        operations=[_verify_op()],
        allowed_artifact_ids=frozenset({"cand-1", "ev-1"}),
    )
    assert req.request_hash()
    assert req.operations[0].kind == "verify"


def test_empty_operations_rejected():
    with pytest.raises(ValidationError):
        build_task_request(
            job_id="j1", run_id="r1", idempotency_key="k" * 16,
            operations=[],
            allowed_artifact_ids=frozenset(),
        )


def test_extra_fields_forbidden():
    payload = _verify_op()
    payload["shell"] = "bash -c rm -rf /"
    with pytest.raises(ValidationError):
        validate_operation(payload)


# ---- resource limits -------------------------------------------------------


def test_resource_limits_defaults():
    from workers.broker import ResourceLimits
    limits = ResourceLimits()
    assert limits.cpu_seconds == 300
    assert limits.as_gib == 4
    assert limits.nofile == 1024
    assert limits.fsize_mib == 256


def test_resource_limits_clamp_negative():
    from workers.broker import ResourceLimits
    with pytest.raises(ValidationError):
        ResourceLimits(cpu_seconds=-1)


def test_request_hash_is_stable():
    a = build_task_request(
        job_id="j1", run_id="r1", idempotency_key="k" * 16,
        operations=[_verify_op()], allowed_artifact_ids=frozenset({"cand-1", "ev-1"}),
    )
    b = build_task_request(
        job_id="j1", run_id="r1", idempotency_key="k" * 16,
        operations=[_verify_op()], allowed_artifact_ids=frozenset({"cand-1", "ev-1"}),
    )
    assert a.request_hash() == b.request_hash()
