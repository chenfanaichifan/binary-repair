"""V3 concrete-behaviour assertions for the frozen fixture manifest.

V3 asks one question: given what a candidate binary actually did on the frozen
test matrix, does it reproduce the reviewed contract byte for byte?

This module deliberately **executes nothing**. It is a pure function from
(manifest, observations) to a result, so that:

- the host and CI can run the assertions without running a binary, which the
  project forbids outside the disposable guest;
- Route A and Route B are judged by exactly the same code, so the F5 comparison
  compares like with like;
- the acceptance engine receives an ordinary obligation result
  (``passed`` / ``failed`` / ``not_run``) instead of a second verdict path.

The guest-side runner is responsible for producing :class:`Observation` values
(exit code, raw stdout bytes, raw stderr bytes). Nothing in this module may
default, repair, or reinterpret a missing observation: a missing result is
``not_run``, never ``passed``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = 1
GATE = "V3"
KINDS = ("valid", "invalid")

PASSED = "passed"
FAILED = "failed"
NOT_RUN = "not_run"


class ManifestError(ValueError):
    """The manifest is malformed or contradicts the reviewed contract."""


@dataclass(frozen=True)
class Observation:
    """What the candidate binary did, as raw bytes.

    ``stdout`` and ``stderr`` are bytes on purpose: the contract is byte-exact,
    and a comparison against decoded text would hide a stray ``\\r`` or a
    missing trailing newline.
    """

    return_code: int
    stdout: bytes = b""
    stderr: bytes = b""
    output_files: Mapping[str, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    kind: str
    result: str
    mismatches: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "kind": self.kind,
            "result": self.result,
            "mismatches": list(self.mismatches),
        }


@dataclass(frozen=True)
class SuiteResult:
    gate: str
    result: str
    cases: tuple[CaseResult, ...]
    passed: int
    failed: int
    not_run: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "result": self.result,
            "passed": self.passed,
            "failed": self.failed,
            "not_run": self.not_run,
            "cases": [case.as_dict() for case in self.cases],
        }

    def obligation(self) -> dict[str, Any]:
        """Shape this suite as an acceptance-engine obligation."""
        detail = (
            f"{self.passed} passed, {self.failed} failed, {self.not_run} not run"
        )
        return {
            "kind": "behaviour",
            "required": True,
            "result": self.result,
            "detail": detail,
        }


def load_manifest(path: str | Path) -> dict[str, Any]:
    """Load and structurally validate one manifest file."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # keep the filename in the error
        raise ManifestError(f"{path.name}: not valid JSON: {exc}") from exc
    return validate_manifest(raw, name=path.name)


def validate_manifest(
    raw: Any, *, name: str = "<manifest>"
) -> dict[str, Any]:
    """Structurally validate one already-parsed manifest.

    Structural validation only: it cannot tell whether an expectation is
    *correct*, only whether the file is a well-formed claim. Kept separate from
    :func:`load_manifest` so the rules can be tested without touching the
    filesystem.
    """
    if not isinstance(raw, dict):
        raise ManifestError(f"{name}: top level must be an object")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(
            f"{name}: schema_version must be {SCHEMA_VERSION}, "
            f"got {raw.get('schema_version')!r}"
        )
    for key in ("case_id", "original_sha256", "tests"):
        if key not in raw:
            raise ManifestError(f"{name}: missing {key!r}")
    tests = raw["tests"]
    if not isinstance(tests, list) or not tests:
        raise ManifestError(f"{name}: 'tests' must be a non-empty list")
    seen: set[str] = set()
    for index, case in enumerate(tests):
        where = f"{name}: tests[{index}]"
        if not isinstance(case, dict):
            raise ManifestError(f"{where}: must be an object")
        for key in ("id", "kind", "argv", "expected"):
            if key not in case:
                raise ManifestError(f"{where}: missing {key!r}")
        if case["kind"] not in KINDS:
            raise ManifestError(f"{where}: kind must be one of {KINDS}")
        if case["id"] in seen:
            raise ManifestError(f"{where}: duplicate id {case['id']!r}")
        seen.add(case["id"])
        argv = case["argv"]
        if not isinstance(argv, list) or not argv:
            raise ManifestError(f"{where}: 'argv' must be a non-empty list")
        expected = case["expected"]
        if not isinstance(expected, dict):
            raise ManifestError(f"{where}: 'expected' must be an object")
        for key in ("return_code", "stdout", "stderr"):
            if key not in expected:
                raise ManifestError(f"{where}: expected missing {key!r}")
        if not isinstance(expected["return_code"], int):
            raise ManifestError(f"{where}: expected.return_code must be an int")
        for key in ("stdout", "stderr"):
            if not isinstance(expected[key], str):
                raise ManifestError(f"{where}: expected.{key} must be a string")
    return raw


def input_length(case: Mapping[str, Any]) -> int:
    """Length of the argv[1] payload, in bytes as the program will see it."""
    argv = case["argv"]
    if len(argv) < 2:
        return 0
    return len(str(argv[1]).encode("utf-8"))


def validate_contract_bounds(
    manifest: Mapping[str, Any], *, dest_capacity: int, max_valid_len: int
) -> None:
    """Check the manifest against the reviewed capacity contract.

    This is the guard against silently weakening the oracle: every ``valid``
    case must fit ``DEST_CAPACITY`` once ``strcpy``'s NUL is counted, and every
    ``invalid`` case must exceed it. Editing a case to make a candidate pass
    therefore fails here, before any candidate runs.
    """
    if max_valid_len != dest_capacity - 1:
        raise ManifestError(
            f"contract says max_valid_len={max_valid_len} but dest_capacity="
            f"{dest_capacity} implies {dest_capacity - 1}"
        )
    for case in manifest["tests"]:
        length = input_length(case)
        kind = case["kind"]
        if kind == "valid" and length > max_valid_len:
            raise ManifestError(
                f"case {case['id']!r}: valid input of {length} bytes exceeds "
                f"max_valid_len={max_valid_len}"
            )
        if kind == "invalid" and length <= max_valid_len:
            raise ManifestError(
                f"case {case['id']!r}: invalid input of {length} bytes does not "
                f"exceed max_valid_len={max_valid_len}"
            )


def check_manifest_pair(
    valid: Mapping[str, Any],
    invalid: Mapping[str, Any],
    *,
    dest_capacity: int = 50,
    max_valid_len: int = 49,
) -> None:
    """Validate the two manifests as one frozen oracle.

    Catches the mistakes that would quietly split V3 into two standards: the
    two files describing different cases, different originals, or a different
    schema.
    """
    if valid.get("case_id") != invalid.get("case_id"):
        raise ManifestError("valid/invalid manifests disagree on case_id")
    if valid.get("original_sha256") != invalid.get("original_sha256"):
        raise ManifestError("valid/invalid manifests disagree on original_sha256")
    ids = [case["id"] for case in valid["tests"]] + [
        case["id"] for case in invalid["tests"]
    ]
    if len(ids) != len(set(ids)):
        raise ManifestError("case ids must be unique across both manifests")
    for manifest, kind in ((valid, "valid"), (invalid, "invalid")):
        for case in manifest["tests"]:
            if case["kind"] != kind:
                raise ManifestError(
                    f"case {case['id']!r}: kind {case['kind']!r} in the "
                    f"{kind} manifest"
                )
    validate_contract_bounds(
        valid, dest_capacity=dest_capacity, max_valid_len=max_valid_len
    )
    validate_contract_bounds(
        invalid, dest_capacity=dest_capacity, max_valid_len=max_valid_len
    )


def _decode_expected(value: str) -> bytes:
    return value.encode("utf-8")


def _first_difference(expected: bytes, actual: bytes) -> str:
    limit = min(len(expected), len(actual))
    for offset in range(limit):
        if expected[offset] != actual[offset]:
            return f"first difference at byte {offset}"
    return f"length differs: expected {len(expected)}, actual {len(actual)}"


def compare_case(case: Mapping[str, Any], observed: Observation) -> CaseResult:
    """Compare one case's expectation with one observation, byte for byte."""
    expected = case["expected"]
    mismatches: list[str] = []

    expected_rc = expected["return_code"]
    if observed.return_code != expected_rc:
        mismatches.append(
            f"return_code: expected {expected_rc}, actual {observed.return_code}"
        )

    for stream in ("stdout", "stderr"):
        want = _decode_expected(expected[stream])
        got = observed.stdout if stream == "stdout" else observed.stderr
        if want != got:
            mismatches.append(
                f"{stream}: expected {want!r}, actual {got!r} "
                f"({_first_difference(want, got)})"
            )

    allowed = set(expected.get("allowed_output_files") or ())
    unexpected = sorted(set(observed.output_files) - allowed)
    if unexpected:
        mismatches.append(f"unexpected output files: {unexpected}")

    return CaseResult(
        case_id=str(case["id"]),
        kind=str(case["kind"]),
        result=FAILED if mismatches else PASSED,
        mismatches=tuple(mismatches),
    )


def evaluate(
    manifest: Mapping[str, Any],
    observations: Mapping[str, Observation],
) -> SuiteResult:
    """Compare a whole manifest against observations keyed by case id."""
    cases: list[CaseResult] = []
    for case in manifest["tests"]:
        case_id = str(case["id"])
        observed = observations.get(case_id)
        if observed is None:
            cases.append(
                CaseResult(
                    case_id=case_id,
                    kind=str(case["kind"]),
                    result=NOT_RUN,
                    mismatches=("no observation supplied for this case",),
                )
            )
            continue
        cases.append(compare_case(case, observed))

    passed = sum(1 for case in cases if case.result == PASSED)
    failed = sum(1 for case in cases if case.result == FAILED)
    not_run = sum(1 for case in cases if case.result == NOT_RUN)

    if failed:
        result = FAILED
    elif not_run:
        result = NOT_RUN
    else:
        result = PASSED

    return SuiteResult(
        gate=GATE,
        result=result,
        cases=tuple(cases),
        passed=passed,
        failed=failed,
        not_run=not_run,
    )


def evaluate_files(
    manifests: Iterable[str | Path],
    observations: Mapping[str, Observation],
) -> SuiteResult:
    """Convenience wrapper: load every manifest and evaluate them as one gate.

    A malformed manifest is a failure of the oracle itself, so it raises
    instead of degrading to a result.
    """
    cases: list[CaseResult] = []
    passed = failed = not_run = 0
    for path in manifests:
        manifest = load_manifest(path)
        suite = evaluate(manifest, observations)
        cases.extend(suite.cases)
        passed += suite.passed
        failed += suite.failed
        not_run += suite.not_run
    if failed:
        result = FAILED
    elif not_run:
        result = NOT_RUN
    else:
        result = PASSED
    return SuiteResult(
        gate=GATE,
        result=result,
        cases=tuple(cases),
        passed=passed,
        failed=failed,
        not_run=not_run,
    )
