#!/usr/bin/env python3
"""Verify a release evidence branch is a reviewable, tamper-evident bundle.

The release flow keeps three things separate: the gated mainline commit, the
GitHub Actions/self-hosted gate evidence, and the evidence branch that stores
that evidence for review.  This checker ties them together with read-only git:

* the gated SHA is an ancestor of the mainline ref;
* the evidence branch tip contains
  ``artifacts/release-gate-*/{gate.json,freeze.json,README.md,SHA256SUMS}``;
* ``SHA256SUMS`` validates against the file blobs in the evidence commit;
* ``gate.json`` and ``freeze.json`` record exactly the gated SHA;
* the evidence branch only adds allowed paths (release-gate artifacts, release
  docs, CI acceptance docs, claims) relative to the gated commit.

Output (``--json``)::

    {"ok": bool, "gated_sha": str|null, "evidence_ref": str,
     "evidence_sha": str|null, "changed_paths": [str],
     "checks": [{"id": str, "status": "passed"|"failed", "detail": str}]}

Exit codes: 0 all checks passed, 1 any violation (and for unresolvable refs).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVIDENCE_REF = "release/2026-11-15-evidence"
DEFAULT_MAINLINE_REF = "origin/workbench-v3"
TIMEOUT_GIT = 30.0
REQUIRED_FILES = ("gate.json", "freeze.json", "README.md", "SHA256SUMS")
GATE_DIR_RE = re.compile(r"^artifacts/release-gate-[^/]+/$")
ALLOWED_PREFIXES = (
    "artifacts/release-gate-",
    "docs/release-",
    "docs/acceptance/ci-",
)
ALLOWED_EXACT = frozenset({"docs/status/claims.json"})
CHECK_IDS = (
    "gated-sha-resolves",
    "gated-is-ancestor",
    "evidence-tip",
    "evidence-files",
    "gate-json-sha",
    "freeze-json-sha",
    "sha256sums",
    "changed-paths",
)


def _run_git_bytes(root: Path, args: Sequence[str]) -> tuple[int, bytes, str]:
    """Run read-only git and return raw bytes (needed for digest checks)."""
    try:
        completed = subprocess.run(
            ["git", *args], cwd=str(root), capture_output=True, timeout=TIMEOUT_GIT
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, b"", f"{type(exc).__name__}: {exc}"
    return completed.returncode, completed.stdout or b"", (
        completed.stderr or b""
    ).decode("utf-8", "replace")


def _git_text(root: Path, args: Sequence[str]) -> tuple[int, str, str]:
    returncode, stdout, stderr = _run_git_bytes(root, args)
    return returncode, stdout.decode("utf-8", "replace"), stderr


def resolve_commit(root: Path, ref: str) -> tuple[str | None, str]:
    returncode, stdout, stderr = _git_text(root, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if returncode != 0:
        return None, f"cannot resolve {ref!r}: {(stderr or stdout).strip()[:300]}"
    sha = stdout.strip().splitlines()[0] if stdout.strip() else ""
    return (sha or None), ("" if sha else f"{ref!r} resolved to an empty SHA")


def is_ancestor(root: Path, ancestor: str, descendant: str) -> tuple[bool, str]:
    returncode, stdout, stderr = _git_text(
        root, ["merge-base", "--is-ancestor", ancestor, descendant]
    )
    if returncode == 0:
        return True, f"{ancestor[:12]} is an ancestor of {descendant[:12]}"
    return False, (
        f"{ancestor[:12]} is not an ancestor of {descendant[:12]}: "
        f"{(stderr or stdout).strip()[:200]}"
    )


def list_tree(root: Path, sha: str) -> list[str]:
    returncode, stdout, stderr = _git_text(root, ["ls-tree", "-r", "--name-only", sha])
    if returncode != 0:
        raise RuntimeError(f"git ls-tree failed for {sha}: {stderr.strip()[:300]}")
    return [path for path in stdout.splitlines() if path]


def read_blob(root: Path, sha: str, path: str) -> bytes | None:
    returncode, stdout, _stderr = _run_git_bytes(root, ["show", f"{sha}:{path}"])
    return stdout if returncode == 0 else None


def find_gate_dir(paths: Sequence[str]) -> tuple[str | None, str]:
    gate_entries = [
        path for path in paths if re.match(r"^artifacts/release-gate-[^/]+/", path)
    ]
    directories = sorted({
        "/".join(path.split("/", 2)[:2]) + "/" for path in gate_entries
    })
    if not directories:
        return None, "no artifacts/release-gate-*/ directory in the evidence tip"
    for directory in directories:
        present = {path[len(directory):] for path in paths if path.startswith(directory)}
        missing = [name for name in REQUIRED_FILES if name not in present]
        if not missing:
            return directory, f"evidence directory {directory} has all required files"
    details = []
    for directory in directories:
        present = {path[len(directory):] for path in paths if path.startswith(directory)}
        missing = [name for name in REQUIRED_FILES if name not in present]
        details.append(f"{directory} missing {missing}")
    return None, "incomplete evidence directory: " + "; ".join(details)


def parse_sums(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    entries: list[tuple[str, str]] = []
    errors: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            errors.append(f"SHA256SUMS:{number}: cannot parse {line!r}")
            continue
        digest, path = parts[0].strip().lower(), parts[1].strip().lstrip("*")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append(f"SHA256SUMS:{number}: invalid digest {digest!r}")
            continue
        entries.append((digest, path))
    if not entries and not errors:
        errors.append("SHA256SUMS is empty")
    return entries, errors


def path_allowed(path: str) -> bool:
    return path in ALLOWED_EXACT or any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def _read_json_blob(root: Path, sha: str, path: str) -> tuple[dict[str, Any] | None, str]:
    blob = read_blob(root, sha, path)
    if blob is None:
        return None, f"cannot read {path} from {sha[:12]}"
    try:
        payload = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"{path} is not valid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, f"{path} does not contain a JSON object"
    return payload, ""


def evaluate(
    *,
    gated_sha: str,
    evidence_ref: str = DEFAULT_EVIDENCE_REF,
    mainline_ref: str = DEFAULT_MAINLINE_REF,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Run every evidence-branch check with read-only git commands."""
    root = root.resolve()
    checks: list[dict[str, str]] = []

    def add(check_id: str, ok: bool, detail: str) -> None:
        checks.append({
            "id": check_id,
            "status": "passed" if ok else "failed",
            "detail": detail,
        })

    canonical, error = resolve_commit(root, gated_sha)
    add("gated-sha-resolves", canonical is not None, error or f"gated sha {canonical}")
    if canonical is None:
        return _summary(False, None, evidence_ref, None, [], checks)

    mainline_sha, mainline_error = resolve_commit(root, mainline_ref)
    if mainline_sha is None:
        add("gated-is-ancestor", False, mainline_error)
    else:
        ancestor, ancestor_detail = is_ancestor(root, canonical, mainline_sha)
        add("gated-is-ancestor", ancestor, ancestor_detail)

    evidence_sha, evidence_error = resolve_commit(root, evidence_ref)
    add("evidence-tip", evidence_sha is not None, evidence_error or f"evidence tip {evidence_sha}")
    if evidence_sha is None:
        for check_id in CHECK_IDS[3:]:
            add(check_id, False, "evidence tip unresolved")
        return _summary(False, canonical, evidence_ref, None, [], checks)

    paths = list_tree(root, evidence_sha)
    gate_dir, gate_dir_detail = find_gate_dir(paths)
    add("evidence-files", gate_dir is not None, gate_dir_detail)
    changed_paths: list[str] = []
    returncode, stdout, stderr = _git_text(
        root, ["diff", "--name-only", canonical, evidence_sha]
    )
    diff_ok = returncode == 0
    if diff_ok:
        changed_paths = [path for path in stdout.splitlines() if path]
    if gate_dir is None:
        for check_id in ("gate-json-sha", "freeze-json-sha", "sha256sums"):
            add(check_id, False, "evidence directory incomplete")
        if diff_ok:
            _add_changed_paths(add, changed_paths)
        else:
            add("changed-paths", False,
                f"git diff failed: {(stderr or stdout).strip()[:200]}")
        return _summary(False, canonical, evidence_ref, evidence_sha, changed_paths, checks)

    gate_path = gate_dir + "gate.json"
    freeze_path = gate_dir + "freeze.json"
    gate_payload, gate_error = _read_json_blob(root, evidence_sha, gate_path)
    if gate_payload is None:
        add("gate-json-sha", False, gate_error)
    else:
        gate_shas = (gate_payload.get("frozen_sha"), gate_payload.get("release_sha"))
        gate_ok = gate_shas == (canonical, canonical)
        add(
            "gate-json-sha",
            gate_ok,
            f"gate.json frozen_sha/release_sha={gate_shas} gated={canonical}",
        )

    freeze_payload, freeze_error = _read_json_blob(root, evidence_sha, freeze_path)
    if freeze_payload is None:
        add("freeze-json-sha", False, freeze_error)
    else:
        freeze_ok, freeze_detail = _freeze_matches_gated(freeze_payload, canonical)
        add("freeze-json-sha", freeze_ok, freeze_detail)

    sums_blob = read_blob(root, evidence_sha, gate_dir + "SHA256SUMS")
    if sums_blob is None:
        add("sha256sums", False, "SHA256SUMS unreadable")
    else:
        entries, sum_errors = parse_sums(sums_blob.decode("utf-8", "replace"))
        failures = list(sum_errors)
        covered = {path for _digest, path in entries}
        for name in REQUIRED_FILES:
            if name != "SHA256SUMS" and name not in covered:
                failures.append(f"SHA256SUMS does not cover {name}")
        for digest, name in entries:
            blob = read_blob(root, evidence_sha, gate_dir + name)
            if blob is None:
                failures.append(f"SHA256SUMS references missing file {name}")
                continue
            actual = hashlib.sha256(blob).hexdigest()
            if actual != digest:
                failures.append(f"SHA256SUMS mismatch for {name}")
        add(
            "sha256sums",
            not failures,
            f"{len(entries)} hash entry(ies) validated"
            if not failures else "; ".join(failures[:5]),
        )

    if diff_ok:
        _add_changed_paths(add, changed_paths)
    else:
        add("changed-paths", False, f"git diff failed: {(stderr or stdout).strip()[:200]}")
    ok = all(check["status"] == "passed" for check in checks)
    return _summary(ok, canonical, evidence_ref, evidence_sha, changed_paths, checks)


def _add_changed_paths(add, changed_paths: list[str]) -> None:
    disallowed = [path for path in changed_paths if not path_allowed(path)]
    add(
        "changed-paths",
        not disallowed,
        f"{len(changed_paths)} changed path(s), all allowed" if not disallowed
        else f"disallowed changed path(s): {disallowed[:10]}",
    )


def _freeze_matches_gated(freeze: dict[str, Any], gated: str) -> tuple[bool, str]:
    requested = freeze.get("requested_sha")
    head = freeze.get("head_sha")
    summary = freeze.get("gate_summary") if isinstance(freeze.get("gate_summary"), dict) else {}
    problems: list[str] = []
    if requested is not None and requested != gated:
        problems.append(f"freeze.json requested_sha={requested} != {gated}")
    if head is not None and head != gated:
        problems.append(f"freeze.json head_sha={head} != {gated}")
    if requested is None and head is None:
        problems.append("freeze.json records neither requested_sha nor head_sha")
    for key in ("frozen_sha", "release_sha"):
        value = summary.get(key)
        if value != gated:
            problems.append(f"freeze.json gate_summary.{key}={value} != {gated}")
    return (not problems), ("; ".join(problems) if problems else "freeze.json pins match the gated sha")


def _summary(
    ok: bool,
    gated_sha: str | None,
    evidence_ref: str,
    evidence_sha: str | None,
    changed_paths: list[str],
    checks: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "ok": ok,
        "gated_sha": gated_sha,
        "evidence_ref": evidence_ref,
        "evidence_sha": evidence_sha,
        "changed_paths": changed_paths,
        "checks": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a release evidence branch against the gated commit (read-only).",
    )
    parser.add_argument("--gated-sha", required=True, help="gated release commit SHA")
    parser.add_argument("--evidence-ref", default=DEFAULT_EVIDENCE_REF,
                        help=f"evidence branch/ref (default: {DEFAULT_EVIDENCE_REF})")
    parser.add_argument("--mainline-ref", default=DEFAULT_MAINLINE_REF,
                        help=f"mainline ref the gated sha must be an ancestor of "
                             f"(default: {DEFAULT_MAINLINE_REF})")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root (default: this checkout; tests/diagnostics only)")
    parser.add_argument("--json", action="store_true", help="print the JSON summary")
    args = parser.parse_args(argv)
    payload = evaluate(
        gated_sha=args.gated_sha,
        evidence_ref=args.evidence_ref,
        mainline_ref=args.mainline_ref,
        root=args.root.resolve(),
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "verify-evidence-branch: {result} gated={gated} evidence={evidence}".format(
                result="PASS" if payload["ok"] else "FAIL",
                gated=payload["gated_sha"],
                evidence=payload["evidence_sha"],
            )
        )
        for check in payload["checks"]:
            print(f"  {check['status'].upper():<7} {check['id']}: {check['detail']}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
