#!/usr/bin/env python3
"""Flake-quarantine policy checker.

The release gate treats a quarantined test as debt with an owner and a hard
expiry; a flaky test may be quarantined for at most 14 days and may never be a
gate-critical test (target-scope, acceptance/invariant, release gate, provider
coverage, claims or evidence checks). This checker validates the registry JSON:

* top-level ``schema_version`` (int), ``generated_at`` (ISO date/datetime),
  ``entries`` (list) and ``prohibited`` (non-empty list of patterns);
* every entry has ``test_id``, ``owner``, ``reason``, ``opened``, ``expiry``
  and ``evidence``;
* ``test_id`` names an existing test file under ``tests/`` (optionally
  ``file::test``);
* ``opened <= expiry`` and the quarantine window is at most 14 days;
* a non-expired registry has no entry past its ``expiry`` relative to
  ``--as-of`` (default: today);
* no entry matches a prohibited gate-critical pattern, and the registry
  ``prohibited`` list covers every required gate-critical category;
* no duplicate ``test_id`` entries.

``--json`` prints ``{ok, registry, ...violations}``; exit code is 0 iff ok, 2
when the registry or args are unusable.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "docs" / "operations" / "flake-quarantine-2026-11-15.json"
SCHEMA_VERSION = 1
MAX_QUARANTINE_DAYS = 14
ENTRY_FIELDS = ("test_id", "owner", "reason", "opened", "expiry", "evidence")

#: Gate-critical categories that may never be quarantined. The registry
#: ``prohibited`` list must contain every pattern below; entries matching any of
#: them (or any additional registry pattern) are policy violations.
REQUIRED_PROHIBITED: tuple[str, ...] = (
    "tests/test_target_scope.py::*",
    "tests/test_acceptance_invariants.py::*",
    "tests/test_release_gate.py::*",
    "tests/test_provider_matrix.py::*",
    "tests/test_provider_coverage_artifact.py::*",
    "tests/test_capability_audit.py::*",
    "tests/test_coverage_gate.py::*",
    "tests/test_ci_evidence.py::*",
    "tests/test_contract_revision.py::*",
)

_TEST_ID_PATTERN = re.compile(r"^tests/[A-Za-z0-9_./-]+\.py(?:::[^\s]+)?$")


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _parse_generated_at(value: Any) -> datetime | date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    return parsed


def _matches_prohibited(test_id: str, patterns: Iterable[str]) -> str | None:
    """Return the first prohibited pattern matching ``test_id``, if any."""
    for pattern in patterns:
        text = str(pattern or "").strip()
        if not text:
            continue
        if text.endswith("::*"):
            base = text[:-3]
            if test_id == base or test_id.startswith(base + "::"):
                return text
        if fnmatch.fnmatch(test_id, text):
            return text
    return None


def _evidence_ok(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value) and all(
            isinstance(item, str) and item.strip() for item in value
        )
    return False


def _check_entry(index: int, entry: Any, as_of: date,
                 prohibited: list[str], violations: list[str],
                 seen_ids: set[str]) -> None:
    prefix = f"entries[{index}]"
    if not isinstance(entry, dict):
        violations.append(f"{prefix} is not an object")
        return
    missing = [key for key in ENTRY_FIELDS if not str(entry.get(key, "") or "").strip()]
    if missing:
        violations.append(f"{prefix} missing fields: {missing}")
        return

    test_id = str(entry.get("test_id", "") or "").strip()
    if not _TEST_ID_PATTERN.fullmatch(test_id):
        violations.append(
            f"{prefix} test_id is not a tests/*.py[::test] id: {test_id!r}")
    else:
        file_part = test_id.split("::", 1)[0]
        test_path = ROOT / file_part
        if not test_path.is_file():
            violations.append(
                f"{prefix} test file does not exist: {file_part}")
    if test_id in seen_ids:
        violations.append(f"{prefix} duplicate test_id: {test_id}")
    seen_ids.add(test_id)

    owner = str(entry.get("owner", "") or "").strip()
    reason = str(entry.get("reason", "") or "").strip()
    if not owner:
        violations.append(f"{prefix} owner is empty")
    if not reason:
        violations.append(f"{prefix} reason is empty")
    if not _evidence_ok(entry.get("evidence")):
        violations.append(
            f"{prefix} evidence must be a non-empty string or string list")

    opened = _parse_date(entry.get("opened"))
    expiry = _parse_date(entry.get("expiry"))
    if opened is None:
        violations.append(f"{prefix} opened is not an ISO date")
    if expiry is None:
        violations.append(f"{prefix} expiry is not an ISO date")
    if opened is not None and expiry is not None:
        if expiry < opened:
            violations.append(f"{prefix} expiry is before opened")
        window = (expiry - opened).days
        if window > MAX_QUARANTINE_DAYS:
            violations.append(
                f"{prefix} quarantine window is {window} days "
                f"(max {MAX_QUARANTINE_DAYS})")
        if expiry < as_of:
            violations.append(
                f"{prefix} quarantine expired on {expiry.isoformat()} "
                f"(as-of {as_of.isoformat()})")

    matched = _matches_prohibited(test_id, prohibited)
    if matched is not None:
        violations.append(
            f"{prefix} quarantines a gate-critical test "
            f"({test_id!r} matches prohibited pattern {matched!r})")


def evaluate_registry(payload: Any, *, as_of: date | None = None,
                      registry_path: Path | None = None) -> dict[str, Any]:
    """Validate one parsed registry payload and return the report payload."""
    resolved_as_of = as_of or date.today()
    report: dict[str, Any] = {
        "ok": False,
        "registry": str(registry_path) if registry_path is not None else "",
        "as_of": resolved_as_of.isoformat(),
        "schema_version": None,
        "generated_at": None,
        "entry_count": 0,
        "active_count": 0,
        "prohibited": [],
        "prohibited_count": 0,
        "required_prohibited": list(REQUIRED_PROHIBITED),
        "missing_required_prohibited": [],
        "violations": [],
    }
    violations: list[str] = report["violations"]
    if not isinstance(payload, dict):
        violations.append("registry is not a JSON object")
        return report

    schema_version = payload.get("schema_version")
    report["schema_version"] = schema_version
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        violations.append("schema_version must be an integer")
    elif schema_version != SCHEMA_VERSION:
        violations.append(
            f"schema_version {schema_version} != supported {SCHEMA_VERSION}")

    generated_at = payload.get("generated_at")
    if _parse_generated_at(generated_at) is None:
        violations.append("generated_at is not an ISO date/datetime")
    report["generated_at"] = generated_at

    entries = payload.get("entries")
    if not isinstance(entries, list):
        violations.append("entries must be a list")
        entries = []
    report["entry_count"] = len(entries)

    prohibited_raw = payload.get("prohibited")
    if not isinstance(prohibited_raw, list) or not prohibited_raw:
        violations.append("prohibited must be a non-empty list")
        prohibited_raw = []
    prohibited = [str(item).strip() for item in prohibited_raw
                  if isinstance(item, str)]
    if len(prohibited) != len(prohibited_raw):
        violations.append("prohibited must contain only strings")
    report["prohibited"] = prohibited
    report["prohibited_count"] = len(prohibited)
    missing_required = [
        pattern for pattern in REQUIRED_PROHIBITED if pattern not in prohibited
    ]
    report["missing_required_prohibited"] = missing_required
    if missing_required:
        violations.append(
            "prohibited does not cover required gate-critical patterns: "
            f"{missing_required}")

    seen_ids: set[str] = set()
    active = 0
    for index, entry in enumerate(entries):
        _check_entry(index, entry, resolved_as_of, prohibited, violations, seen_ids)
        if isinstance(entry, dict):
            expiry = _parse_date(entry.get("expiry"))
            opened = _parse_date(entry.get("opened"))
            if (
                expiry is not None
                and opened is not None
                and expiry >= resolved_as_of
            ):
                active += 1
    report["active_count"] = active
    report["ok"] = not violations
    return report


def load_registry(path: Path) -> tuple[Any | None, str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    try:
        return json.loads(text), ""
    except json.JSONDecodeError as exc:
        return None, f"JSONDecodeError: {exc}"


def _format_text(report: dict[str, Any]) -> str:
    lines = [
        "flake-policy: ok={ok} registry={registry} as_of={as_of} "
        "schema={schema} entries={entries} active={active} "
        "prohibited={prohibited} violations={violations}".format(
            ok=report["ok"],
            registry=report["registry"],
            as_of=report["as_of"],
            schema=report["schema_version"],
            entries=report["entry_count"],
            active=report["active_count"],
            prohibited=report["prohibited_count"],
            violations=len(report["violations"]),
        )
    ]
    for violation in report["violations"]:
        lines.append(f"FAIL {violation}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="validate the flake-quarantine registry policy")
    parser.add_argument(
        "--registry", type=Path, default=DEFAULT_REGISTRY,
        help="registry JSON path (default: docs/operations/"
             "flake-quarantine-2026-11-15.json)")
    parser.add_argument(
        "--as-of", type=str, default="",
        help="ISO date used for expiry checks (default: today)")
    parser.add_argument(
        "--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    as_of: date | None = None
    if args.as_of:
        as_of = _parse_date(args.as_of)
        if as_of is None:
            print(f"ERROR: --as-of is not an ISO date: {args.as_of}",
                  file=sys.stderr)
            return 2
    payload, error = load_registry(args.registry)
    if payload is None:
        print(f"ERROR: registry unavailable: {error}", file=sys.stderr)
        return 2
    report = evaluate_registry(payload, as_of=as_of,
                               registry_path=args.registry)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print(_format_text(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
