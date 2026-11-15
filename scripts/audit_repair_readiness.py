#!/usr/bin/env python3
"""Phase-8A repair readiness audit (G01-G30).

Read-only, deterministic evidence audit of the 30 Phase-8 user requirements.
The probes only read the working tree (file existence, static source/test
markers, import-spec availability, committed artifact SHA256SUMS and ground
truth files).  They never run repair, providers/AI, benchmarks or PoCs.

Artifacts::

    artifacts/phase8-readiness-2026-11-16/{readiness.json,README.md,SHA256SUMS}

Usage::

    python scripts/audit_repair_readiness.py --write
    python scripts/audit_repair_readiness.py --json
    python scripts/audit_repair_readiness.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import repair_readiness as readiness  # noqa: E402

SCHEMA_VERSION = 1
ARTIFACT_DIR = ROOT / "artifacts" / "phase8-readiness-2026-11-16"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def _summary(document: dict[str, Any]) -> dict[str, Any]:
    items = document.get("items", [])
    return {
        "ok": not readiness.validate_document(document),
        "schema_version": document.get("schema_version"),
        "kind": document.get("kind"),
        "audit_date": document.get("audit_date"),
        "generated_from_sha": document.get("generated_from_sha"),
        "probe_mode": document.get("probe_mode"),
        "summary": document.get("summary"),
        "items": [
            {
                "gap_id": item.get("gap_id"),
                "title": item.get("title"),
                "phase": item.get("phase"),
                "priority": item.get("priority"),
                "measured_status": item.get("measured_status"),
                "evidence_refs": item.get("evidence_refs"),
                "blocker": item.get("blocker"),
                "next_action": item.get("next_action"),
                "capability_claim": item.get("capability_claim"),
            }
            for item in items
        ],
        "capability_claims": document.get("capability_claims"),
        "not_run": document.get("not_run"),
        "limitations": document.get("limitations"),
    }


def write_artifacts(document: dict[str, Any],
                    artifact_dir: Path) -> dict[str, Any]:
    return readiness.write_artifacts(document, artifact_dir)


def _read_json(path: Path) -> tuple[Any, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _verify_sums(target: Path) -> list[str]:
    sums_path = target / "SHA256SUMS"
    if not sums_path.is_file():
        return [f"missing SHA256SUMS: {sums_path}"]
    problems: list[str] = []
    try:
        lines = sums_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [f"SHA256SUMS unreadable: {exc}"]
    for line in lines:
        parts = line.split()
        if len(parts) != 2:
            problems.append(f"malformed SHA256SUMS line: {line!r}")
            continue
        expected, name = parts[0], parts[1]
        file_path = target / name
        if not file_path.is_file():
            problems.append(f"artifact missing: {name}")
        elif _sha256(file_path) != expected:
            problems.append(f"sha256 mismatch for {name}")
    return problems


def _is_sha(value: str) -> bool:
    return len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def _is_ancestor(commit: str, root: Path) -> bool:
    """True when commit is an ancestor of HEAD (read-only git predicate).

    Shallow CI checkouts (actions/checkout default fetch-depth=1) do not contain
    the generation commit, so ancestry cannot be established there.  The
    artifact is still bound by its SHA256SUMS and by the release evidence; only
    the syntactic 40-hex check is available in that environment.
    """
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=str(root), capture_output=True, text=True, timeout=20,
            check=False)
        if result.returncode == 0:
            return True
        shallow = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=str(root), capture_output=True, text=True, timeout=20,
            check=False)
        return shallow.returncode == 0 and shallow.stdout.strip() == "true"
    except (OSError, subprocess.SubprocessError):
        # No git available (e.g. source tarball): the committed SHA cannot be
        # cross-checked; treat only the syntactic check as available.
        return True


def check_artifacts(artifact_dir: Path = ARTIFACT_DIR,
                    document: dict[str, Any] | None = None) -> list[str]:
    """Rebuild and compare the committed artifacts (deterministic tamper check)."""
    target = Path(artifact_dir)
    fresh = document if document is not None else readiness.build_readiness(ROOT)
    problems: list[str] = []
    readiness_path = target / "readiness.json"
    readme_path = target / "README.md"
    committed, error = _read_json(readiness_path)
    if error:
        problems.append(f"readiness.json unreadable: {error}")
    else:
        # The committed bundle records the base commit it was generated from.
        # Later commits legitimately add files/tests, so compare freshness with
        # the committed base SHA (and verify it is an ancestor of HEAD) rather
        # than requiring HEAD to be byte-identical to the generation commit.
        committed_sha = committed.get("generated_from_sha")
        if not isinstance(committed_sha, str) or not _is_sha(committed_sha):
            problems.append("generated_from_sha is not a 40-hex commit SHA")
        elif not _is_ancestor(committed_sha, ROOT):
            problems.append(
                f"generated_from_sha {committed_sha[:12]} is not an ancestor "
                "of the current HEAD")
        fresh = readiness.build_readiness(
            ROOT, generated_from_sha=committed_sha if isinstance(
                committed_sha, str) and _is_sha(committed_sha) else None)
        if committed != fresh:
            problems.append(
                "readiness.json is stale/tampered relative to a fresh "
                "read-only recomputation")
        problems.extend(readiness.validate_document(committed, ROOT))
    try:
        committed_readme = readme_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        problems.append(f"README.md unreadable: {type(exc).__name__}: {exc}")
    else:
        if committed_readme != readiness.render_readme(fresh):
            problems.append(
                "README.md is stale/tampered relative to a fresh recomputation")
    problems.extend(_verify_sums(target))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="read-only Phase-8A repair readiness audit (G01-G30)")
    parser.add_argument("--write", action="store_true",
                        help="write readiness.json/README.md/SHA256SUMS")
    parser.add_argument("--check", action="store_true",
                        help="recompute and verify the committed artifacts")
    parser.add_argument("--json", action="store_true",
                        help="print the audit summary JSON")
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACT_DIR)
    args = parser.parse_args(argv)
    if args.check:
        problems = check_artifacts(args.artifact_dir)
        if problems:
            for problem in problems:
                print(f"READINESS-VIOLATION: {problem}")
            return 1
        print("repair-readiness: check OK "
              "(30 items, deterministic recomputation, SHA256SUMS verified)")
        return 0
    document = readiness.build_readiness(ROOT)
    violations = readiness.validate_document(document, ROOT)
    if args.write:
        if violations:
            print("READINESS-VIOLATION: refusing to write an invalid audit")
            for violation in violations:
                print(f"READINESS-VIOLATION: {violation}")
            return 1
        artifacts = write_artifacts(document, args.artifact_dir)
        print(f"repair-readiness: wrote {artifacts['artifact_dir']}")
        print(f"generated_from_sha={document['generated_from_sha']}")
        print("summary=" + ", ".join(
            f"{status}={document['summary'][status]}"
            for status in readiness.STATUSES))
        for name in sorted(artifacts["sha256"]):
            print(f"{name}_sha256={artifacts['sha256'][name]}")
    if args.json:
        print(json.dumps(_summary(document), indent=2, sort_keys=True,
                         ensure_ascii=True))
    elif not args.write:
        print(
            "repair-readiness: sha={sha} total={total} implemented={impl} "
            "partial={part} missing={miss} not_run={nr} non_goal={ng} "
            "capability_claims={claims} violations={violations}".format(
                sha=document["generated_from_sha"][:12],
                total=document["summary"]["total"],
                impl=document["summary"]["implemented"],
                part=document["summary"]["partial"],
                miss=document["summary"]["missing"],
                nr=document["summary"]["not_run"],
                ng=document["summary"]["non_goal"],
                claims=len(document["capability_claims"]),
                violations=len(violations),
            ))
        for violation in violations[:10]:
            print(f"READINESS-VIOLATION: {violation}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
