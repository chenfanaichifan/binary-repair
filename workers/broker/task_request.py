"""Guest broker — typed task request (host-safe part).

A task request is what the host hands to the guest broker. It wraps one or more
operations into a single typed unit with:

* an idempotency key (a double submit must not create two charged attempts);
* resource limits (enforced here and re-enforced by jobwrap);
* a fail-closed policy: an unregistered artifact, a hash mismatch, or a
  ``scope_authorized`` gap rejects the whole request before it reaches the
  guest.

This module plans and validates only. It never executes, compiles, or
symbolically analyses a binary, and never builds a shell string or an argv
array.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .operations import (
    AnalyzeOp,
    ApplyOp,
    AssembleOp,
    CompileOp,
    ResourceLimits,
    TestOp,
    VerifyOp,
    validate_operation,
)

IDEMPOTENCY_KEY_RE = r"^[A-Za-z0-9._:-]{8,128}$"


class TaskRequest(BaseModel):
    """One typed request to the guest broker.

    ``operations`` is ordered (the broker runs them sequentially by default).
    ``job_id`` / ``run_id`` bind the request to a specific attempt so a stray
    request can never satisfy a different obligation.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["broker-request-v1"] = "broker-request-v1"
    job_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")]
    run_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")]
    idempotency_key: Annotated[str, Field(pattern=IDEMPOTENCY_KEY_RE)]
    operations: tuple[
        AnalyzeOp | AssembleOp | CompileOp | ApplyOp | TestOp | VerifyOp, ...
    ] = Field(min_length=1, max_length=32)
    limits: ResourceLimits = ResourceLimits()
    # Artifact ids the request may reference. The host resolves each against the
    # artifact store before building the request; anything not listed here is
    # rejected by the broker.
    allowed_artifact_ids: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def _references_stay_inside_allowed_set(self) -> "TaskRequest":
        allowed = set(self.allowed_artifact_ids)
        for op in self.operations:
            refs = _artifact_refs(op)
            missing = refs - allowed
            if missing:
                raise ValueError(
                    f"operation references unregistered artifact ids: {sorted(missing)}"
                )
        return self

    def request_hash(self) -> str:
        """Stable identity of the request, used by the broker for replay checks."""
        canon = self.model_dump_json()
        return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _artifact_refs(op) -> set[str]:
    """Collect every artifact id an operation references."""
    ids: set[str] = set()
    if isinstance(op, AnalyzeOp):
        ids.add(op.binary.artifact_id)
    elif isinstance(op, AssembleOp):
        ids.add(op.base_binary.artifact_id)
        ids.add(op.out_artifact_id)
    elif isinstance(op, CompileOp):
        ids.add(op.source_artifact_id)
        ids.add(op.out_artifact_id)
    elif isinstance(op, ApplyOp):
        ids.add(op.base_binary.artifact_id)
        ids.add(op.candidate_artifact_id)
        ids.add(op.out_artifact_id)
    elif isinstance(op, TestOp):
        ids.add(op.candidate.artifact_id)
        ids.add(op.manifest_artifact_id)
    elif isinstance(op, VerifyOp):
        ids.add(op.candidate.artifact_id)
        ids.add(op.evidence_artifact_id)
    return ids


def build_task_request(
    *,
    job_id: str,
    run_id: str,
    idempotency_key: str,
    operations: list[dict],
    limits: ResourceLimits | None = None,
    allowed_artifact_ids: frozenset[str] | None = None,
) -> TaskRequest:
    """Validate and build a task request.

    Raises ``ValueError`` for any invalid operation or a reference to an
    artifact id outside ``allowed_artifact_ids``. The caller is responsible for
    resolving ``allowed_artifact_ids`` against the artifact store and for
    checking that every referenced ``sha256`` matches the recorded identity —
    this builder only enforces membership and structure.
    """
    parsed = [validate_operation(op) for op in operations]
    return TaskRequest(
        job_id=job_id,
        run_id=run_id,
        idempotency_key=idempotency_key,
        operations=tuple(parsed),
        limits=limits if limits is not None else ResourceLimits(),
        allowed_artifact_ids=(
            allowed_artifact_ids if allowed_artifact_ids is not None else frozenset()
        ),
    )


__all__ = [
    "ResourceLimits",
    "TaskRequest",
    "build_task_request",
    "validate_operation",
]
