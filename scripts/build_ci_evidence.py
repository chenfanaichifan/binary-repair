#!/usr/bin/env python3
"""Assemble portable GitHub-hosted CI evidence for the release candidate.

The full release gate measures host-specific capability tiers (Linux/macOS
probes, Lima guest) and is therefore recorded on the frozen reference host by
``release_freeze.py``.  A GitHub-hosted runner cannot reproduce those
platform-specific measurements, so this job records the *portable* CI layer it
can prove:

* ``release_gate.py --pr`` (static coverage gate + measured claims diff +
  targeted pytest subset),
* the full non-browser pytest suite,
* the GitHub runner environment and the exact commands/inputs.

The resulting ``ci-evidence.json`` is uploaded as a workflow artifact.  It is a
genuine CI record with an explicit portable scope; it is not the self-hosted
Lima nightly and never claims to be one.

Exit codes: 0 evidence written and all inputs green; 1 an input failed or the
evidence could not be written; 2 usage error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1


def _sha256_file(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{path}: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, f"{path}: payload is not a JSON object"
    return payload, ""


def _junit_counts(path: Path) -> dict[str, Any]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in root.iter("testsuite"):
        for key in totals:
            try:
                totals[key] += int(suite.attrib.get(key, "0"))
            except ValueError:
                continue
    totals["available"] = True
    return totals


def _github() -> dict[str, Any] | None:
    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        return None
    return {
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "job": os.environ.get("GITHUB_JOB"),
        "sha": os.environ.get("GITHUB_SHA"),
        "ref": os.environ.get("GITHUB_REF"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "server_url": os.environ.get("GITHUB_SERVER_URL"),
    }


def build_evidence(
    *,
    pr_gate: dict[str, Any],
    pytest_counts: dict[str, Any],
    pr_gate_path: Path,
    pytest_junit_path: Path,
    command: Sequence[str] | None = None,
) -> dict[str, Any]:
    pr_ok = pr_gate.get("ok") is True
    pytest_ok = (
        pytest_counts.get("available") is True
        and int(pytest_counts.get("failures", 0)) == 0
        and int(pytest_counts.get("errors", 0)) == 0
    )
    pr_checks = [
        {
            "id": str(check.get("id", "?")),
            "status": str(check.get("status", "?")),
            "required": bool(check.get("required", True)),
        }
        for check in (pr_gate.get("checks") or [])
        if isinstance(check, dict)
    ]
    github = _github()
    ok = bool(pr_ok and pytest_ok)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "ci_portable_evidence",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": ok,
        "scope": (
            "GitHub-hosted portable CI layer: PR gate (static coverage + claims "
            "diff + targeted pytest) and the full non-browser pytest suite. It "
            "does not reproduce host-specific capability measurements or the "
            "Lima nightly; those are recorded by the frozen-host release gate "
            "and the self-hosted nightly job remains separate/not-run."
        ),
        "github": github,
        "runner": {
            "kind": "github-actions" if github else "local",
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "kernel": platform.uname().release,
        },
        "invocation": {
            "argv": list(command or sys.argv),
            "cwd": str(ROOT),
        },
        "commands": {
            "pr_gate": "python scripts/release_gate.py --pr --json",
            "pytest": (
                "python -m pytest -q -p no:xdist --ignore=tests/e2e "
                "--junitxml=artifacts/release-gate-ci/pytest.xml"),
        },
        "pr_gate": {
            "ok": pr_ok,
            "mode": pr_gate.get("mode"),
            "branch": pr_gate.get("branch"),
            "checks": pr_checks,
            "violations": list(pr_gate.get("violations") or []),
            "input_sha256": _sha256_file(pr_gate_path),
        },
        "pytest": {
            "ok": pytest_ok,
            **pytest_counts,
            "junit_sha256": _sha256_file(pytest_junit_path),
        },
    }


def _write_bundle(out: Path, evidence: dict[str, Any]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    readme = out.parent / "README.md"
    readme.write_text(
        "# GitHub-hosted portable CI evidence\n\n"
        f"- gated SHA: `{(evidence.get('github') or {}).get('sha')}`\n"
        f"- run: `{(evidence.get('github') or {}).get('run_id')}` "
        f"attempt `{(evidence.get('github') or {}).get('run_attempt')}`\n"
        f"- overall: `{'passed' if evidence['ok'] else 'failed'}`\n"
        f"- scope: {evidence['scope']}\n",
        encoding="utf-8",
    )
    sums = []
    for name in ("ci-evidence.json", "README.md", "pr-gate.json", "pytest.xml"):
        path = out.parent / name
        digest = _sha256_file(path)
        if digest:
            sums.append(f"{digest}  {name}")
    (out.parent / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assemble portable GitHub-hosted CI evidence.")
    parser.add_argument("--out", type=Path,
                        default=Path("artifacts/release-gate-ci/ci-evidence.json"))
    parser.add_argument("--pr-json", type=Path,
                        default=Path("artifacts/release-gate-ci/pr-gate.json"))
    parser.add_argument("--pytest-junit", type=Path,
                        default=Path("artifacts/release-gate-ci/pytest.xml"))
    parser.add_argument("--json", action="store_true",
                        help="print the evidence payload")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    pr_gate, error = _load_json(args.pr_json)
    if error or pr_gate is None:
        print(f"build-ci-evidence: {error}", file=sys.stderr)
        return 2
    counts = _junit_counts(args.pytest_junit)
    evidence = build_evidence(
        pr_gate=pr_gate,
        pytest_counts=counts,
        pr_gate_path=args.pr_json,
        pytest_junit_path=args.pytest_junit,
    )
    try:
        _write_bundle(args.out, evidence)
    except OSError as exc:
        print(f"build-ci-evidence: write failed: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(evidence, indent=2, sort_keys=True))
    else:
        print(
            "ci-evidence: {status} pr={pr} pytest={pytest} ".format(
                status="PASS" if evidence["ok"] else "FAIL",
                pr="passed" if evidence["pr_gate"]["ok"] else "failed",
                pytest=(
                    f"{counts.get('tests', 0)} tests/"
                    f"{counts.get('failures', 0)} failures"),
            )
        )
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
