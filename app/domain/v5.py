"""Typed formal-V5 clean-snapshot replay evidence.

The 2026-11-19 V5 specification is stricter than the earlier build-twice
envelope: for each route, the VM must be restored from an approved clean
snapshot, the frozen final ELF and the approved test manifest hashes must be
verified, the ELF must be run through the existing broker, and the snapshot
restore receipt, per-case expected/observed results, environment, and an
independent review must be recorded.

This module is the single schema for that record. A file that merely says
``passed`` is not evidence: the restore receipt, identity pins, per-case
comparison, isolation attestation and independent review are all required, and a
missing or inconsistent section is rejected instead of defaulted.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

HEX64 = r"^[a-f0-9]{64}$"
REASON_PREFIXES = ("host_verified:", "guest_observed:", "missing:", "invalid:", "check_failed:", "inconclusive:")


class V5EvidenceError(ValueError):
    """The formal V5 record is incomplete or inconsistent."""


class RestoreReceipt(BaseModel):
    model_config = ConfigDict(extra="allow")

    snapshot_name: str = Field(min_length=1)
    snapshot_uid: int = Field(ge=1)
    snapshot_file_sha256: str = Field(pattern=HEX64)
    vmx_path: str = Field(min_length=1)
    revert_command: str = Field(min_length=1)
    revert_exit_code: int
    revert_stdout: str = ""
    revert_stderr: str = ""
    restore_started_at: str = Field(min_length=1)
    restore_finished_at: str = Field(min_length=1)
    power_state_before: Literal["poweredOn", "poweredOff", "suspended"]
    power_state_after_revert: Literal["poweredOff"]
    booted_at: str = Field(min_length=1)
    boot_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _restore_confirmed(self) -> "RestoreReceipt":
        if self.revert_exit_code != 0:
            raise ValueError("snapshot revert did not exit 0")
        if self.restore_finished_at < self.restore_started_at:
            raise ValueError("restore finish precedes start")
        if self.booted_at < self.restore_finished_at:
            raise ValueError("guest boot precedes the revert")
        return self


class CaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    expected_return_code: int
    expected_stdout_sha256: str = Field(pattern=HEX64)
    expected_stderr_sha256: str = Field(pattern=HEX64)
    observed_return_code: int
    observed_stdout_sha256: str = Field(pattern=HEX64)
    observed_stderr_sha256: str = Field(pattern=HEX64)
    ok: bool

    @model_validator(mode="after")
    def _comparison_honest(self) -> "CaseResult":
        matches = (
            self.expected_return_code == self.observed_return_code
            and self.expected_stdout_sha256 == self.observed_stdout_sha256
            and self.expected_stderr_sha256 == self.observed_stderr_sha256
        )
        if self.ok != matches:
            raise ValueError("case ok flag disagrees with the observed comparison")
        return self


class Isolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_uid: int = Field(ge=0)
    uid: int = Field(ge=0)
    cap_eff: str
    no_new_privs: str
    seccomp: str
    netns: str = Field(min_length=1)
    jobwrap_attested: bool

    @model_validator(mode="after")
    def _isolated(self) -> "Isolation":
        if self.uid != self.expected_uid:
            raise ValueError("replay did not run as the unprivileged executor user")
        if self.cap_eff not in ("0", "0000000000000000"):
            raise ValueError("effective capabilities are not empty")
        if self.no_new_privs != "1":
            raise ValueError("NoNewPrivs is not 1")
        if self.jobwrap_attested is not True:
            raise ValueError("jobwrap attestation is missing")
        return self


class ReplayEnvelope(BaseModel):
    """The cross-run build replay: deterministic bytes, not the behaviour replay."""

    model_config = ConfigDict(extra="allow")

    method: str = Field(min_length=1)
    runs: int = Field(ge=2)
    sha256: list[str] = Field(min_length=2)
    byte_identical: bool
    matches_candidate: bool
    patch_tool_sha256: str = Field(pattern=HEX64)
    replayed_by: str = Field(min_length=1)
    independent_replay: bool


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewed_by: str = Field(min_length=1)
    independent: bool
    result: Literal["pass", "fail"]
    reviewed_at: str = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    def _independent(self) -> "Review":
        if self.independent is not True:
            raise ValueError("review is not independent")
        return self


class V5Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    gate: Literal["V5"] = "V5"
    kind: Literal["reproducibility"] = "reproducibility"
    scope: Literal["replay"] = "replay"
    state: Literal["passed"] = "passed"
    candidate_sha256: str = Field(pattern=HEX64)
    original_sha256: str = Field(pattern=HEX64)
    test_manifest_sha256: str = Field(pattern=HEX64)
    contract_canonical_sha256: str = Field(pattern=HEX64)
    environment: dict[str, str] = Field(min_length=3)
    restore_receipt: RestoreReceipt
    behavior: list[CaseResult] = Field(min_length=1)
    isolation: Isolation
    replay: ReplayEnvelope
    review: Review
    not_claimed: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _passed(self) -> "V5Evidence":
        if not all(case.ok for case in self.behavior):
            raise ValueError("a behaviour case did not meet its approved expectation")
        if self.review.result != "pass":
            raise ValueError("independent review did not pass")
        if any(value != self.candidate_sha256 for value in self.replay.sha256):
            raise ValueError("replay output does not equal the frozen candidate")
        if not self.replay.byte_identical or not self.replay.matches_candidate:
            raise ValueError("replay is not byte-identical to the frozen candidate")
        if not self.replay.independent_replay:
            raise ValueError("replay is not labelled independent")
        if not any("binary-level" in item.lower() for item in self.not_claimed):
            raise ValueError("not_claimed must exclude a binary-level claim")
        if not any("single" in item.lower() or "one approved" in item.lower() for item in self.not_claimed):
            raise ValueError("not_claimed must name the single-snapshot scope")
        return self


def manifest_sha256(files: dict[str, str]) -> str:
    """Hash an approved test manifest set: sorted name/sha256 entries."""

    payload = [{"name": name, "sha256": files[name]} for name in sorted(files)]
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_files(tests_dir: str | "PathLike") -> dict[str, str]:
    """Return ``{name: sha256}`` for valid.json and (when present) invalid.json."""

    from pathlib import Path

    root = Path(tests_dir)
    files: dict[str, str] = {}
    valid = root / "valid.json"
    if not valid.is_file():
        raise V5EvidenceError(f"approved test manifest is missing: {valid}")
    files["valid.json"] = hashlib.sha256(valid.read_bytes()).hexdigest()
    invalid = root / "invalid.json"
    if invalid.is_file():
        files["invalid.json"] = hashlib.sha256(invalid.read_bytes()).hexdigest()
    return files


def validate_v5_evidence(
    data: object,
    *,
    candidate_sha256: str | None = None,
    original_sha256: str | None = None,
    test_manifest_sha256: str | None = None,
    require_restore: bool = True,
    require_independent_review: bool = True,
    require_independent_replay: bool = True,
) -> V5Evidence:
    """Validate one formal V5 record; every failure is NOT VERIFIED."""

    try:
        evidence = V5Evidence.model_validate(data)
    except Exception as exc:  # pydantic.ValidationError and nested TypeErrors
        raise V5EvidenceError(str(exc)) from exc
    if candidate_sha256 is not None and evidence.candidate_sha256 != candidate_sha256:
        raise V5EvidenceError(
            f"candidate hash {evidence.candidate_sha256} != {candidate_sha256}"
        )
    if original_sha256 is not None and evidence.original_sha256 != original_sha256:
        raise V5EvidenceError(
            f"original hash {evidence.original_sha256} != {original_sha256}"
        )
    if test_manifest_sha256 is not None and evidence.test_manifest_sha256 != test_manifest_sha256:
        raise V5EvidenceError(
            f"test manifest hash {evidence.test_manifest_sha256} != {test_manifest_sha256}"
        )
    if require_restore and evidence.restore_receipt.revert_exit_code != 0:
        raise V5EvidenceError("snapshot restore is not confirmed")
    if require_independent_review and evidence.review.result != "pass":
        raise V5EvidenceError("independent review did not pass")
    if require_independent_replay and not evidence.replay.independent_replay:
        raise V5EvidenceError("independent replay is missing")
    return evidence


__all__ = [
    "CaseResult",
    "Isolation",
    "ReplayEnvelope",
    "RestoreReceipt",
    "Review",
    "V5Evidence",
    "V5EvidenceError",
    "manifest_files",
    "manifest_sha256",
    "validate_v5_evidence",
]
