#!/usr/bin/env python3
"""Staged release/nightly gate for the binary-repair product.

Three explicit cost layers (the gate never fakes a check and never claims a run
that did not happen):

``--pr``
    Fast pull-request layer: the static capability audit gate
    (``scripts/verify_coverage_gate.py --static-only``), the measured
    claims/measurement diff, and a targeted pytest subset.  ``dynamic_unverified``
    gaps are expected in static mode and are reported, not failed.

``--release``
    Release layer: everything in ``--pr`` plus the local coverage gate
    (``--local``: bounded probes, real-guest acceptance capture
    ``artifacts/coverage-closure-2026-11-14/acceptance.json``, meta-audit and
    acceptance invariants), the release acceptance contract (capacity + heap +
    target-scoped cases), the provider-matrix artifact with target-strict
    fields, and the full pytest suite.

``--nightly``
    Release checks plus a fresh real-Lima acceptance capture when a guest runner
    is available.  If no runner is available the capture check degrades to an
    explicit ``unavailable`` reason (never faked) and is not a violation; every
    other required release check still applies.

Exit codes: ``0`` all required checks passed, ``1`` at least one violation,
``2`` usage error.

Output: a structured summary (``--json`` for CI) and exit non-zero on any
violation.  Missing mid-flight teammate modules/artifacts are reported as
explicit ``unavailable``/``failed`` reasons, never silently skipped.

Release freeze enforcement (phase 4): ``--release`` requires ``--release-sha``
(frozen commit) and ``--release``/``--nightly`` require a **clean worktree**
(``git status --porcelain`` empty).  The read-only tree identity (HEAD SHA,
branch and porcelain status) is recorded as ``frozen_sha`` / ``branch`` /
``clean_tree`` in the JSON summary and as the ``release-tree-identity`` check;
an unfrozen tree fails fast with "commit or freeze before release".  Any commit
after a green run invalidates it: re-freeze (new SHA) and re-run the gate.

Environment note: no network is used.  ``--release``/``--nightly`` may execute
the real Lima guest (through the product's own PoC runner) and the full pytest
suite; ``--pr`` is deterministic and host-portable.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]

CHECK_PASSED = "passed"
CHECK_FAILED = "failed"
CHECK_UNAVAILABLE = "unavailable"
CHECK_SKIPPED = "skipped"

DEFAULT_ACCEPTANCE = "artifacts/coverage-closure-2026-11-14/acceptance.json"
DEFAULT_CAPTURE = "artifacts/coverage-closure-2026-11-14/capture_acceptance.py"
DEFAULT_PROVIDER_MATRIX = "artifacts/provider-matrix-2026-11-14"
DEFAULT_PROVIDER_COVERAGE = "artifacts/provider-coverage-2026-11-14"
DEFAULT_EVIDENCE = "artifacts/release-gate-2026-11-14/gate.json"
DEFAULT_CLAIMS = "docs/status/claims.json"
DEFAULT_NON_GOALS = "docs/acceptance/non-goals-2026-11-14.md"
COVERAGE_GATE = "scripts/verify_coverage_gate.py"
META_AUDIT = "scripts/meta_audit.py"

TIMEOUT_STATIC = 300.0
TIMEOUT_TARGETED = 900.0
TIMEOUT_LOCAL = 1500.0
TIMEOUT_META_AUDIT = 300.0
TIMEOUT_FULL_PYTEST = 2700.0
TIMEOUT_CAPTURE = 2400.0
TIMEOUT_GIT = 30.0

#: Targeted pytest subset for the fast PR layer.  Missing files are reported as
#: ``not_present`` (teammate suites land incrementally) but at least one must
#: exist and pass.  The full release layer runs the entire suite.
TARGETED_TESTS: tuple[str, ...] = (
    "tests/test_release_gate.py",
    "tests/test_coverage_gate.py",
    "tests/test_capability_audit.py",
    "tests/test_acceptance_invariants.py",
    "tests/test_meta_audit.py",
    "tests/test_ci_evidence.py",
    "tests/test_repair_matrix.py",
    "tests/test_runtime_capabilities.py",
)

REQUIRED_CLAIM_NON_GOAL_KEYS = ("id", "category", "enforcement", "claim")
REQUIRED_CLAIM_TOP_LEVEL = ("scope", "product_paths", "non_goals")

PROVIDER_MATRIX_FILES = ("README.md", "summary.json", "SHA256SUMS")
PROVIDER_MATRIX_CASES = 12
PROVIDER_PROVIDER_STATUSES = frozenset(
    # T4 writes "ok"/"reference"/"unavailable"/"not_requested"; "error" is kept
    # for forward compatibility with an explicit provider-error run.
    {"ok", "reference", "unavailable", "error", "not_requested"}
)
#: Statuses that must explain why the AI phase could not run.
PROVIDER_UNAVAILABLE_STATUSES = frozenset({"unavailable", "error"})
#: Statuses that may legitimately record a verified reference/AI attempt.
PROVIDER_TRUSTED_STATUSES = frozenset({"ok", "reference"})
PROVIDER_CASE_REQUIRED_FIELDS = (
    "provider",
    "model",
    "seed",
    "cost",
    "elapsed_ms",
    "target_policy",
    "target_scope",
    "target_scope_check",
    "target_in_scope",
    "baseline_target_strict",
    "reference_fix",
    "ai_target",
)
PROVIDER_CASE_ALIASES = {
    "baseline_whole_image": ("baseline_whole_image", "baseline"),
    "ai_target": ("ai_target", "ai_result"),
}
PROVIDER_TARGET_SCOPE_CHECK_VALUES = frozenset({"passed", "failed", "not_run"})
PROVIDER_RATE_ALIASES = {
    "target_strict_pass_rate": ("target_strict_pass_rate", "target_strict_rate"),
    "target_in_scope_rate": ("target_in_scope_rate", "in_scope_rate"),
}

# ---------------------------------------------------------------------------
# Paths and subprocess plumbing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Paths:
    """Filesystem layout of the tree under gate (root override is test/debug)."""

    root: Path = ROOT

    @property
    def coverage_gate_script(self) -> Path:
        return self.root / COVERAGE_GATE

    @property
    def meta_audit_script(self) -> Path:
        return self.root / META_AUDIT

    @property
    def acceptance(self) -> Path:
        return self.root / DEFAULT_ACCEPTANCE

    @property
    def capture_script(self) -> Path:
        return self.root / DEFAULT_CAPTURE

    @property
    def provider_matrix_dir(self) -> Path:
        return self.root / DEFAULT_PROVIDER_MATRIX

    @property
    def provider_coverage_dir(self) -> Path:
        return self.root / DEFAULT_PROVIDER_COVERAGE

    @property
    def claims(self) -> Path:
        return self.root / DEFAULT_CLAIMS

    @property
    def non_goals_doc(self) -> Path:
        return self.root / DEFAULT_NON_GOALS


@dataclass
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


Runner = Callable[[Sequence[str], Path, float], RunResult]


def run_command(argv: Sequence[str], cwd: Path, timeout: float) -> RunResult:
    """Run a subprocess with a hard timeout; never raises for gate inputs."""
    try:
        completed = subprocess.run(
            list(argv),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            returncode=124,
            stdout=_text(exc.stdout),
            stderr=f"timeout after {timeout:.0f}s",
            timed_out=True,
        )
    except OSError as exc:
        return RunResult(returncode=127, stderr=f"{type(exc).__name__}: {exc}")
    return RunResult(
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


# ---------------------------------------------------------------------------
# Check model and JSON helpers
# ---------------------------------------------------------------------------


@dataclass
class Check:
    check_id: str
    title: str
    status: str = CHECK_SKIPPED
    required: bool = True
    detail: str = ""
    violations: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def fail(self, violation: str, detail: str | None = None) -> "Check":
        self.status = CHECK_FAILED
        self.violations.append(violation)
        if detail is not None:
            self.detail = detail
        return self

    def unavailable(self, reason: str) -> "Check":
        self.status = CHECK_UNAVAILABLE
        self.detail = reason
        return self

    def skipped(self, reason: str) -> "Check":
        self.status = CHECK_SKIPPED
        self.detail = reason
        return self

    def passed(self, detail: str) -> "Check":
        self.status = CHECK_PASSED
        self.detail = detail
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "title": self.title,
            "status": self.status,
            "required": bool(self.required),
            "detail": self.detail,
            "violations": list(self.violations),
            "elapsed_ms": int(self.elapsed_ms),
        }


@dataclass
class GateSummary:
    mode: str
    checks: list[Check]
    violations: list[str]
    notes: list[str] = field(default_factory=list)
    elapsed_ms: int = 0
    #: --release-sha as supplied by the operator (frozen commit), if any.
    release_sha: str | None = None
    #: HEAD SHA measured by the gate's read-only ``git rev-parse HEAD``.
    frozen_sha: str | None = None
    #: Current branch, or "HEAD" when detached.
    branch: str | None = None
    #: True iff ``git status --porcelain`` was empty (None when git is absent).
    clean_tree: bool | None = None

    @property
    def ok(self) -> bool:
        return not self.violations

    def status_counts(self) -> dict[str, int]:
        counts = {CHECK_PASSED: 0, CHECK_FAILED: 0, CHECK_UNAVAILABLE: 0,
                  CHECK_SKIPPED: 0}
        for check in self.checks:
            counts[check.status] = counts.get(check.status, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "mode": self.mode,
            "ok": self.ok,
            "exit_code": 0 if self.ok else 1,
            "violations": list(self.violations),
            "notes": list(self.notes),
            "release_sha": self.release_sha,
            "frozen_sha": self.frozen_sha,
            "branch": self.branch,
            "clean_tree": self.clean_tree,
            "status_counts": self.status_counts(),
            "checks": [check.to_dict() for check in self.checks],
            "elapsed_ms": int(self.elapsed_ms),
        }


def _load_json(path: Path) -> tuple[Any | None, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{path}: {type(exc).__name__}: {exc}"


def _parse_json_output(text: str) -> tuple[Any | None, str]:
    """Parse a subprocess JSON payload, tolerating leading/trailing noise."""
    payload = _text(text).strip()
    if not payload:
        return None, "empty stdout (no JSON payload)"
    try:
        return json.loads(payload), ""
    except json.JSONDecodeError:
        start, end = payload.find("{"), payload.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(payload[start:end + 1]), ""
            except json.JSONDecodeError as exc:
                return None, f"invalid JSON payload: {exc}"
        return None, "no JSON object in stdout"


def _tail(text: str, limit: int = 600) -> str:
    payload = _text(text).strip()
    return payload if len(payload) <= limit else "…" + payload[-limit:]


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


# ---------------------------------------------------------------------------
# --pr layer: static coverage gate
# ---------------------------------------------------------------------------


def check_static_coverage_gate(paths: Paths, run: Runner = run_command) -> Check:
    check = Check(
        "static-coverage-gate",
        "Static capability-audit coverage gate (no probes)",
    )
    script = paths.coverage_gate_script
    if not script.is_file():
        return check.fail(f"static coverage gate script missing: {script}")
    started = time.monotonic()
    try:
        result = run(
            [sys.executable, str(script), "--static-only", "--json"],
            paths.root,
            TIMEOUT_STATIC,
        )
    finally:
        check.elapsed_ms = int((time.monotonic() - started) * 1000)
    if result.timed_out:
        return check.fail(f"static coverage gate timed out after {TIMEOUT_STATIC:.0f}s")
    payload, error = _parse_json_output(result.stdout)
    if error:
        return check.fail(
            f"static coverage gate produced no usable summary: {error}; "
            f"rc={result.returncode}; stderr={_tail(result.stderr)}"
        )
    violations = [f"static coverage gate violation: {item}"
                  for item in _as_list(payload.get("violations"))]
    if payload.get("ok") is False:
        violations.append("static coverage gate reported ok=false")
    if result.returncode != 0 and not violations:
        violations.append(
            f"static coverage gate exited non-zero (rc={result.returncode})"
        )
    dynamic = payload.get("dynamic_unverified_count")
    dynamic_ids = _as_list(payload.get("dynamic_unverified_gap_ids"))
    notes = []
    if isinstance(dynamic, int) and dynamic > 0:
        notes.append(f"dynamic_unverified={dynamic} (allowed in static/PR mode)")
    elif dynamic_ids:
        notes.append(
            f"dynamic_unverified={len(dynamic_ids)} (allowed in static/PR mode)"
        )
    check.detail = (
        f"open={_as_list(payload.get('open_gap_ids'))} "
        f"non_goals={len(_as_list(payload.get('non_goal_gap_ids')))} "
        f"dynamic_unverified={dynamic if dynamic is not None else '?'}"
    )
    if violations:
        check.violations.extend(violations)
        check.status = CHECK_FAILED
        return check
    if notes:
        check.detail += "; " + "; ".join(notes)
    return check.passed(check.detail)


# ---------------------------------------------------------------------------
# --pr layer: measured claims/measurement diff
# ---------------------------------------------------------------------------


def _claims_non_goal_ids(
    claims: Any,
) -> tuple[set[str], list[str]]:
    """Validate the structured claims non-goals and return their ids."""
    if not isinstance(claims, dict):
        return set(), ["claims.json is missing or not a JSON object"]
    entries = claims.get("non_goals")
    if not isinstance(entries, list) or not entries:
        return set(), ["claims.json has no non-empty structured 'non_goals' list"]
    ids: set[str] = set()
    violations: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            violations.append(f"claims.json non_goals[{index}] is not an object")
            continue
        missing = [
            key for key in REQUIRED_CLAIM_NON_GOAL_KEYS
            if not str(entry.get(key, "") or "").strip()
        ]
        if missing:
            violations.append(
                f"claims.json non_goals[{index}] missing fields: {missing}"
            )
        entry_id = str(entry.get("id", "") or "")
        if not entry_id:
            continue
        if entry_id in ids:
            violations.append(f"claims.json non_goals lists duplicate id {entry_id!r}")
        ids.add(entry_id)
    return ids, violations


def evaluate_claims_measurement(
    audit: Any,
    claims: Any,
    non_goals_doc: str,
) -> tuple[list[str], dict[str, Any]]:
    """Compare the measured audit against the declared claims (release layer).

    A clean diff means: the audit has zero open gaps, no detector errors, no
    unresolved matrix/claim mismatches, and every measured non-goal is mapped in
    ``claims.json`` or the non-goals document.  ``dynamic_unverified`` rows are
    expected in static mode (the local gate resolves them with probes) and are
    only counted here.
    """
    violations: list[str] = []
    if not isinstance(audit, dict) or not isinstance(audit.get("gaps"), list):
        return ["measured audit document has no 'gaps' list"], {}
    rows = [row for row in audit["gaps"] if isinstance(row, dict)]
    statuses = [str(row.get("status", "")) for row in rows]
    gap_ids = [str(row.get("gap_id", "")) for row in rows]
    open_ids = sorted(
        str(row.get("gap_id", "")) for row in rows
        if str(row.get("status", "")) == "open"
    )
    mitigated_ids = sorted(
        str(row.get("gap_id", "")) for row in rows
        if str(row.get("status", "")) == "mitigated"
    )
    dynamic_ids = sorted(
        str(row.get("gap_id", "")) for row in rows
        if str(row.get("status", "")) == "dynamic_unverified"
    )
    detector_errors = sorted(
        gap_id for gap_id in gap_ids if gap_id.startswith("GM-detector-error::")
    )
    mm_unresolved = sorted(
        str(row.get("gap_id", "")) for row in rows
        if str(row.get("category", "")) == "matrix_claim_mismatch"
        and str(row.get("status", "")) in {"open", "mitigated"}
    )
    non_goal_ids = sorted(
        str(row.get("gap_id", "")) for row in rows
        if str(row.get("status", "")) == "non_goal"
    )
    if open_ids:
        violations.append(
            f"measured open gaps present (release requires zero): {open_ids}"
        )
    # ``mitigated`` means the audit recorded an accepted residual with an
    # explicit rationale (for example a host-dependent runtime tier: a macOS
    # arm64 host cannot run x86_64 ELF natively, so a declared native_run tier is
    # measured as emulated_run with a capability-contract reason).  The audit
    # contract allows that status; the release gate accepts it only when the
    # rationale is recorded, and always prints the residual ids.  Matrix/claim
    # mismatches stay hard failures below, and an open gap is never tolerated.
    mitigated_rows = [
        row for row in rows if str(row.get("status", "")) == "mitigated"
    ]
    unjustified_mitigated = sorted(
        str(row.get("gap_id", "")) for row in mitigated_rows
        if not str(row.get("symptom", "") or "").strip()
        or not (
            str(row.get("next_step", "") or "").strip()
            or _as_list(row.get("evidence"))
        )
    )
    if unjustified_mitigated:
        violations.append(
            "measured mitigated gaps without a recorded rationale "
            f"(symptom/next_step/evidence): {unjustified_mitigated}"
        )
    if detector_errors:
        violations.append(f"audit detector errors present: {detector_errors}")
    if mm_unresolved:
        violations.append(
            "measured matrix/claim mismatches are not closed: "
            f"{mm_unresolved}"
        )

    claims_ids, claim_violations = _claims_non_goal_ids(claims)
    violations.extend(claim_violations)
    if isinstance(claims, dict):
        for key in REQUIRED_CLAIM_TOP_LEVEL:
            if key not in claims:
                violations.append(f"claims.json missing top-level key {key!r}")
    doc_text = str(non_goals_doc or "")
    unmapped = [
        gap_id for gap_id in non_goal_ids
        if gap_id not in claims_ids and gap_id not in doc_text
    ]
    if unmapped:
        violations.append(
            "measured non-goal id(s) are not mapped in claims.json or the "
            f"non-goals doc: {unmapped}"
        )
    # dynamic_unverified rows are resolved by the local probe run in release
    # mode; count their ids as measured so the declared list is not called stale.
    measured = set(non_goal_ids) | set(open_ids) | set(dynamic_ids)
    stale_claims = sorted(claims_ids - measured)
    if stale_claims:
        violations.append(
            "claims.json declares non-goals that are not measured as "
            f"non_goal/open/dynamic_unverified audit rows: {stale_claims}"
        )
    detail = {
        "gap_count": len(rows),
        "open_gap_ids": open_ids,
        "mitigated_gap_ids": mitigated_ids,
        "unjustified_mitigated_gap_ids": unjustified_mitigated,
        "mitigated_residual_gap_ids": sorted(set(mitigated_ids) - set(unjustified_mitigated)),
        "dynamic_unverified_gap_ids": dynamic_ids,
        "non_goal_gap_ids": non_goal_ids,
        "claims_non_goal_count": len(claims_ids),
        "mm_unresolved_gap_ids": mm_unresolved,
        "status_counts": {
            status: statuses.count(status)
            for status in sorted(set(statuses))
        },
    }
    return violations, detail


def check_claims_measurement(
    paths: Paths,
    *,
    build_audit: Callable[..., dict[str, Any]] | None = None,
) -> Check:
    check = Check(
        "claims-measurement-diff",
        "Measured audit vs declared claims/non-goals diff (static census)",
    )
    started = time.monotonic()
    if build_audit is None:
        try:
            sys.path.insert(0, str(paths.root))
            from app.services import coverage_audit  # noqa: PLC0415

            build_audit = coverage_audit.build_audit
        except Exception as exc:  # noqa: BLE001 - reported as a gate violation
            check.elapsed_ms = int((time.monotonic() - started) * 1000)
            return check.fail(
                f"coverage audit is unavailable, claims/measurement diff cannot "
                f"be measured: {type(exc).__name__}: {exc}"
            )
    try:
        audit = build_audit(include_probes=False)
    except Exception as exc:  # noqa: BLE001
        check.elapsed_ms = int((time.monotonic() - started) * 1000)
        return check.fail(
            f"static audit build failed: {type(exc).__name__}: {exc}"
        )
    claims, error = _load_json(paths.claims)
    claims_violations: list[str] = []
    if error:
        claims_violations.append(f"claims.json unavailable/invalid: {error}")
        claims = None
    try:
        doc_text = paths.non_goals_doc.read_text(encoding="utf-8")
    except OSError as exc:
        doc_text = ""
        claims_violations.append(
            f"non-goals doc unavailable: {type(exc).__name__}: {exc}"
        )
    violations, detail = evaluate_claims_measurement(audit, claims, doc_text)
    violations = claims_violations + violations
    check.elapsed_ms = int((time.monotonic() - started) * 1000)
    check.detail = (
        f"gaps={detail.get('gap_count')} open={detail.get('open_gap_ids')} "
        f"mitigated_residual={detail.get('mitigated_residual_gap_ids')} "
        f"non_goals={len(detail.get('non_goal_gap_ids') or [])} "
        f"dynamic_unverified={len(detail.get('dynamic_unverified_gap_ids') or [])} "
        f"claims_non_goals={detail.get('claims_non_goal_count')} "
        f"mm_unresolved={detail.get('mm_unresolved_gap_ids')}"
    )
    if violations:
        check.violations.extend(violations)
        check.status = CHECK_FAILED
        return check
    return check.passed(check.detail)


# ---------------------------------------------------------------------------
# --pr layer: targeted pytest subset
# ---------------------------------------------------------------------------


def check_targeted_tests(paths: Paths, run: Runner = run_command) -> Check:
    check = Check(
        "targeted-pytest",
        "Targeted pytest subset for gate/audit/release contracts",
    )
    existing = [rel for rel in TARGETED_TESTS if (paths.root / rel).is_file()]
    missing = [rel for rel in TARGETED_TESTS if rel not in existing]
    if not existing:
        return check.fail(
            "no targeted test files exist under the tree (expected at least one)"
        )
    started = time.monotonic()
    result = run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:xdist", *existing],
        paths.root,
        TIMEOUT_TARGETED,
    )
    check.elapsed_ms = int((time.monotonic() - started) * 1000)
    message = (
        f"ran {len(existing)} file(s)={existing}"
        + (f"; not_present={missing}" if missing else "")
    )
    if result.timed_out:
        return check.fail(
            f"targeted pytest timed out after {TIMEOUT_TARGETED:.0f}s; {message}"
        )
    if result.returncode != 0:
        return check.fail(
            f"targeted pytest failed (rc={result.returncode}); {message}; "
            f"stdout={_tail(result.stdout)}; stderr={_tail(result.stderr)}",
            detail=message,
        )
    return check.passed(message)


# ---------------------------------------------------------------------------
# Release layer: acceptance contract (capacity + heap + target-scoped)
# ---------------------------------------------------------------------------


def _case_verified(case: dict[str, Any]) -> bool:
    return case.get("verified") is True


def _case_downloadable(case: dict[str, Any]) -> bool:
    return case.get("download_allowed") is True


def _accepted_cases(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Flatten the capture document into (key, case) pairs."""
    pairs: list[tuple[str, dict[str, Any]]] = []
    for key, value in payload.items():
        if key in {"passed", "failures", "generated_by", "schema_version",
                   "limitations", "notes", "packets"}:
            continue
        if isinstance(value, dict):
            pairs.append((key, value))
    return pairs


def validate_acceptance(payload: Any) -> tuple[list[str], dict[str, Any]]:
    """Validate the committed real-guest acceptance capture.

    Roles are checked instead of one generation of case names so the Lead can
    extend the capture (for example with ``allow_whole_image`` fields) without
    weakening the release contract.
    """
    violations: list[str] = []
    if not isinstance(payload, dict):
        return ["acceptance capture is not a JSON object"], {}
    if payload.get("passed") is not True:
        violations.append(
            f"acceptance capture did not pass: passed={payload.get('passed')!r}"
        )
    failures = payload.get("failures")
    if isinstance(failures, list) and failures:
        violations.append(f"acceptance capture lists failures: {failures[:3]}")
    cases = _accepted_cases(payload)
    if not cases:
        return violations + ["acceptance capture has no per-case records"], {}

    review = [(key, case) for key, case in cases
              if key.startswith("marcx_review_api")
              or str(case.get("case", "")) == "marcx-review-api"]
    capacity = [(key, case) for key, case in cases
                if str(case.get("strategy", "")) == "capacity"
                and case.get("with_manifest") is True]
    capacity_control = [(key, case) for key, case in cases
                        if str(case.get("strategy", "")) == "capacity"
                        and case.get("with_manifest") is False]
    heap = [(key, case) for key, case in cases
            if str(case.get("strategy", "")) == "guard"
            and case.get("with_manifest") is True]
    heap_control = [(key, case) for key, case in cases
                    if str(case.get("strategy", "")) == "guard"
                    and case.get("with_manifest") is False]
    target_scoped = [(key, case) for key, case in cases
                     if "target_scope_check" in case
                     and case.get("target_scope_check") == "passed"]
    wrong_target = [(key, case) for key, case in cases
                    if case.get("target") and not _case_verified(case)]

    if not review:
        violations.append("acceptance capture has no marcx review-API success case")
    else:
        for key, case in review:
            decision = _as_dict(case.get("decision"))
            if decision.get("success") is not True:
                violations.append(
                    f"acceptance {key}: marcx review-API decision.success is not true"
                )
            if _as_list(case.get("checks_failed")):
                violations.append(
                    f"acceptance {key}: failed checks present "
                    f"{_as_list(case.get('checks_failed'))[:3]}"
                )
            if _as_list(case.get("checks_not_run")):
                violations.append(
                    f"acceptance {key}: not_run checks present "
                    f"{_as_list(case.get('checks_not_run'))[:3]}"
                )
            if case.get("runtime_tier") not in {"native_run", "emulated_run"}:
                violations.append(
                    f"acceptance {key}: runtime_tier={case.get('runtime_tier')!r} "
                    "is not native_run/emulated_run"
                )

    def _require_verified(
        role: str, pairs: list[tuple[str, dict[str, Any]]],
    ) -> None:
        if not pairs:
            violations.append(f"acceptance capture has no {role} case")
            return
        for key, case in pairs:
            if not _case_verified(case):
                violations.append(f"acceptance {key}: {role} is not verified")
            if case.get("disposition") not in {None, "verified_patch"}:
                violations.append(
                    f"acceptance {key}: disposition={case.get('disposition')!r} "
                    "is not verified_patch"
                )
            if not _case_downloadable(case):
                violations.append(
                    f"acceptance {key}: verified {role} must allow download"
                )
            if case.get("gate_outcome") not in {None, "success_within_scope"}:
                violations.append(
                    f"acceptance {key}: gate_outcome="
                    f"{case.get('gate_outcome')!r} is not success_within_scope"
                )
            sha = case.get("candidate_sha256")
            if not (isinstance(sha, str) and len(sha) == 64
                    and all(char in "0123456789abcdef" for char in sha)):
                violations.append(
                    f"acceptance {key}: {role} candidate_sha256 is not a "
                    "lower-case SHA-256 hex digest"
                )

    _require_verified("capacity verified_patch", capacity)
    _require_verified("heap verified_patch", heap)

    def _require_control(
        role: str, pairs: list[tuple[str, dict[str, Any]]],
    ) -> None:
        if not pairs:
            violations.append(f"acceptance capture has no {role} control case")
            return
        for key, case in pairs:
            if _case_verified(case):
                violations.append(
                    f"acceptance {key}: {role} control must not be verified"
                )
            if _case_downloadable(case):
                violations.append(
                    f"acceptance {key}: {role} control must not allow download"
                )
            if case.get("candidate_sha256"):
                violations.append(
                    f"acceptance {key}: {role} control must not carry a candidate"
                )

    _require_control("capacity no-manifest", capacity_control)
    _require_control("heap no-manifest", heap_control)
    if not target_scoped:
        violations.append(
            "acceptance capture has no passed target-scoped ownership case "
            "(patch.target_scope=passed)"
        )
    else:
        for key, case in target_scoped:
            scope = _as_dict(case.get("target_scope"))
            if not _case_verified(case):
                violations.append(
                    f"acceptance {key}: target-scoped case is not verified"
                )
            if not scope.get("name") or not isinstance(scope.get("va"), int):
                violations.append(
                    f"acceptance {key}: target_scope must carry name and numeric va"
                )
            if _as_list(case.get("checks_failed")):
                violations.append(
                    f"acceptance {key}: target-scoped case has failed checks "
                    f"{_as_list(case.get('checks_failed'))[:3]}"
                )
    if not wrong_target:
        violations.append(
            "acceptance capture has no fail-closed wrong-target control case"
        )
    else:
        for key, case in wrong_target:
            if _case_downloadable(case):
                violations.append(
                    f"acceptance {key}: wrong-target control must not allow download"
                )
            if case.get("candidate_present") is True:
                violations.append(
                    f"acceptance {key}: wrong-target control must not carry a "
                    "candidate"
                )
    detail = {
        "case_keys": [key for key, _case in cases],
        "review_api_cases": [key for key, _case in review],
        "capacity_verified": [key for key, _case in capacity],
        "capacity_controls": [key for key, _case in capacity_control],
        "heap_verified": [key for key, _case in heap],
        "heap_controls": [key for key, _case in heap_control],
        "target_scoped": [key for key, _case in target_scoped],
        "wrong_target_controls": [key for key, _case in wrong_target],
    }
    return violations, detail


def check_acceptance_contract(paths: Paths) -> Check:
    check = Check(
        "acceptance-contract",
        "Release acceptance capture (capacity + heap + target-scoped)",
    )
    payload, error = _load_json(paths.acceptance)
    if error:
        return check.fail(f"acceptance capture unavailable: {error}")
    violations, detail = validate_acceptance(payload)
    check.detail = (
        f"roles: capacity={len(detail.get('capacity_verified') or [])} "
        f"heap={len(detail.get('heap_verified') or [])} "
        f"target_scoped={len(detail.get('target_scoped') or [])} "
        f"controls={len(detail.get('capacity_controls') or []) + len(detail.get('heap_controls') or [])}"
    )
    if violations:
        check.violations.extend(violations)
        check.status = CHECK_FAILED
        return check
    return check.passed(check.detail)


# ---------------------------------------------------------------------------
# Release layer: local coverage gate (probes + acceptance + meta/invariants)
# ---------------------------------------------------------------------------


def evaluate_local_gate_payload(
    payload: Any, returncode: int, stderr: str = "",
) -> tuple[list[str], dict[str, Any]]:
    """Validate the ``--local --json`` coverage-gate summary for release."""
    violations: list[str] = []
    if not isinstance(payload, dict):
        return ["local coverage gate produced no JSON summary"], {}
    if returncode != 0:
        violations.append(
            f"local coverage gate exited non-zero (rc={returncode}); "
            f"stderr={_tail(stderr)}"
        )
    violations.extend(
        f"local coverage gate violation: {item}"
        for item in _as_list(payload.get("violations"))
    )
    if payload.get("ok") is False:
        violations.append("local coverage gate reported ok=false")
    open_ids = _as_list(payload.get("open_gap_ids"))
    if open_ids:
        violations.append(
            f"local coverage gate reports open gaps (release requires zero): "
            f"{open_ids[:5]}"
        )
    dynamic = payload.get("dynamic_unverified_count")
    dynamic_ids = _as_list(payload.get("dynamic_unverified_gap_ids"))
    if not isinstance(dynamic, int):
        if dynamic_ids:
            dynamic = len(dynamic_ids)
        else:
            violations.append(
                "local coverage gate summary has no dynamic_unverified_count "
                "(the release gate cannot verify dynamic_unverified==0)"
            )
            dynamic = None
    if isinstance(dynamic, int) and dynamic != 0:
        violations.append(
            f"local coverage gate reports dynamic_unverified={dynamic} "
            "(release requires zero)"
        )
    universe = _as_dict(payload.get("universe"))
    if not universe:
        violations.append(
            "local coverage gate summary has no universe block "
            "(release requires universe.unknown==0)"
        )
    else:
        unknown = universe.get("unknown")
        if unknown != 0:
            violations.append(
                f"local coverage gate universe.unknown={unknown!r} "
                "(release requires zero)"
            )
        unmapped = (
            _as_list(universe.get("unmapped_non_goal_ids"))
            or _as_list(universe.get("unmapped"))
        )
        if unmapped:
            violations.append(
                f"local coverage gate universe has unmapped non-goal cells: "
                f"{unmapped[:5]}"
            )
        if universe.get("ok") is False:
            violations.append("local coverage gate universe.ok=false")
        if universe.get("missing_reason_count"):
            violations.append(
                "local coverage gate universe counts non-goal/unavailable cells "
                "without a reason: "
                f"missing_reason_count={universe.get('missing_reason_count')}"
            )
    acceptance = _as_dict(payload.get("acceptance"))
    if not acceptance:
        violations.append(
            "local coverage gate summary has no acceptance field"
        )
    elif acceptance.get("ok") is not True:
        violations.append(
            "local coverage gate acceptance.ok is not true: "
            f"{_as_list(acceptance.get('violations'))[:3]}"
        )
    detail = {
        "open_gap_ids": open_ids,
        "dynamic_unverified": dynamic,
        "universe_unknown": universe.get("unknown"),
        "universe_cell_count": universe.get("cell_count"),
        "meta_audit": _as_dict(payload.get("meta_audit")),
        "invariants": _as_dict(payload.get("invariants")),
        "acceptance": acceptance,
    }
    return violations, detail


def check_local_coverage_gate(
    paths: Paths, run: Runner = run_command,
) -> tuple[Check, dict[str, Any] | None]:
    check = Check(
        "local-coverage-gate",
        "Local coverage gate (bounded probes + real-guest acceptance)",
    )
    script = paths.coverage_gate_script
    if not script.is_file():
        return check.fail(f"local coverage gate script missing: {script}"), None
    started = time.monotonic()
    result = run(
        [sys.executable, str(script), "--local", "--json"],
        paths.root,
        TIMEOUT_LOCAL,
    )
    check.elapsed_ms = int((time.monotonic() - started) * 1000)
    if result.timed_out:
        return check.fail(
            f"local coverage gate timed out after {TIMEOUT_LOCAL:.0f}s"
        ), None
    payload, error = _parse_json_output(result.stdout)
    if error:
        return check.fail(
            f"local coverage gate produced no usable summary: {error}; "
            f"rc={result.returncode}; stderr={_tail(result.stderr)}"
        ), None
    violations, detail = evaluate_local_gate_payload(
        payload, result.returncode, result.stderr
    )
    check.detail = (
        f"open={detail.get('open_gap_ids')} "
        f"dynamic_unverified={detail.get('dynamic_unverified')} "
        f"universe_unknown={detail.get('universe_unknown')} "
        f"cells={detail.get('universe_cell_count')}"
    )
    if violations:
        check.violations.extend(violations)
        check.status = CHECK_FAILED
        return check, payload
    return check.passed(check.detail), payload


# ---------------------------------------------------------------------------
# Release layer: meta-audit and acceptance invariants
# ---------------------------------------------------------------------------


def _payload_flag(payload: Any, keys: Sequence[str]) -> bool | None:
    data = _as_dict(payload)
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            return value
    return None


def check_meta_audit(
    paths: Paths,
    local_payload: dict[str, Any] | None,
    run: Runner = run_command,
) -> Check:
    check = Check(
        "meta-audit",
        "Meta-audit detector recall/precision over injected gaps",
    )
    summary = _as_dict((local_payload or {}).get("meta_audit"))
    if summary:
        flag = _payload_flag(summary, ("ok", "passed"))
        if flag is False:
            return check.fail(
                "meta-audit failed: "
                f"{_as_list(summary.get('violations'))[:3]}"
            )
        details = (
            f"recall={summary.get('recall')} precision={summary.get('precision')} "
            f"scenarios={summary.get('scenario_count')}"
        )
        if flag is None:
            return check.fail(
                f"local coverage gate meta_audit block has no ok/passed flag: "
                f"{details}"
            )
        return check.passed(details)
    script = paths.meta_audit_script
    if not script.is_file():
        return check.unavailable(
            "meta-audit unavailable: script "
            f"{META_AUDIT} is not present and the local gate summary has no "
            "meta_audit block (T2 mid-flight)"
        )
    started = time.monotonic()
    result = run(
        [sys.executable, str(script), "--json"],
        paths.root,
        TIMEOUT_META_AUDIT,
    )
    check.elapsed_ms = int((time.monotonic() - started) * 1000)
    if result.timed_out:
        return check.fail(
            f"meta-audit timed out after {TIMEOUT_META_AUDIT:.0f}s"
        )
    payload, error = _parse_json_output(result.stdout)
    if error:
        return check.fail(
            f"meta-audit produced no usable summary: {error}; "
            f"rc={result.returncode}; stderr={_tail(result.stderr)}"
        )
    flag = _payload_flag(payload, ("ok", "passed"))
    meta_violations = _as_list(payload.get("violations"))
    details = (
        f"recall={payload.get('recall')} precision={payload.get('precision')} "
        f"scenarios={payload.get('scenario_count')}"
    )
    if flag is not True or meta_violations:
        return check.fail(
            f"meta-audit failed (rc={result.returncode}): {meta_violations[:3]}",
            detail=details,
        )
    return check.passed(details)


def check_acceptance_invariants(
    paths: Paths,
    local_payload: dict[str, Any] | None,
    acceptance_payload: dict[str, Any] | None = None,
) -> Check:
    check = Check(
        "acceptance-invariants",
        "Acceptance invariant engine (packet/capture invariants)",
    )
    summary = _as_dict((local_payload or {}).get("invariants"))
    if summary:
        flag = _payload_flag(summary, ("ok", "passed"))
        invariant_violations = _as_list(summary.get("violations"))
        if flag is False or invariant_violations:
            return check.fail(
                "acceptance invariants failed: "
                f"{invariant_violations[:5]}"
            )
        if flag is None:
            return check.fail(
                "local coverage gate invariants block has no ok/passed flag"
            )
        return check.passed(
            f"packets_checked={summary.get('packets_checked')} "
            f"limitations={len(_as_list(summary.get('limitations')))}"
        )
    # Fallback: lazy-import the invariant engine and validate the capture.
    try:
        sys.path.insert(0, str(paths.root))
        from app.services import acceptance_invariants  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        return check.unavailable(
            "acceptance invariants unavailable: "
            f"module/app/services/acceptance_invariants.py missing "
            f"({type(exc).__name__}: {exc}) and the local gate summary has no "
            "invariants block (T2 mid-flight)"
        )
    checker = getattr(acceptance_invariants, "check_acceptance", None)
    if not callable(checker):
        return check.unavailable(
            "acceptance invariants unavailable: "
            "app.services.acceptance_invariants has no check_acceptance()"
        )
    if acceptance_payload is None:
        acceptance_payload, error = _load_json(paths.acceptance)
        if error:
            return check.fail(
                f"acceptance invariants cannot run: {error}"
            )
    try:
        result = checker(acceptance_payload)
    except Exception as exc:  # noqa: BLE001
        return check.fail(
            f"acceptance invariants raised: {type(exc).__name__}: {exc}"
        )
    if not isinstance(result, dict):
        return check.fail(
            f"acceptance invariants returned non-dict: {type(result).__name__}"
        )
    violations = _as_list(result.get("violations"))
    if result.get("ok") is not True or violations:
        return check.fail(
            f"acceptance invariants failed: {violations[:5]}"
        )
    return check.passed(
        f"packets_checked={result.get('packets_checked')} "
        f"(fallback check_acceptance)"
    )


def check_universe_evidence(
    paths: Paths, local_payload: dict[str, Any] | None,
) -> Check:
    """Release evidence that the capability universe has no unknown cells.

    Prefers the local gate summary (T2 gate asserts it); falls back to the
    committed ``coverage-matrix.json`` artifact only as corroboration, never to
    silently override a gate summary that reports unknowns.
    """
    check = Check(
        "universe-unknown-zero",
        "Capability universe has zero unknown cells and mapped non-goals",
    )
    summary = _as_dict((local_payload or {}).get("universe"))
    if summary:
        unknown = summary.get("unknown")
        unmapped = (
            _as_list(summary.get("unmapped_non_goal_ids"))
            or _as_list(summary.get("unmapped"))
        )
        if unknown != 0:
            return check.fail(
                f"universe.unknown={unknown!r} (release requires zero)"
            )
        if unmapped:
            return check.fail(
                f"universe has unmapped non-goal cells: {unmapped[:5]}"
            )
        if summary.get("missing_reason_count"):
            return check.fail(
                "universe non-goal/unavailable cells without a reason: "
                f"missing_reason_count={summary.get('missing_reason_count')}"
            )
        return check.passed(
            f"cells={summary.get('cell_count')} counts={summary.get('counts')}"
        )
    matrix_path = paths.root / "artifacts" / "capability-gap-audit-2026-11-14" / "coverage-matrix.json"
    matrix, error = _load_json(matrix_path)
    universe = _as_dict(_as_dict(matrix).get("universe"))
    if error or not universe:
        return check.unavailable(
            "universe evidence unavailable: local gate summary has no universe "
            "block and the capability matrix artifact has none (T2 mid-flight)"
        )
    if universe.get("unknown") != 0:
        return check.fail(
            f"coverage-matrix universe.unknown={universe.get('unknown')!r}"
        )
    return check.passed(
        f"cells={universe.get('cell_count')} (from coverage-matrix.json)"
    )


# ---------------------------------------------------------------------------
# Release layer: provider-matrix artifact (T4) with target-strict fields
# ---------------------------------------------------------------------------


def _rate_ok(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0.0 <= float(value) <= 1.0


def _first_present(data: dict[str, Any], aliases: Sequence[str]) -> Any:
    for key in aliases:
        if key in data:
            return data[key]
    return None


def _sha256_file(path: Path) -> str | None:
    import hashlib

    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _parse_sha256sums(text: str) -> tuple[dict[str, str], list[str]]:
    entries: dict[str, str] = {}
    violations: list[str] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            violations.append(
                f"SHA256SUMS line {line_no} is not sha256sum format: {raw_line!r}"
            )
            continue
        digest, name = parts[0].lower(), parts[1].strip()
        if name.startswith("*"):
            name = name[1:]
        if not name or name.startswith("/") or ".." in Path(name).parts:
            violations.append(
                f"SHA256SUMS line {line_no} has an unsafe/absolute path: {name!r}"
            )
            continue
        entries[name] = digest
    return entries, violations


def evaluate_provider_matrix(artifact_dir: Path) -> tuple[list[str], dict[str, Any]]:
    """Validate the T4 provider-matrix artifact (release evidence)."""
    violations: list[str] = []
    detail: dict[str, Any] = {}
    if not artifact_dir.is_dir():
        return (
            [f"provider-matrix artifact missing: {artifact_dir} (T4 mid-flight)"],
            {},
        )
    for name in PROVIDER_MATRIX_FILES:
        path = artifact_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            violations.append(f"provider-matrix file missing/empty: {name}")
    readme = artifact_dir / "README.md"
    if readme.is_file() and not readme.read_text(encoding="utf-8", errors="replace").strip():
        violations.append("provider-matrix README.md is empty")
    summary, error = _load_json(artifact_dir / "summary.json")
    if error:
        return violations + [f"provider-matrix summary.json invalid: {error}"], detail
    if not isinstance(summary, dict):
        return violations + ["provider-matrix summary.json is not an object"], detail
    detail["provider_status"] = summary.get("provider_status")
    if summary.get("schema_version") != 1:
        violations.append(
            f"provider-matrix summary.schema_version={summary.get('schema_version')!r} "
            "is not 1"
        )
    if summary.get("kind") != "provider_matrix":
        violations.append(
            f"provider-matrix summary.kind={summary.get('kind')!r} is not "
            "'provider_matrix'"
        )
    provider = _as_dict(summary.get("provider"))
    if not provider:
        violations.append("provider-matrix summary has no provider block")
    status = summary.get("provider_status")
    if status not in PROVIDER_PROVIDER_STATUSES:
        violations.append(
            f"provider-matrix provider_status={status!r} is not one of "
            f"{sorted(PROVIDER_PROVIDER_STATUSES)}"
        )
    if status in PROVIDER_UNAVAILABLE_STATUSES:
        reason = summary.get("unavailable_reason")
        if not isinstance(reason, str) or not reason.strip():
            violations.append(
                f"provider-matrix provider_status={status!r} requires a typed "
                "unavailable_reason"
            )
    cases = summary.get("cases")
    if not isinstance(cases, list) or len(cases) != PROVIDER_MATRIX_CASES:
        violations.append(
            "provider-matrix must record "
            f"{PROVIDER_MATRIX_CASES} case rows, got "
            f"{len(cases) if isinstance(cases, list) else 'none'}"
        )
        case_rows: list[dict[str, Any]] = []
    else:
        case_rows = [row for row in cases if isinstance(row, dict)]
        if len(case_rows) != len(cases):
            violations.append("provider-matrix summary.cases contains non-object rows")
    aggregate = _as_dict(summary.get("aggregate"))
    if not aggregate:
        violations.append("provider-matrix summary has no aggregate block")
    top_strict = _first_present(summary, PROVIDER_RATE_ALIASES["target_strict_pass_rate"])
    top_scope = _first_present(summary, PROVIDER_RATE_ALIASES["target_in_scope_rate"])
    if top_strict is None and "target_strict_pass_rate" not in aggregate:
        violations.append(
            "provider-matrix has no target_strict_pass_rate aggregate"
        )
    elif top_strict is not None and not _rate_ok(top_strict):
        violations.append(
            f"provider-matrix target_strict_pass_rate={top_strict!r} is not a "
            "ratio in [0,1]"
        )
    if top_scope is None and "target_in_scope_rate" not in aggregate:
        violations.append(
            "provider-matrix has no target_in_scope_rate aggregate"
        )
    elif top_scope is not None and not _rate_ok(top_scope):
        violations.append(
            f"provider-matrix target_in_scope_rate={top_scope!r} is not a "
            "ratio in [0,1]"
        )
    for key in ("target_strict_pass_rate", "target_in_scope_rate"):
        value = aggregate.get(key)
        if value is not None and not _rate_ok(value):
            violations.append(
                f"provider-matrix aggregate.{key}={value!r} is not a ratio in [0,1]"
            )
    case_ids: list[str] = []
    for index, row in enumerate(case_rows):
        case_id = str(row.get("case_id", "") or "")
        if not case_id:
            violations.append(f"provider-matrix cases[{index}] has no case_id")
        else:
            case_ids.append(case_id)
        for field in (
            "baseline_whole_image_disposition",
            "baseline_target_strict_disposition",
            "baseline_target_strict_expected",
            "baseline_target_strict_matches_expected",
            "target_scope_resolved",
            "target_in_scope",
        ):
            if field not in row:
                violations.append(
                    f"provider-matrix cases[{index}] ({case_id or '?'}) lacks "
                    f"target-strict field {field!r}"
                )
        if status not in PROVIDER_TRUSTED_STATUSES and row.get("ai_verified") is True:
            violations.append(
                f"provider-matrix cases[{index}] ({case_id or '?'}) claims "
                "ai_verified=true while the provider is not ok/reference"
            )
    # Per-case files with the full target-strict record contract.
    per_case_dir = artifact_dir / "per-case"
    per_case_files: set[str] = set()
    if not per_case_dir.is_dir():
        violations.append("provider-matrix per-case/ directory missing")
    else:
        for case_id in case_ids:
            path = per_case_dir / f"{case_id}.json"
            if not path.is_file():
                violations.append(
                    f"provider-matrix per-case file missing: per-case/{case_id}.json"
                )
                continue
            per_case_files.add(f"per-case/{case_id}.json")
            record, case_error = _load_json(path)
            if case_error:
                violations.append(
                    f"provider-matrix per-case/{case_id}.json invalid: {case_error}"
                )
                continue
            if not isinstance(record, dict):
                violations.append(
                    f"provider-matrix per-case/{case_id}.json is not an object"
                )
                continue
            missing = []
            for field in PROVIDER_CASE_REQUIRED_FIELDS:
                aliases = (field,) if field not in PROVIDER_CASE_ALIASES else (
                    PROVIDER_CASE_ALIASES[field]
                )
                if not any(alias in record for alias in aliases):
                    missing.append(field)
            if missing:
                violations.append(
                    f"provider-matrix per-case/{case_id}.json lacks target-strict "
                    f"fields: {missing}"
                )
            policy = record.get("target_policy")
            policy_ok = (
                (isinstance(policy, str) and bool(policy.strip()))
                or (isinstance(policy, dict) and bool(policy))
            )
            if not policy_ok:
                violations.append(
                    f"provider-matrix per-case/{case_id}.json target_policy must be "
                    "a non-empty string or object"
                )
            scope = record.get("target_scope")
            if scope is not None and not isinstance(scope, dict):
                violations.append(
                    f"provider-matrix per-case/{case_id}.json target_scope must be "
                    "an object or null"
                )
            scope_check = record.get("target_scope_check")
            if scope_check not in PROVIDER_TARGET_SCOPE_CHECK_VALUES:
                violations.append(
                    f"provider-matrix per-case/{case_id}.json "
                    f"target_scope_check={scope_check!r} is not one of "
                    f"{sorted(PROVIDER_TARGET_SCOPE_CHECK_VALUES)}"
                )
            if not isinstance(record.get("target_in_scope"), bool):
                violations.append(
                    f"provider-matrix per-case/{case_id}.json target_in_scope must "
                    "be a boolean"
                )
            baseline = _first_present(
                record, PROVIDER_CASE_ALIASES["baseline_whole_image"]
            )
            strict = _as_dict(record.get("baseline_target_strict"))
            if not strict:
                violations.append(
                    f"provider-matrix per-case/{case_id}.json "
                    "baseline_target_strict is missing/not an object"
                )
            else:
                strict_missing = [
                    field for field in
                    ("disposition", "verified", "expected", "matches_expected",
                     "target_scope", "target_in_scope", "actions")
                    if field not in strict
                ]
                if strict_missing:
                    violations.append(
                        f"provider-matrix per-case/{case_id}.json "
                        f"baseline_target_strict lacks fields: {strict_missing}"
                    )
            ai = _as_dict(_first_present(record, PROVIDER_CASE_ALIASES["ai_target"]))
            if not ai:
                violations.append(
                    f"provider-matrix per-case/{case_id}.json has no ai_target/ "
                    "ai_result block"
                )
            else:
                for field in ("attempted", "status"):
                    if field not in ai:
                        violations.append(
                            f"provider-matrix per-case/{case_id}.json ai_target lacks "
                            f"{field!r}"
                        )
                if (
                    status not in PROVIDER_TRUSTED_STATUSES
                    and ai.get("verified") is True
                ):
                    violations.append(
                        f"provider-matrix per-case/{case_id}.json claims "
                        "ai_target.verified=true while the provider is not "
                        "ok/reference"
                    )
            if baseline is None and "baseline_target_strict" not in record:
                violations.append(
                    f"provider-matrix per-case/{case_id}.json lacks a baseline block"
                )
    # SHA256SUMS must cover README/summary and every per-case file, and match.
    checksums_text = ""
    checksums_path = artifact_dir / "SHA256SUMS"
    if checksums_path.is_file():
        checksums_text = checksums_path.read_text(encoding="utf-8", errors="replace")
    entries, parse_violations = _parse_sha256sums(checksums_text)
    violations.extend(parse_violations)
    if not entries and checksums_path.is_file():
        violations.append("provider-matrix SHA256SUMS lists no files")
    required_names = {"README.md", "summary.json"} | per_case_files
    missing_sums = sorted(required_names - set(entries))
    if missing_sums:
        violations.append(
            f"provider-matrix SHA256SUMS does not cover required file(s): "
            f"{missing_sums[:6]}"
        )
    for name, digest in sorted(entries.items()):
        path = artifact_dir / name
        if not path.is_file():
            violations.append(
                f"provider-matrix SHA256SUMS references missing file: {name}"
            )
            continue
        actual = _sha256_file(path)
        if actual != digest:
            violations.append(
                f"provider-matrix SHA256SUMS digest mismatch for {name} "
                f"(listed={digest[:12]}… actual={(actual or 'unreadable')[:12]}…); "
                "the matrix is stale or tampered"
            )
    detail.update(
        {
            "cases": len(case_rows),
            "per_case_files": sorted(per_case_files),
            "sums_files": sorted(entries),
            "target_strict_pass_rate": top_strict,
            "target_in_scope_rate": top_scope,
        }
    )
    return violations, detail


def check_provider_matrix(paths: Paths) -> Check:
    check = Check(
        "provider-matrix",
        "Real provider matrix evidence with target-strict measurement (T4)",
    )
    violations, detail = evaluate_provider_matrix(paths.provider_matrix_dir)
    check.detail = (
        f"cases={detail.get('cases', 0)} "
        f"provider_status={detail.get('provider_status')} "
        f"target_strict_pass_rate={detail.get('target_strict_pass_rate')} "
        f"target_in_scope_rate={detail.get('target_in_scope_rate')}"
    )
    if violations:
        check.violations.extend(violations)
        check.status = CHECK_FAILED
        return check
    return check.passed(check.detail)


def evaluate_provider_coverage(artifact_dir: Path) -> tuple[list[str], dict[str, Any]]:
    """Validate the provider-coverage artifact (identity + statistics evidence).

    Required schema (built by ``scripts/build_provider_coverage.py``):
    ``summary.json`` with schema_version/kind/identity_policy/evidence_rows/
    aggregate/statistics/cost/seed, plus README.md and a SHA256SUMS that covers
    both files.  A row whose ``identity_ok`` is false may be recorded as served
    model evidence but must never be marked identity-verified / requested-model
    coverage; the international matrix must be explicitly ``not_satisfied``
    rather than silently omitted.
    """
    violations: list[str] = []
    detail: dict[str, Any] = {}
    if not artifact_dir.is_dir():
        return [f"provider-coverage artifact missing: {artifact_dir}"], detail
    for name in ("README.md", "summary.json", "SHA256SUMS"):
        if not (artifact_dir / name).is_file():
            violations.append(f"provider-coverage artifact missing file: {name}")
    if violations:
        return violations, detail
    summary, error = _load_json(artifact_dir / "summary.json")
    if error or not isinstance(summary, dict):
        return [f"provider-coverage summary unreadable: {error}"], detail
    if summary.get("kind") != "provider_coverage":
        violations.append(
            f"provider-coverage kind={summary.get('kind')!r} (expected provider_coverage)"
        )
    if summary.get("schema_version") != 1:
        violations.append(
            "provider-coverage schema_version is not 1: "
            f"{summary.get('schema_version')!r}"
        )
    rows = _as_list(summary.get("evidence_rows"))
    detail["rows"] = len(rows)
    if not rows:
        violations.append("provider-coverage has no evidence_rows")
    for index, raw in enumerate(rows):
        row = _as_dict(raw)
        label = row.get("row_id") or row.get("provider") or f"row[{index}]"
        for field in ("provider", "model_requested", "model_served",
                      "identity_ok", "status", "cases"):
            if field not in row:
                violations.append(f"provider-coverage row {label} missing {field}")
        if row.get("identity_ok") is False:
            if row.get("identity_verified") is True:
                violations.append(
                    f"provider-coverage row {label} claims identity_verified "
                    "with identity_ok=false"
                )
            if row.get("status") == "identity_verified_completed":
                violations.append(
                    f"provider-coverage row {label} is identity_verified_completed "
                    "with identity_ok=false (requested-model coverage overclaimed)"
                )
    policy = _as_dict(summary.get("identity_policy"))
    detail["identity_policy"] = bool(policy.get("applied_in_this_artifact"))
    if policy.get("applied_in_this_artifact") is not True:
        violations.append(
            "provider-coverage identity_policy.applied_in_this_artifact is not true"
        )
    aggregate = _as_dict(summary.get("aggregate"))
    for field in ("providers_completed_12case", "models_completed_12case"):
        if not isinstance(aggregate.get(field), int):
            violations.append(
                f"provider-coverage aggregate.{field} is not an integer"
            )
    detail["providers_completed_12case"] = aggregate.get("providers_completed_12case")
    detail["models_completed_12case"] = aggregate.get("models_completed_12case")
    not_satisfied = _as_list(aggregate.get("not_satisfied"))
    if not not_satisfied:
        violations.append(
            "provider-coverage aggregate.not_satisfied is empty: the international "
            "5-6 model matrix gap must be recorded explicitly"
        )
    if not _as_list(aggregate.get("blocked_reasons")):
        violations.append(
            "provider-coverage aggregate.blocked_reasons is empty: blocked "
            "providers must be recorded explicitly"
        )
    statistics = summary.get("statistics")
    serialized = json.dumps(statistics, sort_keys=True) if statistics else ""
    if not statistics or "wilson_ci95" not in serialized:
        violations.append(
            "provider-coverage statistics missing (per-model rates with wilson_ci95)"
        )
    detail["statistics"] = bool(statistics)
    cost = _as_dict(summary.get("cost"))
    seed = _as_dict(summary.get("seed"))
    if "available" not in cost:
        violations.append("provider-coverage cost.available missing (honest null)")
    if "available" not in seed:
        violations.append("provider-coverage seed.available missing (honest null)")
    detail["cost_available"] = cost.get("available")
    detail["seed_available"] = seed.get("available")
    # SHA256SUMS must cover README.md + summary.json and match on disk.
    checksums_path = artifact_dir / "SHA256SUMS"
    entries, parse_violations = _parse_sha256sums(
        checksums_path.read_text(encoding="utf-8", errors="replace")
    )
    violations.extend(parse_violations)
    for name in ("README.md", "summary.json"):
        if name not in entries:
            violations.append(
                f"provider-coverage SHA256SUMS does not cover {name}"
            )
            continue
        actual = _sha256_file(artifact_dir / name)
        if actual is None:
            violations.append(f"provider-coverage cannot hash {name}")
        elif actual.lower() != entries[name].lower():
            violations.append(
                f"provider-coverage SHA256SUMS mismatch for {name}: "
                f"recorded={entries[name]} actual={actual}"
            )
    return violations, detail


def check_provider_coverage(paths: Paths) -> Check:
    check = Check(
        "provider-coverage",
        "Provider/model coverage artifact: identity policy + statistics (P1)",
    )
    violations, detail = evaluate_provider_coverage(paths.provider_coverage_dir)
    check.detail = (
        f"rows={detail.get('rows', 0)} "
        f"providers_completed_12case={detail.get('providers_completed_12case')} "
        f"models_completed_12case={detail.get('models_completed_12case')} "
        f"identity_policy={detail.get('identity_policy')} "
        f"statistics={detail.get('statistics')} "
        f"cost_available={detail.get('cost_available')} "
        f"seed_available={detail.get('seed_available')}"
    )
    if violations:
        check.violations.extend(violations)
        check.status = CHECK_FAILED
        return check
    return check.passed(check.detail)


# ---------------------------------------------------------------------------
# Release layer: full pytest suite
# ---------------------------------------------------------------------------


def check_full_pytest(paths: Paths, run: Runner = run_command) -> Check:
    check = Check("full-pytest", "Full pytest suite (release gate)")
    started = time.monotonic()
    result = run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:xdist"],
        paths.root,
        TIMEOUT_FULL_PYTEST,
    )
    check.elapsed_ms = int((time.monotonic() - started) * 1000)
    if result.timed_out:
        return check.fail(
            f"full pytest suite timed out after {TIMEOUT_FULL_PYTEST:.0f}s"
        )
    if result.returncode != 0:
        return check.fail(
            f"full pytest suite failed (rc={result.returncode}); "
            f"stdout={_tail(result.stdout)}; stderr={_tail(result.stderr)}"
        )
    return check.passed(f"full pytest suite passed in {check.elapsed_ms} ms")


# ---------------------------------------------------------------------------
# --nightly layer: fresh real-Lima acceptance capture (never faked)
# ---------------------------------------------------------------------------


def probe_guest_runner() -> dict[str, Any]:
    """Probe the product's own guest-runner selection (no side effects)."""
    try:
        sys.path.insert(0, str(ROOT))
        from app.services.guest_runner import find_guest_runner  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "runner": "",
            "reason": f"guest_runner import failed: {type(exc).__name__}: {exc}",
        }
    try:
        runner = find_guest_runner("x86_64")
    except Exception as exc:  # noqa: BLE001
        return {
            "available": False,
            "runner": "",
            "reason": f"guest runner probe failed: {type(exc).__name__}: {exc}",
        }
    if runner is None:
        return {
            "available": False,
            "runner": "",
            "reason": "no native/qemu/Lima guest runner for x86_64 ELF",
        }
    kind = getattr(runner, "kind", "") or "runner"
    tool = str(getattr(runner, "tool", "") or "")
    name = Path(tool).name if tool else kind
    tier = getattr(runner, "tier", "") or ""
    return {
        "available": True,
        "runner": f"{kind}:{name}" if tool else kind,
        "tier": tier,
        "reason": "",
    }


def check_real_lima_capture(
    paths: Paths,
    run: Runner = run_command,
    *,
    runner_probe: Callable[[], dict[str, Any]] | None = None,
) -> Check:
    check = Check(
        "nightly-real-lima-acceptance",
        "Fresh real-Lima acceptance capture (temporary, artifacts untouched)",
        required=False,
    )
    probe = (runner_probe or probe_guest_runner)()
    if not probe.get("available"):
        return check.unavailable(
            "real-guest acceptance capture unavailable: "
            f"{probe.get('reason') or 'no guest runner'}"
        )
    script = paths.capture_script
    if not script.is_file():
        check.required = True
        return check.fail(f"acceptance capture script missing: {script}")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="br-release-gate-") as tmp:
        tmp_script = Path(tmp) / "capture_acceptance.py"
        try:
            shutil.copyfile(script, tmp_script)
        except OSError as exc:
            check.required = True
            return check.fail(
                f"cannot stage acceptance capture script: "
                f"{type(exc).__name__}: {exc}"
            )
        result = run(
            [sys.executable, str(tmp_script)], paths.root, TIMEOUT_CAPTURE
        )
        check.elapsed_ms = int((time.monotonic() - started) * 1000)
        generated = Path(tmp) / "acceptance.json"
        if result.timed_out:
            check.required = True
            return check.fail(
                f"real-Lima acceptance capture timed out after "
                f"{TIMEOUT_CAPTURE:.0f}s (runner={probe.get('runner')})"
            )
        if result.returncode != 0:
            check.required = True
            return check.fail(
                f"real-Lima acceptance capture failed (rc={result.returncode}, "
                f"runner={probe.get('runner')}); stderr={_tail(result.stderr)}"
            )
        payload, error = _load_json(generated)
        if error:
            check.required = True
            return check.fail(
                f"real-Lima acceptance capture produced no usable capture: {error}"
            )
        violations, detail = validate_acceptance(payload)
        if violations:
            check.required = True
            check.violations.extend(violations)
            check.status = CHECK_FAILED
            check.detail = (
                f"runner={probe.get('runner')} roles="
                f"{sorted(key for key, _case in _accepted_cases(payload))}"
            )
            return check
        check.required = True
        return check.passed(
            f"runner={probe.get('runner')} "
            f"tier={probe.get('tier')} "
            f"captured_in_seconds={check.elapsed_ms / 1000:.1f} "
            f"(temporary dir, repository artifacts untouched)"
        )


# ---------------------------------------------------------------------------
# Release freeze: tree identity (read-only git) + clean-worktree enforcement
# ---------------------------------------------------------------------------


@dataclass
class TreeIdentity:
    available: bool = False
    sha: str = ""
    branch: str = ""
    dirty_paths: list[str] = field(default_factory=list)
    error: str = ""

    @property
    def clean(self) -> bool | None:
        return (not self.dirty_paths) if self.available else None


def _git(paths: Paths, run: Runner, args: Sequence[str]) -> RunResult:
    """Run one read-only git command against the gated tree."""
    return run(["git", "-C", str(paths.root), *args], paths.root, TIMEOUT_GIT)


def read_tree_identity(paths: Paths, run: Runner = run_command) -> TreeIdentity:
    """Read HEAD SHA, branch and ``status --porcelain`` (read-only git only)."""
    head = _git(paths, run, ["rev-parse", "HEAD"])
    if head.timed_out:
        return TreeIdentity(error="git rev-parse HEAD timed out")
    if head.returncode != 0:
        return TreeIdentity(
            error=(head.stderr or head.stdout or "git rev-parse HEAD failed").strip()[:300]
        )
    sha = head.stdout.strip().splitlines()[0] if head.stdout.strip() else ""
    if not sha:
        return TreeIdentity(error="git rev-parse HEAD returned no SHA")
    branch_result = _git(paths, run, ["rev-parse", "--abbrev-ref", "HEAD"])
    branch = (
        branch_result.stdout.strip()
        if branch_result.returncode == 0 and branch_result.stdout.strip()
        else ""
    )
    status = _git(paths, run, ["status", "--porcelain"])
    if status.returncode != 0:
        return TreeIdentity(
            available=True,
            sha=sha,
            branch=branch,
            error=(status.stderr or "git status --porcelain failed").strip()[:300],
        )
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    return TreeIdentity(available=True, sha=sha, branch=branch, dirty_paths=dirty)


def _resolve_release_sha(
    paths: Paths, release_sha: str, run: Runner,
) -> tuple[str | None, str]:
    """Resolve ``--release-sha`` (short or full SHA) to a full commit SHA."""
    result = _git(paths, run, ["rev-parse", "--verify", f"{release_sha}^{{commit}}"])
    if result.timed_out:
        return None, "resolving --release-sha timed out"
    if result.returncode != 0:
        return None, (
            f"--release-sha {release_sha!r} is not a commit in this repository: "
            f"{_tail(result.stderr or result.stdout)}"
        )
    resolved = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if not resolved:
        return None, f"--release-sha {release_sha!r} resolved to an empty value"
    return resolved, ""


def check_release_tree_identity(
    paths: Paths,
    mode: str,
    release_sha: str | None,
    run: Runner = run_command,
) -> tuple[Check, dict[str, Any]]:
    """Freeze enforcement: record the tree identity and fail closed when unfrozen.

    * ``--release``: requires ``--release-sha``, a matching HEAD and a clean
      worktree (``git status --porcelain`` empty).
    * ``--nightly``: requires a clean worktree; ``--release-sha`` is verified
      when supplied.
    * ``--pr``: no freeze requirement (dirty trees are normal); a supplied
      ``--release-sha`` is still verified and a mismatch fails.
    """
    check = Check(
        "release-tree-identity",
        "Release tree identity: frozen SHA and clean worktree",
    )
    identity = read_tree_identity(paths, run)
    strict = mode in ("release", "nightly")
    tree: dict[str, Any] = {
        "release_sha": release_sha or None,
        "frozen_sha": identity.sha or None,
        "branch": identity.branch or None,
        "clean_tree": identity.clean,
    }
    if not identity.available:
        message = f"cannot read release tree identity: {identity.error}"
        if strict:
            return check.fail(
                message + " (release/nightly require a frozen git tree)"
            ), tree
        check.skipped(message + " (PR mode does not require freeze identity)")
        return check, tree
    detail = (
        f"sha={identity.sha} branch={identity.branch or 'unknown'} "
        f"clean_tree={identity.clean}"
    )
    if strict and identity.dirty_paths:
        preview = identity.dirty_paths[:8]
        check.fail(
            "worktree is dirty "
            f"({len(identity.dirty_paths)} path(s)); commit or freeze before "
            "release: " + "; ".join(preview)
            + ("; …" if len(identity.dirty_paths) > len(preview) else ""),
            detail=detail,
        )
        return check, tree
    if release_sha:
        resolved, error = _resolve_release_sha(paths, release_sha, run)
        if error:
            check.fail(error, detail=detail)
        else:
            tree["release_sha_resolved"] = resolved
            if resolved != identity.sha:
                check.fail(
                    f"--release-sha {release_sha!r} resolves to {resolved} but "
                    f"HEAD is {identity.sha}; the frozen tree moved or the "
                    "wrong SHA was given",
                    detail=detail,
                )
            else:
                detail += f" release_sha={release_sha} resolved={resolved} MATCH"
    elif mode == "release":
        check.fail(
            "release requires --release-sha <sha> from this phase on so the "
            "gate can prove the frozen tree identity (a clean worktree alone is "
            "not enough); freeze the tree, then pass the frozen commit SHA",
            detail=detail,
        )
    else:
        detail += " release_sha=not_required"
    if check.status == CHECK_FAILED:
        return check, tree
    return check.passed(detail), tree


# ---------------------------------------------------------------------------
# Mode orchestration
# ---------------------------------------------------------------------------


def _summarize(mode: str, checks: list[Check], started: float,
               notes: Sequence[str] = (),
               tree: dict[str, Any] | None = None) -> GateSummary:
    violations: list[str] = []
    for check in checks:
        if not check.required:
            continue
        if check.status == CHECK_FAILED:
            violations.extend(check.violations or [f"{check.check_id}: failed"])
        elif check.status == CHECK_UNAVAILABLE:
            violations.append(
                f"{check.check_id}: unavailable required check — "
                f"{check.detail or 'no reason reported'}"
            )
    summary = GateSummary(
        mode=mode,
        checks=checks,
        violations=violations,
        notes=list(notes),
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )
    if tree is not None:
        summary.release_sha = tree.get("release_sha")
        summary.frozen_sha = tree.get("frozen_sha")
        summary.branch = tree.get("branch")
        summary.clean_tree = tree.get("clean_tree")
    return summary


def _identity_blocked(
    mode: str,
    identity_check: Check,
    tree: dict[str, Any],
    started: float,
) -> GateSummary | None:
    """Fail fast when the tree identity check fails (do not burn the suite)."""
    if identity_check.status != CHECK_FAILED:
        return None
    return _summarize(
        mode,
        [identity_check],
        started,
        notes=[
            "release-tree-identity failed first: the remaining required checks "
            "were not run (fail fast on an unfrozen/dirty tree)"
        ],
        tree=tree,
    )


def run_pr(
    paths: Paths, run: Runner = run_command, *,
    build_audit: Callable[..., dict[str, Any]] | None = None,
    release_sha: str | None = None,
) -> GateSummary:
    """Fast PR layer: static coverage gate + claims diff + targeted pytest."""
    started = time.monotonic()
    identity, tree = check_release_tree_identity(paths, "pr", release_sha, run)
    checks = [
        identity,
        check_static_coverage_gate(paths, run),
        check_claims_measurement(paths, build_audit=build_audit),
        check_targeted_tests(paths, run),
    ]
    return _summarize("pr", checks, started, tree=tree)


def run_release(
    paths: Paths, run: Runner = run_command, *,
    build_audit: Callable[..., dict[str, Any]] | None = None,
    release_sha: str | None = None,
) -> GateSummary:
    """Release layer: frozen tree + PR checks + local gate + full pytest."""
    started = time.monotonic()
    identity, tree = check_release_tree_identity(
        paths, "release", release_sha, run
    )
    blocked = _identity_blocked("release", identity, tree, started)
    if blocked is not None:
        return blocked
    static = check_static_coverage_gate(paths, run)
    claims = check_claims_measurement(paths, build_audit=build_audit)
    acceptance = check_acceptance_contract(paths)
    local, local_payload = check_local_coverage_gate(paths, run)
    meta = check_meta_audit(paths, local_payload, run)
    invariants = check_acceptance_invariants(paths, local_payload)
    universe = check_universe_evidence(paths, local_payload)
    provider = check_provider_matrix(paths)
    provider_coverage = check_provider_coverage(paths)
    full = check_full_pytest(paths, run)
    return _summarize(
        "release",
        [identity, static, claims, acceptance, local, meta, invariants,
         universe, provider, provider_coverage, full],
        started,
        tree=tree,
    )


def run_nightly(
    paths: Paths, run: Runner = run_command, *,
    build_audit: Callable[..., dict[str, Any]] | None = None,
    runner_probe: Callable[[], dict[str, Any]] | None = None,
    release_sha: str | None = None,
) -> GateSummary:
    """Nightly layer: release checks + fresh real-Lima capture when available."""
    started = time.monotonic()
    identity, tree = check_release_tree_identity(
        paths, "nightly", release_sha, run
    )
    blocked = _identity_blocked("nightly", identity, tree, started)
    if blocked is not None:
        return blocked
    static = check_static_coverage_gate(paths, run)
    claims = check_claims_measurement(paths, build_audit=build_audit)
    acceptance = check_acceptance_contract(paths)
    local, local_payload = check_local_coverage_gate(paths, run)
    meta = check_meta_audit(paths, local_payload, run)
    invariants = check_acceptance_invariants(paths, local_payload)
    universe = check_universe_evidence(paths, local_payload)
    provider = check_provider_matrix(paths)
    provider_coverage = check_provider_coverage(paths)
    capture = check_real_lima_capture(paths, run, runner_probe=runner_probe)
    full = check_full_pytest(paths, run)
    notes = []
    if capture.status == CHECK_UNAVAILABLE:
        notes.append(
            "nightly real-Lima acceptance capture unavailable and not treated "
            "as a pass: " + (capture.detail or "no reason")
        )
    return _summarize(
        "nightly",
        [identity, static, claims, acceptance, local, meta, invariants,
         universe, provider, provider_coverage, capture, full],
        started,
        notes=notes,
        tree=tree,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


CHECK_MATRIX: dict[str, tuple[str, ...]] = {
    "pr": (
        "release-tree-identity",
        "static-coverage-gate",
        "claims-measurement-diff",
        "targeted-pytest",
    ),
    "release": (
        "release-tree-identity",
        "static-coverage-gate",
        "claims-measurement-diff",
        "acceptance-contract",
        "local-coverage-gate",
        "meta-audit",
        "acceptance-invariants",
        "universe-unknown-zero",
        "provider-matrix",
        "provider-coverage",
        "full-pytest",
    ),
    "nightly": (
        "release-tree-identity",
        "static-coverage-gate",
        "claims-measurement-diff",
        "acceptance-contract",
        "local-coverage-gate",
        "meta-audit",
        "acceptance-invariants",
        "universe-unknown-zero",
        "provider-matrix",
        "provider-coverage",
        "nightly-real-lima-acceptance",
        "full-pytest",
    ),
}


def _print_human(summary: GateSummary) -> None:
    counts = summary.status_counts()
    print(
        "release-gate: mode={mode} result={result} checks={checks} "
        "passed={passed} failed={failed} unavailable={unavailable} "
        "skipped={skipped} violations={violations} elapsed={elapsed:.1f}s".format(
            mode=summary.mode,
            result="PASS" if summary.ok else "FAIL",
            checks=len(summary.checks),
            passed=counts.get(CHECK_PASSED, 0),
            failed=counts.get(CHECK_FAILED, 0),
            unavailable=counts.get(CHECK_UNAVAILABLE, 0),
            skipped=counts.get(CHECK_SKIPPED, 0),
            violations=len(summary.violations),
            elapsed=summary.elapsed_ms / 1000.0,
        )
    )
    if any(value is not None for value in (
        summary.frozen_sha, summary.release_sha, summary.clean_tree,
        summary.branch,
    )):
        print(
            "  tree        frozen_sha={sha} branch={branch} clean_tree={clean} "
            "release_sha={release}".format(
                sha=summary.frozen_sha,
                branch=summary.branch,
                clean=summary.clean_tree,
                release=summary.release_sha,
            )
        )
    for check in summary.checks:
        print(
            "  {status:<11} {check_id}: {detail}".format(
                status=check.status.upper(),
                check_id=check.check_id,
                detail=check.detail or check.title,
            )
        )
    for note in summary.notes:
        print(f"  NOTE        {note}")
    if summary.violations:
        print("violations:")
        for violation in summary.violations:
            print(f"  - {violation}")


def _sha256_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()


def _lima_identity(run: Runner = run_command) -> dict[str, Any]:
    """Best-effort, read-only Lima/guest provenance (never raises)."""
    identity: dict[str, Any] = {"available": False}
    try:
        version = run(["limactl", "--version"], Path("/"), 30.0)
        if version.returncode == 0 and version.stdout.strip():
            identity["limactl_version"] = version.stdout.strip()
        listing = run(["limactl", "list", "--json"], Path("/"), 30.0)
        if listing.returncode == 0 and listing.stdout.strip():
            identity["available"] = True
            identity["list_sha256"] = _sha256_text(listing.stdout.strip())
            parsed = json.loads(listing.stdout)
            items = parsed if isinstance(parsed, list) else []
            if not items:
                # ``limactl list --json`` is newline-delimited JSON on some versions.
                items = []
                for line in listing.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, dict):
                        items.append(item)
            identity["vms"] = sorted(
                str(item.get("name"))
                for item in items
                if isinstance(item, dict) and item.get("name")
            )
    except Exception as exc:  # noqa: BLE001 - provenance is optional
        identity["error"] = f"{type(exc).__name__}: {exc}"
    config = Path.home() / ".lima" / "binaryrepair" / "lima.yaml"
    identity["config_present"] = config.is_file()
    identity["config_sha256"] = _sha256_file(config) if config.is_file() else None
    return identity


def _artifact_evidence(paths: Paths) -> dict[str, Any]:
    """Content-addressed digests of the committed release evidence inputs."""
    artifacts = {
        "artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json": None,
        "artifacts/capability-gap-audit-2026-11-14/gap-report.md": None,
        "artifacts/capability-gap-audit-2026-11-14/SHA256SUMS": None,
        "artifacts/coverage-closure-2026-11-14/acceptance.json": None,
        "artifacts/coverage-closure-2026-11-14/README.md": None,
        "artifacts/provider-matrix-2026-11-14/summary.json": None,
        "artifacts/provider-matrix-2026-11-14/SHA256SUMS": None,
        "artifacts/provider-coverage-2026-11-14/summary.json": None,
        "artifacts/provider-coverage-2026-11-14/SHA256SUMS": None,
        "artifacts/browser-e2e-2026-11-14/summary.json": None,
        "docs/status/claims.json": None,
        "docs/acceptance/non-goals-2026-11-14.md": None,
        "docs/acceptance/non-goal-roadmap-2026-11-14.md": None,
    }
    rows: dict[str, Any] = {}
    for relative, _unused in artifacts.items():
        path = paths.root / relative
        rows[relative] = {
            "present": path.is_file(),
            "sha256": _sha256_file(path) if path.is_file() else None,
        }
    return rows


def _mitigated_residual(checks: Sequence[Check]) -> list[str]:
    for check in checks:
        if check.check_id != "claims-measurement-diff":
            continue
        match = re.search(r"mitigated_residual=(\[[^\]]*\])", check.detail)
        if not match:
            continue
        try:
            parsed = json.loads(match.group(1).replace("'", '"'))
        except json.JSONDecodeError:
            return [match.group(1)]
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    return []


def _build_evidence(
    paths: Paths,
    summary: GateSummary,
    run: Runner = run_command,
    *,
    not_run: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a provenance-rich release evidence JSON (no repo mutation)."""
    import platform
    import sys

    tree_sha = None
    if summary.frozen_sha:
        tree_result = _git(paths, run, ["rev-parse", "HEAD^{tree}"])
        if tree_result.returncode == 0:
            tree_sha = tree_result.stdout.strip() or None
    environment = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    missing_not_run = list(dict.fromkeys(["github_actions", *not_run]))
    evidence: dict[str, Any] = {
        "schema_version": 1,
        "kind": "release_gate_evidence",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": summary.mode,
        "ok": summary.ok,
        "exit_code": 0 if summary.ok else 1,
        "frozen_sha": summary.frozen_sha,
        "release_sha": summary.release_sha,
        "branch": summary.branch,
        "clean_tree": summary.clean_tree,
        "tree_sha": tree_sha,
        "frozen_matches_release": (
            summary.frozen_sha == summary.release_sha
            if summary.frozen_sha and summary.release_sha else None
        ),
        "status_counts": summary.status_counts(),
        "violations": list(summary.violations),
        "notes": list(summary.notes),
        "elapsed_ms": int(summary.elapsed_ms),
        "checks": [check.to_dict() for check in summary.checks],
        "environment": environment,
        "lima": _lima_identity(run),
        "artifacts": _artifact_evidence(paths),
        "mitigated_residual": _mitigated_residual(summary.checks),
        "not_run": missing_not_run,
        "evidence_scope": (
            "local frozen-tree gate; proves the gated git tree identity and the "
            "measured checks. It does not prove a GitHub Actions run or binary "
            "provenance beyond the recorded artifact digests."
        ),
    }
    return evidence


def _write_evidence(path: Path, payload: dict[str, Any]) -> str:
    """Write the evidence JSON atomically enough for release use."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return f"{path}: {type(exc).__name__}: {exc}"
    return ""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Staged release/nightly gate: --pr (fast), --release (full), "
            "--nightly (full + real-Lima capture). Never fakes a check; exits "
            "non-zero on a violation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  .venv/bin/python scripts/release_gate.py --pr\n"
            "  .venv/bin/python scripts/release_gate.py --pr --json\n"
            "  .venv/bin/python scripts/release_gate.py --release "
            "--release-sha <frozen-commit-sha>\n"
            "  .venv/bin/python scripts/release_gate.py --nightly --json\n"
        ),
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--pr", dest="mode", action="store_const", const="pr",
        help="fast PR layer: static coverage gate + claims diff + targeted pytest",
    )
    modes.add_argument(
        "--release", dest="mode", action="store_const", const="release",
        help="release layer: local gate + acceptance + invariants + meta-audit "
             "+ provider matrix + full pytest",
    )
    modes.add_argument(
        "--nightly", dest="mode", action="store_const", const="nightly",
        help="nightly layer: release checks + fresh real-Lima capture when a "
             "guest runner is available (unavailable degrades honestly)",
    )
    parser.add_argument("--json", action="store_true",
                        help="print the structured summary as JSON")
    parser.add_argument(
        "--list-checks", action="store_true",
        help="print the mode/check matrix and exit (no checks are run)",
    )
    parser.add_argument(
        "--release-sha", default=None, metavar="SHA",
        help=(
            "frozen commit SHA to verify against the tree HEAD (read-only "
            "git rev-parse); required for --release, optional for --nightly "
            "and --pr"
        ),
    )
    parser.add_argument(
        "--evidence-out", type=Path, default=None, metavar="PATH",
        help=(
            "write a provenance-rich release evidence JSON to PATH after the "
            "gate run (gate result is unchanged; an unwritable path exits 2)"
        ),
    )
    parser.add_argument(
        "--root", type=Path, default=ROOT,
        help="tree root to gate (default: repository root; for tests/debug only)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.list_checks:
        print(json.dumps(
            {mode: list(checks) for mode, checks in CHECK_MATRIX.items()},
            indent=2,
        ))
        return 0
    if not args.mode:
        parser.error("one of --pr, --release or --nightly is required")
    release_sha = (args.release_sha or "").strip() or None
    if args.release_sha is not None and release_sha is None:
        parser.error("--release-sha must not be empty")
    paths = Paths(Path(args.root).resolve())
    try:
        if args.mode == "pr":
            summary = run_pr(paths, release_sha=release_sha)
        elif args.mode == "release":
            summary = run_release(paths, release_sha=release_sha)
        else:
            summary = run_nightly(paths, release_sha=release_sha)
    except KeyboardInterrupt:
        print("release-gate: interrupted", file=sys.stderr)
        return 130
    if args.evidence_out is not None:
        evidence = _build_evidence(paths, summary)
        error = _write_evidence(Path(args.evidence_out), evidence)
        if error:
            print(f"release-gate: evidence write failed: {error}",
                  file=sys.stderr)
            return 2
        print(f"release-gate: evidence written to {args.evidence_out}",
              file=sys.stderr)
    if args.json:
        print(json.dumps(summary.to_dict(), indent=2, sort_keys=True,
                         ensure_ascii=False))
    else:
        _print_human(summary)
    return 0 if summary.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
