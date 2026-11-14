#!/usr/bin/env python3
"""Release drift check: release tag vs mainline vs evidence branch.

A release tag is only trustworthy while it points at the current mainline tip
and the evidence branch's gate evidence was produced for exactly that commit.
This checker is read-only (git queries only) and exits 1 on drift or on an
evidence/tag association mismatch.

Output (``--json``)::

    {"ok": bool, "tag_sha": str|null, "mainline_sha": str|null,
     "drift": int|null, "evidence_gated_sha": str|null,
     "tag": str, "mainline_ref": str, "evidence_ref": str,
     "evidence_sha": str|null, "reasons": [str]}

``drift`` is the number of mainline commits that are not reachable from the tag.
The script never writes to git and only fetches when ``--offline`` is not given.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAINLINE_REF = "origin/workbench-v3"
TIMEOUT_GIT = 30.0
#: ``artifacts/release-gate-<date>/gate.json`` inside the evidence branch.
GATE_JSON_RE = re.compile(r"^artifacts/release-gate-[^/]+/gate\.json$")


@dataclass
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False


Runner = Callable[[Sequence[str], Path, float], CommandResult]


def run_command(command: Sequence[str], cwd: Path, timeout: float) -> CommandResult:
    """Run one read-only command, capturing stdout/stderr."""
    try:
        result = subprocess.run(
            list(command), cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return CommandResult(1, "", f"{type(exc).__name__}: {exc}")
    return CommandResult(
        result.returncode, result.stdout or "", result.stderr or "",
        timed_out=False,
    )


def git(run: Runner, root: Path, args: Sequence[str]) -> CommandResult:
    """Run one read-only git command in ``root``."""
    return run(["git", *args], root, TIMEOUT_GIT)


def derive_evidence_ref(tag: str) -> str:
    """Map ``release-<date>`` to the conventional evidence branch name."""
    prefix = "release-"
    if tag.startswith(prefix):
        return f"release/{tag[len(prefix):]}-evidence"
    return f"{tag}-evidence"


def resolve_commit(run: Runner, root: Path, ref: str) -> tuple[str | None, str]:
    """Resolve a ref to a full commit SHA (read-only)."""
    result = git(run, root, ["rev-parse", "--verify", f"{ref}^{{commit}}"])
    if result.timed_out:
        return None, f"resolving {ref!r} timed out"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "not found").strip()[:300]
        return None, f"cannot resolve {ref!r}: {detail}"
    sha = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    return (sha or None), ("" if sha else f"{ref!r} resolved to an empty SHA")


def count_drift(run: Runner, root: Path, tag_sha: str, mainline_sha: str) -> tuple[int | None, str]:
    """Count mainline commits not reachable from the tag."""
    result = git(run, root, ["rev-list", "--count", f"{tag_sha}..{mainline_sha}"])
    if result.timed_out:
        return None, "drift count timed out"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "rev-list failed").strip()[:300]
        return None, f"cannot count drift: {detail}"
    try:
        return int(result.stdout.strip().splitlines()[0]), ""
    except (ValueError, IndexError):
        return None, f"unexpected rev-list output: {result.stdout.strip()[:200]!r}"


def _evidence_gate_paths(run: Runner, root: Path, evidence_sha: str) -> list[str]:
    result = git(run, root, ["ls-tree", "-r", "--name-only", evidence_sha])
    if result.returncode != 0:
        return []
    return sorted(path for path in result.stdout.splitlines() if GATE_JSON_RE.match(path))


def read_evidence_gated_sha(
    run: Runner,
    root: Path,
    evidence_ref: str,
    tag: str,
) -> tuple[str | None, str | None, str]:
    """Return ``(evidence_sha, gated_sha, detail)`` for the evidence branch."""
    evidence_sha, error = resolve_commit(run, root, evidence_ref)
    if error:
        return None, None, error
    candidates = _evidence_gate_paths(run, root, evidence_sha)
    if not candidates:
        return evidence_sha, None, f"{evidence_ref!r} tip has no artifacts/release-gate-*/gate.json"
    # Prefer the evidence directory named after the tag date, else the last one.
    expected = ""
    match = re.match(r"^release-(.+)$", tag)
    if match:
        expected = f"artifacts/release-gate-{match.group(1)}/gate.json"
    path = expected if expected in candidates else candidates[-1]
    result = git(run, root, ["show", f"{evidence_sha}:{path}"])
    if result.returncode != 0 or not result.stdout.strip():
        return evidence_sha, None, f"cannot read {path} from {evidence_ref!r}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return evidence_sha, None, f"{path} is not valid JSON: {exc}"
    gated = payload.get("frozen_sha") or payload.get("release_sha")
    if not isinstance(gated, str) or not gated:
        return evidence_sha, None, f"{path} records no frozen_sha/release_sha"
    return evidence_sha, gated, f"evidence {path} gated {gated}"


def evaluate(
    *,
    tag: str,
    mainline_ref: str = DEFAULT_MAINLINE_REF,
    evidence_ref: str | None = None,
    offline: bool = False,
    root: Path = ROOT,
    run: Runner = run_command,
) -> dict[str, Any]:
    """Collect the drift/evidence facts.  Never mutates the repository."""
    reasons: list[str] = []
    if not offline:
        fetch = git(run, root, ["fetch", "--tags", "--force", "origin"])
        if fetch.returncode != 0:
            reasons.append(
                "fetch failed (using existing refs): "
                + (fetch.stderr or fetch.stdout or "unknown error").strip()[:300]
            )
    evidence_ref = evidence_ref or derive_evidence_ref(tag)
    tag_sha, tag_error = resolve_commit(run, root, tag)
    mainline_sha, mainline_error = resolve_commit(run, root, mainline_ref)
    if tag_error:
        reasons.append(tag_error)
    if mainline_error:
        reasons.append(mainline_error)
    drift: int | None = None
    if tag_sha and mainline_sha:
        drift, drift_error = count_drift(run, root, tag_sha, mainline_sha)
        if drift_error:
            reasons.append(drift_error)
    evidence_sha, evidence_gated_sha, evidence_detail = (None, None, "")
    if tag_sha:
        evidence_sha, evidence_gated_sha, evidence_detail = read_evidence_gated_sha(
            run, root, evidence_ref, tag
        )
        if evidence_gated_sha is None:
            reasons.append(evidence_detail)
        elif evidence_gated_sha != tag_sha:
            reasons.append(
                f"evidence gated sha {evidence_gated_sha} != tag sha {tag_sha}"
            )
    if drift is not None and drift > 0:
        reasons.append(f"mainline has drifted {drift} commit(s) since the tag")
    if tag_sha and mainline_sha and tag_sha != mainline_sha:
        reasons.append(f"tag sha {tag_sha} != mainline sha {mainline_sha}")
    ok = bool(
        tag_sha
        and mainline_sha
        and drift == 0
        and evidence_gated_sha == tag_sha
    )
    return {
        "ok": ok,
        "tag": tag,
        "tag_sha": tag_sha,
        "mainline_ref": mainline_ref,
        "mainline_sha": mainline_sha,
        "drift": drift,
        "evidence_ref": evidence_ref,
        "evidence_sha": evidence_sha,
        "evidence_gated_sha": evidence_gated_sha,
        "reasons": reasons,
    }


def main(argv: list[str] | None = None, *, run: Runner = run_command) -> int:
    parser = argparse.ArgumentParser(
        description="Check release tag/mainline/evidence drift (read-only).",
    )
    parser.add_argument("--tag", required=True, help="release tag, e.g. release-2026-11-15")
    parser.add_argument("--mainline-ref", default=DEFAULT_MAINLINE_REF,
                        help=f"mainline ref (default: {DEFAULT_MAINLINE_REF})")
    parser.add_argument("--evidence-ref", default=None,
                        help="evidence branch ref (default: derived from --tag)")
    parser.add_argument("--offline", action="store_true",
                        help="do not fetch; use the refs already present")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root (default: this checkout; tests/diagnostics only)")
    parser.add_argument("--json", action="store_true", help="print the JSON summary")
    args = parser.parse_args(argv)
    payload = evaluate(
        tag=args.tag,
        mainline_ref=args.mainline_ref,
        evidence_ref=args.evidence_ref,
        offline=args.offline,
        root=args.root.resolve(),
        run=run,
    )
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        print(
            "release-drift: {result} tag={tag} tag_sha={tag_sha} "
            "mainline={mainline_sha} drift={drift} evidence_gated={gated}".format(
                result="OK" if payload["ok"] else "DRIFT",
                tag=payload["tag"],
                tag_sha=payload["tag_sha"],
                mainline_sha=payload["mainline_sha"],
                drift=payload["drift"],
                gated=payload["evidence_gated_sha"],
            )
        )
        for reason in payload["reasons"]:
            print(f"  - {reason}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
