"""Conformance matrix for the fixed-argv guest executor (VMer task-15).

This module defines *what* the executor must demonstrate and *how* the host
judges the evidence. It never executes anything: the matrix is data, the
verdict is computed from an evidence file the guest runner produced.

Why a matrix and not a checklist in prose: Nick's audit found the acceptance
layer willing to accept a "passing" claim without the artefact. Here the
verdict is derived from per-case records with exact exit codes and exact
isolation attestations; a case that did not run is ``not_run``, never
``pass``, and a matrix with any gap cannot yield ``pass``.

Authorised by: Lead task table item task-15 (conformance window, VMer);
AGENTS.md §3 (host never executes; the guest runs a fixed operation list);
code_patterns.md §Architecture (fixed operation list, typed manifests).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---- vocabulary ----------------------------------------------------------

CaseKind = Literal["positive", "negative"]
CaseResult = Literal["pass", "fail", "not_run", "inconclusive"]
VerdictState = Literal["pass", "fail", "inconclusive", "not_run"]


class Attestation(BaseModel):
    """Isolation facts the wrapper must emit for a positive case.

    Every field is required. A positive case without a complete attestation is
    ``inconclusive`` — running inside the wrong identity is not a pass.
    """

    model_config = ConfigDict(extra="forbid")

    uid: int
    gid: int
    cap_eff: str  # hex string; "0" or "0000000000000000" both mean no caps
    no_new_privs: int
    netns: str
    default_route: str  # empty string means egress blocked
    rlimit_cpu: int | None = None


class ConformanceCase(BaseModel):
    """One fixed-argv case in the matrix."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")
    kind: CaseKind
    # The exact argv the wrapper is invoked with, program name excluded. It is
    # a tuple of fixed tokens: no shell string, no caller-supplied command.
    argv: tuple[str, ...]
    expected_rc: int
    # For negative cases: a substring that must appear in stderr, so a generic
    # crash cannot be mistaken for the intended refusal.
    expected_stderr_contains: str | None = None
    # For positive cases: the isolation the run must attest.
    expect_isolation: bool = False
    # Optional: a case that is spec-only (no binary yet) is recorded as such.
    requires_mode: str | None = None
    # Run this case as an unprivileged uid instead of root. Needed for the
    # "refuses non-root" case, which cannot be observed from a root runner.
    run_as_uid: int | None = None
    # The case needs a prepared job: a candidate at
    # <work-dir>/route_a/candidate.elf plus a config line whose hash matches it.
    # Without one the runner records a skip, and the host reads it as
    # inconclusive rather than pretending the executor failed.
    requires_job: bool = False


CONFORMANCE_MATRIX: tuple[ConformanceCase, ...] = (
    # --- positive: the executor runs and isolates -------------------------
    ConformanceCase(
        id="pos-gate5-routea-probe",
        kind="positive",
        argv=("probe", "m4-gate5", "--", "<repo>", "<work>"),
        expected_rc=0,
        expect_isolation=True,
    ),
    ConformanceCase(
        id="pos-gate5-routeb-probe",
        kind="positive",
        argv=("probe", "m4-gate5b", "--", "<repo>", "<work>"),
        expected_rc=0,
        expect_isolation=True,
    ),
    ConformanceCase(
        id="pos-routea-exec",
        kind="positive",
        argv=("routea", "demo"),
        expected_rc=0,
        expect_isolation=True,
        requires_mode="routea",
        requires_job=True,
    ),
    # --- negative: the executor refuses, with the documented code ---------
    ConformanceCase(
        id="neg-non-root",
        kind="negative",
        argv=("routea", "demo"),
        expected_rc=1,
        expected_stderr_contains="must run as root",
        requires_mode="routea",
        # Observed by running the executor as an unprivileged uid; a root
        # runner cannot demonstrate this refusal.
        run_as_uid=1000,
    ),
    ConformanceCase(
        id="neg-wrong-argc",
        kind="negative",
        argv=("probe", "m4-gate5"),
        expected_rc=2,
        expected_stderr_contains="usage:",
    ),
    ConformanceCase(
        id="neg-path-traversal-job-id",
        kind="negative",
        argv=("routea", "../etc"),
        expected_rc=2,
        # The wrapper reports the offending id rather than a bare usage line;
        # what matters is that it refuses before any privilege or config check.
        expected_stderr_contains="bad job id",
        requires_mode="routea",
    ),
    ConformanceCase(
        id="neg-unknown-job",
        kind="negative",
        argv=("routea", "missing"),
        expected_rc=3,
        expected_stderr_contains="unknown job",
        requires_mode="routea",
    ),
    ConformanceCase(
        id="neg-candidate-hash-mismatch",
        kind="negative",
        # A job id whose config line carries a hash that deliberately does not
        # match the candidate on disk. Using the good job id here would pass.
        argv=("routea", "demo-badhash"),
        expected_rc=4,
        expected_stderr_contains="hash mismatch",
        requires_mode="routea",
    ),
    ConformanceCase(
        id="neg-unknown-mode",
        kind="negative",
        argv=("probe", "not-a-mode", "--", "/repo", "/work"),
        expected_rc=2,
        expected_stderr_contains="usage:",
    ),
    ConformanceCase(
        id="neg-relative-path",
        kind="negative",
        argv=("probe", "m4-gate5", "--", "repo", "work"),
        expected_rc=1,
        expected_stderr_contains="absolute",
    ),
)


class CaseRecord(BaseModel):
    """What the guest runner writes for one executed case."""

    model_config = ConfigDict(extra="forbid")

    id: str
    rc: int | None = None
    stderr: str = ""
    attestation: Attestation | None = None
    # Set by the runner when the case could not be executed at all.
    skipped_reason: str | None = None
    # Recorded for traceability; not used by the verdict rules.
    argv: tuple[str, ...] = ()
    stdout: str = ""


class WindowMeta(BaseModel):
    """Provenance of the window the cases ran in."""

    model_config = ConfigDict(extra="forbid")

    snapshot_uid: int
    snapshot_name: str
    started_at: str
    finished_at: str
    executor_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    original_jobwrap_sha256: str | None = None
    available_modes: tuple[str, ...] = ()
    # Recorded for traceability, not judged.
    kernel: str | None = None
    python: str | None = None


class Evidence(BaseModel):
    """The whole conformance evidence file."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    window: WindowMeta
    cases: tuple[CaseRecord, ...]


class CaseVerdict(BaseModel):
    id: str
    kind: CaseKind
    result: CaseResult
    detail: str


class ConformanceVerdict(BaseModel):
    """The host's reading of the evidence. Never computed from a claim."""

    state: VerdictState
    cases: tuple[CaseVerdict, ...]
    missing: tuple[str, ...] = ()
    reason: str = ""


def _attestation_ok(att: Attestation) -> tuple[bool, str]:
    if att.uid != 1003:
        return False, f"uid={att.uid}, expected 1003"
    if att.gid != 1003:
        return False, f"gid={att.gid}, expected 1003"
    if att.cap_eff.strip("0") != "":
        return False, f"cap_eff={att.cap_eff!r}, expected no capabilities"
    if att.no_new_privs != 1:
        return False, f"no_new_privs={att.no_new_privs}, expected 1"
    if att.default_route.strip() != "":
        return False, f"default_route={att.default_route!r}, expected blocked egress"
    if not att.netns:
        return False, "netns missing"
    return True, ""


def evaluate(
    payload: dict,
    *,
    matrix: tuple[ConformanceCase, ...] = CONFORMANCE_MATRIX,
) -> ConformanceVerdict:
    """Judge one evidence file against the matrix.

    Fail-closed rules, in this order:

    1. A required case with no record is ``not_run``; the overall state becomes
       ``not_run`` (never ``pass``).
    2. A case whose rc/stderr/attestation does not match the matrix entry is
       ``fail``; the overall state becomes ``fail``.
    3. A case explicitly skipped for a missing mode is ``inconclusive``; the
       overall state becomes ``inconclusive`` unless a ``fail`` already exists.
    4. Only when every required case is ``pass`` is the overall state ``pass``.
    """
    try:
        evidence = Evidence.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 - surface as a typed verdict
        return ConformanceVerdict(
            state="fail",
            cases=(),
            reason=f"evidence failed schema validation: {type(exc).__name__}",
        )

    records = {r.id: r for r in evidence.cases}
    available = set(evidence.window.available_modes)

    verdicts: list[CaseVerdict] = []
    missing: list[str] = []
    saw_fail = False
    saw_inconclusive = False

    for case in matrix:
        record = records.get(case.id)
        if record is None:
            missing.append(case.id)
            verdicts.append(
                CaseVerdict(id=case.id, kind=case.kind, result="not_run",
                            detail="no record in evidence")
            )
            continue

        # A mode that the deployed binary does not ship cannot be conformed.
        if case.requires_mode and case.requires_mode not in available:
            saw_inconclusive = True
            verdicts.append(
                CaseVerdict(id=case.id, kind=case.kind, result="inconclusive",
                            detail=f"mode {case.requires_mode!r} not present in executor")
            )
            continue

        if record.skipped_reason:
            saw_inconclusive = True
            verdicts.append(
                CaseVerdict(id=case.id, kind=case.kind, result="inconclusive",
                            detail=f"skipped: {record.skipped_reason}")
            )
            continue

        if record.rc is None:
            saw_fail = True
            verdicts.append(
                CaseVerdict(id=case.id, kind=case.kind, result="fail",
                            detail="no exit code recorded")
            )
            continue

        if record.rc != case.expected_rc:
            saw_fail = True
            verdicts.append(
                CaseVerdict(id=case.id, kind=case.kind, result="fail",
                            detail=f"rc={record.rc}, expected {case.expected_rc}")
            )
            continue

        if case.expected_stderr_contains and case.expected_stderr_contains not in record.stderr:
            saw_fail = True
            verdicts.append(
                CaseVerdict(id=case.id, kind=case.kind, result="fail",
                            detail="stderr did not contain the documented refusal")
            )
            continue

        if case.expect_isolation:
            if record.attestation is None:
                saw_inconclusive = True
                verdicts.append(
                    CaseVerdict(id=case.id, kind=case.kind, result="inconclusive",
                                detail="no isolation attestation recorded")
                )
                continue
            ok, why = _attestation_ok(record.attestation)
            if not ok:
                saw_fail = True
                verdicts.append(
                    CaseVerdict(id=case.id, kind=case.kind, result="fail",
                                detail=f"isolation: {why}")
                )
                continue

        verdicts.append(
            CaseVerdict(id=case.id, kind=case.kind, result="pass", detail="")
        )

    if saw_fail:
        state: VerdictState = "fail"
        reason = "at least one case contradicted the matrix"
    elif missing:
        state = "not_run"
        reason = f"{len(missing)} required case(s) have no record"
    elif saw_inconclusive:
        state = "inconclusive"
        reason = "a case could not be conformed (missing mode or skipped)"
    else:
        state = "pass"
        reason = "every required case matched the matrix"

    return ConformanceVerdict(
        state=state, cases=tuple(verdicts), missing=tuple(missing), reason=reason
    )


def case_ids() -> tuple[str, ...]:
    """The canonical case order, for a runner that wants to iterate the matrix."""
    return tuple(c.id for c in CONFORMANCE_MATRIX)


def matrix_as_json() -> list[dict]:
    """The matrix as plain JSON, so the guest runner needs no third-party deps.

    The guest is a dumb executor on purpose: it receives this list, runs each
    argv, and writes raw records. All judging (pydantic, fail-closed rules)
    stays on the host, which is the only side allowed to decide a verdict.
    """
    return [c.model_dump() for c in CONFORMANCE_MATRIX]


if __name__ == "__main__":  # python -m workers.broker.conformance --dump-matrix out.json
    import json as _json
    import sys as _sys

    if len(_sys.argv) == 3 and _sys.argv[1] == "--dump-matrix":
        with open(_sys.argv[2], "w", encoding="utf-8") as _fh:
            _json.dump(matrix_as_json(), _fh, indent=2)
            _fh.write("\n")
        print(f"wrote {len(CONFORMANCE_MATRIX)} cases to {_sys.argv[2]}")
    else:
        print("usage: python -m workers.broker.conformance --dump-matrix <out.json>",
              file=_sys.stderr)
        raise SystemExit(2)


__all__ = [
    "CONFORMANCE_MATRIX",
    "Attestation",
    "CaseRecord",
    "CaseVerdict",
    "ConformanceCase",
    "ConformanceVerdict",
    "Evidence",
    "WindowMeta",
    "case_ids",
    "evaluate",
    "matrix_as_json",
]
