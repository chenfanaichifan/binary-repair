#!/usr/bin/env python3
"""Audit the `partial` usage contract at live-bridge 6d67140.

Three questions, answered from immutable git objects (read-only):

  1. does `aggregate_job_usage` return `partial`?
  2. does `_ai_usage_for_job` pass it through unchanged?
  3. does the legacy plan fallback report `partial: false`?

It also pins the relation to canonical 1938c31 (an ancestor) and records the
canonical follow-up commit dc3bcd3 as an observation.  No ref is created,
moved, merged or pushed by this script.

Usage:
    python probe_134_partial_6d67140.py [--repo binary-repair] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

LIVE = "6d67140"
CANONICAL = "1938c31"
FOLLOWUP = "dc3bcd3"


def git(repo: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def show(repo: Path, rev: str, path: str) -> str:
    return git(repo, "show", f"{rev}:{path}")


def exists(repo: Path, rev: str, path: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{rev}:{path}"],
        capture_output=True,
    ).returncode == 0


def is_ancestor(repo: Path, rev: str, maybe_ancestor: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", maybe_ancestor, rev],
        capture_output=True,
    ).returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="binary-repair")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    checks: list[dict] = []

    # Resolve once so abbreviations never leak into equality checks.
    live_full = git(repo, "rev-parse", LIVE).strip()
    canonical_full = git(repo, "rev-parse", CANONICAL).strip()
    followup_full = (
        git(repo, "rev-parse", FOLLOWUP).strip()
        if subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"{FOLLOWUP}^{{commit}}"],
            capture_output=True,
        ).returncode == 0
        else None
    )

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    model_calls = show(repo, LIVE, "app/services/model_calls.py")
    controller = show(repo, LIVE, "app/controller_api.py")
    canonical_model_calls = show(repo, CANONICAL, "app/services/model_calls.py")
    canonical_controller = show(repo, CANONICAL, "app/controller_api.py")

    # 1. aggregate_job_usage returns partial.
    check(
        "aggregate_returns_partial",
        "def aggregate_job_usage(" in model_calls
        and '"partial": len(real) != len(rows),' in model_calls,
        'aggregate_job_usage(...) -> dict[str, Any] | None with '
        '"partial": len(real) != len(rows)',
    )
    check(
        "aggregate_partial_is_false_when_all_complete",
        "partial" in model_calls and "len(real) != len(rows)" in model_calls,
        "partial is the exact expression len(real) != len(rows): False when all "
        "rows carry both counts",
    )
    check(
        "aggregate_null_rows_do_not_erase_real_usage",
        "if not real:" in model_calls and "return None" in model_calls,
        "no real rows -> None; mixed -> sum real + partial True; never zero-pad",
    )

    # 2. _ai_usage_for_job passes partial through unchanged.
    check(
        "controller_passes_aggregate_through",
        "return aggregate_job_usage(data_dir=_data_dir(), job_id=job_id)"
        in controller,
        "_ai_usage_for_job returns aggregate_job_usage(...) untouched when "
        "model_calls rows exist",
    )
    check(
        "controller_does_not_rebuild_partial",
        '"partial"' not in controller.split("def _placeholder_routes")[0]
        .split("def _ai_usage_for_job")[1]
        .split("return {")[0],
        "no local partial derivation before the passthrough return",
    )

    # 3. plan fallback reports partial false.
    fallback = re.search(
        r'return \{\s*"input_tokens": values\[0\],\s*'
        r'"output_tokens": values\[1\],\s*"partial": False,\s*\}',
        controller,
    )
    check(
        "plan_fallback_partial_false",
        fallback is not None,
        'legacy plan fallback returns {"input_tokens": ..., '
        '"output_tokens": ..., "partial": False}',
    )

    # 4. canonical 1938c31 is the ancestor without partial and without V4.
    check(
        "canonical_1938c31_lacks_partial",
        '"partial"' not in canonical_model_calls
        and '"partial"' not in canonical_controller,
        "1938c31 aggregate/controller carry no partial field",
    )
    check(
        "canonical_1938c31_lacks_v4",
        not exists(repo, CANONICAL, "app/domain/v4.py"),
        "1938c31 has no app/domain/v4.py (V4 stack only exists on live-bridge)",
    )

    # 5. topology.
    merge_base = git(repo, "merge-base", CANONICAL, LIVE).strip()
    check(
        "canonical_is_merge_base",
        merge_base == canonical_full,
        f"merge-base({CANONICAL}, {LIVE}) = {merge_base}",
    )
    left, right = git(repo, "rev-list", "--left-right", "--count",
                      f"{CANONICAL}...{LIVE}").split()
    check(
        "live_is_66_ahead_and_canonical_is_0",
        (int(left), int(right)) == (0, 66),
        f"rev-list --left-right --count = {left} {right}",
    )
    live_parents = git(repo, "rev-list", "--parents", "-n1", live_full).split()
    check(
        "live_parent_is_41ff540",
        live_parents[:2] == [live_full, git(repo, "rev-parse", "41ff540").strip()],
        f"6d67140 parent = {live_parents[1] if len(live_parents) > 1 else None}",
    )
    merge_parents = git(repo, "rev-list", "--parents", "-n1", "41ff540").split()
    check(
        "41ff540_merges_c217046_and_3f21d31",
        merge_parents[1:] == [
            git(repo, "rev-parse", "c217046").strip(),
            git(repo, "rev-parse", "3f21d31").strip(),
        ],
        f"41ff540 parents = {merge_parents[1:]}",
    )
    check(
        "partial_commits_are_on_the_live_line",
        is_ancestor(repo, LIVE, "de48d6a") and is_ancestor(repo, LIVE, "165891d")
        and not is_ancestor(repo, CANONICAL, "de48d6a")
        and not is_ancestor(repo, CANONICAL, "165891d"),
        "de48d6a + 165891d are ancestors of 6d67140 and not of 1938c31",
    )

    # 6. canonical follow-up observation (dc3bcd3): partial only, still no V4.
    followup_present = exists(repo, FOLLOWUP, "app/services/model_calls.py")
    followup_parent = (
        git(repo, "rev-list", "--parents", "-n1", followup_full).split()[1]
        if followup_present
        else None
    )
    followup_files = (
        git(repo, "diff", "--name-only", canonical_full, followup_full).splitlines()
        if followup_present
        else []
    )
    check(
        "canonical_followup_is_partial_only",
        followup_present
        and followup_parent == canonical_full
        and "app/services/model_calls.py" in followup_files
        and "app/domain/v4.py" not in followup_files
        and not exists(repo, FOLLOWUP, "app/domain/v4.py"),
        f"{FOLLOWUP} parent={followup_parent}, changed={len(followup_files)} "
        "files, no app/domain/v4.py",
    )
    check(
        "followup_differs_from_live",
        followup_present
        and git(repo, "rev-list", "--left-right", "--count",
                f"{FOLLOWUP}...{LIVE}").split() == ["1", "66"],
        "dc3bcd3 and 6d67140 are siblings (1 / 66), not interchangeable",
    )

    blobs = {
        "model_calls.py@6d67140": git(repo, "rev-parse", f"{LIVE}:app/services/model_calls.py").strip(),
        "controller_api.py@6d67140": git(repo, "rev-parse", f"{LIVE}:app/controller_api.py").strip(),
        "v4.py@6d67140": git(repo, "rev-parse", f"{LIVE}:app/domain/v4.py").strip(),
        "model_calls.py@1938c31": git(repo, "rev-parse", f"{CANONICAL}:app/services/model_calls.py").strip(),
    }

    head = git(repo, "show", "-s", "--format=%H%n%ad%n%s", "--date=iso", LIVE).splitlines()
    report = {
        "live": {"rev": head[0], "date": head[1], "subject": head[2]},
        "canonical": {
            "rev": canonical_full,
            "subject": git(repo, "show", "-s", "--format=%s", CANONICAL).strip(),
        },
        "followup": {
            "rev": followup_full if followup_present else None,
            "parent": followup_parent,
            "changed_files": followup_files,
        },
        "topology": {
            "merge_base": merge_base,
            "canonical_ahead": int(left),
            "live_ahead": int(right),
            "live_parents": live_parents[1:],
            "merge_41ff540_parents": merge_parents[1:],
        },
        "blobs": blobs,
        "checks": checks,
        "summary": {
            "passed": sum(1 for c in checks if c["ok"]),
            "failed": sum(1 for c in checks if not c["ok"]),
        },
    }

    for c in checks:
        print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['check']}")
        print(f"       {c['detail']}")
    print(
        f"\nsummary: {report['summary']['passed']} passed, "
        f"{report['summary']['failed']} failed"
    )

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"json: {args.json}")

    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
