#!/usr/bin/env python3
"""Validate release provenance in a release-gate evidence JSON.

The release gate records a provenance block that binds the gated git tree, the
audit/acceptance/provider/browser artifact digests, the acceptance subjects
(fixture and candidate SHA-256 chains), the builder/runner identity (local
frozen tree or GitHub Actions) and the Lima guest identity for nightly runs.
This script re-checks that block and the on-disk digests; it never executes the
gate or claims a CI run.

Usage::

    python scripts/verify_provenance.py --evidence artifacts/release-gate-2026-11-15/gate.json
    python scripts/verify_provenance.py --dir artifacts/release-gate-2026-11-15 --json

Exit codes: 0 valid, 1 violation, 2 usage/unreadable input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import release_gate as gate  # noqa: E402


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _load(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{path}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, f"{path}: payload is not a JSON object"
    return payload, ""


def _check_materials(payload: dict[str, Any], root: Path) -> list[str]:
    violations: list[str] = []
    provenance = _as_dict(payload.get("provenance"))
    materials = _as_dict(provenance.get("materials"))
    artifacts = _as_dict(materials.get("artifacts"))
    if not artifacts:
        violations.append("provenance.materials.artifacts is empty")
    for relative, raw in sorted(artifacts.items()):
        row = _as_dict(raw)
        if not row.get("present"):
            continue
        digest = str(row.get("sha256") or "")
        if len(digest) != 64:
            violations.append(f"artifact {relative} has no sha256")
            continue
        actual = _sha256_file(root / relative)
        if actual is None:
            violations.append(f"artifact {relative} is recorded present but unreadable")
        elif actual != digest:
            violations.append(
                f"artifact {relative} digest mismatch: recorded={digest} actual={actual}")
    fixtures = _as_dict(materials.get("fixtures"))
    for relative, raw in sorted(fixtures.items()):
        row = _as_dict(raw)
        if row.get("present") and row.get("sha256"):
            actual = _sha256_file(root / relative)
            if actual and actual != row.get("sha256"):
                violations.append(f"fixture {relative} digest mismatch")
    acceptance = _as_dict(materials.get("acceptance_subjects"))
    cases = _as_dict(acceptance.get("cases"))
    if not acceptance.get("available") or not cases:
        violations.append("provenance.materials.acceptance_subjects has no cases")
    for case_id, raw in sorted(cases.items()):
        row = _as_dict(raw)
        if "candidate_sha256" in row and row.get("candidate_sha256") is not None:
            if len(str(row.get("candidate_sha256"))) != 64:
                violations.append(
                    f"acceptance subject {case_id} candidate_sha256 invalid")
    return violations


def check_evidence(
    payload: dict[str, Any], *, root: Path = ROOT,
) -> dict[str, Any]:
    if payload.get("kind") != "release_gate_evidence":
        return {
            "ok": False,
            "violations": [f"not release_gate_evidence: kind={payload.get('kind')!r}"],
            "checks": {},
        }
    mode = str(payload.get("mode") or "")
    if mode not in {"release", "nightly"}:
        return {
            "ok": False,
            "violations": [f"unsupported gate mode {mode!r}"],
            "checks": {},
        }
    violations = list(gate.validate_provenance(payload, mode=mode))
    violations.extend(_check_materials(payload, root))
    provenance = _as_dict(payload.get("provenance"))
    subject = _as_dict(provenance.get("subject"))
    tree_sha = str(subject.get("tree_sha") or "")
    if tree_sha and tree_sha != str(payload.get("tree_sha") or ""):
        violations.append(
            "provenance.subject.tree_sha does not match gate evidence tree_sha")
    builder = _as_dict(provenance.get("builder"))
    guest = _as_dict(provenance.get("guest"))
    checks = {
        "mode": mode,
        "builder_kind": builder.get("kind"),
        "github_run": _as_dict(builder.get("github")).get("run_id"),
        "guest_available": guest.get("available"),
        "limactl_version": guest.get("limactl_version"),
        "artifact_count": len(_as_dict(_as_dict(provenance.get("materials")).get("artifacts"))),
        "acceptance_cases": len(_as_dict(_as_dict(_as_dict(provenance.get("materials")).get("acceptance_subjects")).get("cases"))),
    }
    return {"ok": not violations, "violations": violations, "checks": checks}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a release-gate evidence provenance block.")
    parser.add_argument("--evidence", type=Path,
                        help="path to gate.json (default: <dir>/gate.json)")
    parser.add_argument("--dir", type=Path,
                        help="evidence directory containing gate.json")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root used to re-hash recorded artifacts")
    parser.add_argument("--json", action="store_true",
                        help="print the structured result")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    evidence = args.evidence
    if evidence is None and args.dir is not None:
        evidence = args.dir / "gate.json"
    if evidence is None:
        parser.error("pass --evidence PATH or --dir DIR")
    payload, error = _load(evidence)
    if error or payload is None:
        print(f"verify-provenance: {error}", file=sys.stderr)
        return 2
    result = check_evidence(payload, root=Path(args.root))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            "verify-provenance: {status} builder={builder} guest={guest} "
            "subjects={subjects} violations={count}".format(
                status="PASS" if result["ok"] else "FAIL",
                builder=result["checks"].get("builder_kind"),
                guest=result["checks"].get("guest_available"),
                subjects=result["checks"].get("acceptance_cases"),
                count=len(result["violations"]),
            )
        )
        for violation in result["violations"]:
            print(f"  - {violation}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
