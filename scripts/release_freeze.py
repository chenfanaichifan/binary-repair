#!/usr/bin/env python3
"""Freeze a release tree and record a self-contained gate evidence bundle.

The release gate itself (``scripts/release_gate.py``) proves that the gated git
tree is the frozen SHA and produces a provenance-rich JSON.  This wrapper adds
the operational guarantees around that run:

* the worktree must be clean and ``HEAD`` must equal the requested ``--sha``;
* by default ``origin/workbench-v3`` must also point at the same SHA (a release
  must be verified against the published mainline, not a side branch);
* the gate is invoked with ``--release-sha`` so a mismatched or dirty tree fails
  fast instead of burning the suite;
* the remote mainline is re-checked *after* the gate, so a concurrent push
  during the run invalidates the evidence and exits non-zero;
* a reviewable bundle is written: ``gate.json`` (gate evidence), ``freeze.json``
  (tree/mainline pins and the exact command), ``README.md`` and ``SHA256SUMS``.

It never rewrites the repository and never claims a GitHub Actions run: CI runs
must pass ``--expected-mainline ignore --offline`` and their own ``github.sha``
as ``--sha`` (the CI workflow does exactly that).  The bundle distinguishes
local frozen-tree evidence from CI evidence explicitly.

Exit codes: ``0`` frozen evidence recorded, ``1`` any tree/gate/mainline
violation (partial evidence is still written for diagnosis), ``2`` usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
GATE = "scripts/release_gate.py"
DEFAULT_GATE_JSON = "gate.json"
FREEZE_JSON = "freeze.json"
README = "README.md"
SHA256SUMS = "SHA256SUMS"


class RunResult:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


Runner = Callable[[Sequence[str], Path, float], RunResult]


def run_command(argv: Sequence[str], cwd: Path, timeout: float) -> RunResult:
    try:
        completed = subprocess.run(
            list(argv), cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(124, _text(exc.stdout), f"timeout after {timeout:.0f}s")
    except OSError as exc:
        return RunResult(127, "", f"{type(exc).__name__}: {exc}")
    return RunResult(completed.returncode, completed.stdout or "",
                     completed.stderr or "")


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _github_env() -> dict[str, Any] | None:
    """Return the GitHub Actions identity when this wrapper runs in CI."""
    if os.environ.get("GITHUB_ACTIONS", "").lower() != "true":
        return None
    return {
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "workflow": os.environ.get("GITHUB_WORKFLOW"),
        "job": os.environ.get("GITHUB_JOB"),
        "sha": os.environ.get("GITHUB_SHA"),
        "repository": os.environ.get("GITHUB_REPOSITORY"),
        "server_url": os.environ.get("GITHUB_SERVER_URL"),
        "event_name": os.environ.get("GITHUB_EVENT_NAME"),
    }


def _git(root: Path, run: Runner, *args: str) -> str | None:
    result = run(["git", *args], root, 30.0)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_bundle(
    evidence_dir: Path,
    *,
    sha: str,
    mode: str,
    gate_command: Sequence[str],
    gate_payload: dict[str, Any] | None,
    gate_error: str,
    mainline_start: str | None,
    mainline_end: str | None,
    expected_mainline: str,
    tree_clean: bool,
    head_sha: str | None,
    gate_rc: int,
    tree_sha: str | None = None,
    branch: str | None = None,
    github: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write README/SHA256SUMS/freeze.json; returns the freeze payload."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    drift = bool(
        mainline_start and mainline_end and mainline_start != mainline_end
    )
    frozen_ok = (
        gate_rc == 0
        and bool(gate_payload)
        and gate_payload.get("ok") is True
        and gate_payload.get("frozen_sha") == sha
        and gate_payload.get("release_sha") == sha
        and not drift
        and (expected_mainline != "require" or mainline_start == sha)
    )
    freeze = {
        "schema_version": 1,
        "kind": "release_freeze",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": frozen_ok,
        "exit_code": 0 if frozen_ok else 1,
        "mode": mode,
        "requested_sha": sha,
        "head_sha": head_sha,
        "clean_tree": tree_clean,
        "expected_mainline": expected_mainline,
        "mainline_sha_start": mainline_start,
        "mainline_sha_end": mainline_end,
        "mainline_unchanged": not drift,
        "gate_command": list(gate_command),
        "gate_rc": gate_rc,
        "gate_error": gate_error,
        "tree_sha": tree_sha,
        "branch": branch,
        "gate_summary": {
            key: gate_payload.get(key)
            for key in (
                "ok", "mode", "frozen_sha", "release_sha", "branch",
                "clean_tree", "status_counts", "violations", "not_run",
                "tree_sha",
            )
        } if gate_payload else None,
        "runner": {
            "kind": "github-actions" if github else "local-frozen-tree",
            "github": github,
        },
        "evidence_scope": (
            "frozen-tree gate evidence: proves the gated git tree identity, the "
            "measured checks and the recorded artifact digests, plus provenance. "
            "When runner.kind is local-frozen-tree this is not a GitHub Actions "
            "run; a CI run is a separate claim recorded from its own artifact."
        ),
    }
    _write_json(evidence_dir / FREEZE_JSON, freeze)
    readme = [
        "# Release freeze evidence",
        "",
        f"- mode: `{mode}`",
        f"- requested sha: `{sha}`",
        f"- head sha: `{head_sha}`",
        f"- clean tree: `{tree_clean}`",
        f"- expected mainline policy: `{expected_mainline}`",
        f"- mainline at start: `{mainline_start}`",
        f"- mainline at end: `{mainline_end}`",
        f"- mainline unchanged: `{not drift}`",
        f"- gate rc: `{gate_rc}`",
        f"- gate ok: `{bool(gate_payload and gate_payload.get('ok'))}`",
        f"- runner kind: `{'github-actions' if github else 'local-frozen-tree'}`",
        (f"- GitHub run: `{github.get('run_id')}` workflow `{github.get('workflow')}` "
         f"job `{github.get('job')}` sha `{github.get('sha')}`" if github else
         "- GitHub run: not applicable (local frozen-tree evidence)"),
        f"- evidence scope: frozen-tree gate (not automatically a CI run)",
        "",
        "## Command",
        "",
        "```",
        " ".join(str(part) for part in gate_command),
        "```",
        "",
        "## Files",
        "",
        f"- `{DEFAULT_GATE_JSON}`: gate evidence with checks/provenance",
        f"- `{FREEZE_JSON}`: tree/mainline pins and the exact command",
        f"- `{SHA256SUMS}`: sha256 of the files above",
        "",
    ]
    (evidence_dir / README).write_text("\n".join(readme), encoding="utf-8")
    lines = []
    for name in (DEFAULT_GATE_JSON, FREEZE_JSON, README):
        path = evidence_dir / name
        digest = _sha256_file(path) if path.is_file() else None
        if digest:
            lines.append(f"{digest}  {name}")
    (evidence_dir / SHA256SUMS).write_text("\n".join(lines) + "\n",
                                           encoding="utf-8")
    return freeze


def freeze(
    *,
    sha: str | None = None,
    evidence_dir: Path | None = None,
    mode: str = "nightly",
    expected_mainline: str = "require",
    offline: bool = False,
    overwrite: bool = False,
    root: Path = ROOT,
    run: Runner = run_command,
) -> dict[str, Any]:
    """Freeze the tree at ``sha``, run the gate and write the evidence bundle."""
    if mode not in ("release", "nightly"):
        raise ValueError(f"unsupported mode: {mode!r}")
    if expected_mainline not in ("require", "ignore", "record"):
        raise ValueError(f"unsupported expected-mainline policy: {expected_mainline!r}")
    target_dir = evidence_dir or (root / "artifacts" / "release-gate-2026-11-14")
    if target_dir.exists() and any(target_dir.iterdir()) and not overwrite:
        raise ValueError(
            f"evidence directory is not empty: {target_dir} (pass --overwrite)"
        )
    head = _git(root, run, "rev-parse", "HEAD")
    clean = True
    status_out = _git(root, run, "status", "--porcelain") or ""
    clean = status_out == ""
    tree_sha = _git(root, run, "rev-parse", "HEAD^{tree}")
    branch = _git(root, run, "rev-parse", "--abbrev-ref", "HEAD")
    mainline_start = None
    if not offline:
        _git(root, run, "fetch", "origin", "workbench-v3")
        mainline_start = _git(root, run, "rev-parse", "origin/workbench-v3")
    if expected_mainline == "require" and not offline:
        if mainline_start != (sha or head):
            raise ValueError(
                "origin/workbench-v3 does not match the frozen SHA: "
                f"mainline={mainline_start} frozen={sha or head}; publish "
                "mainline first or pass --expected-mainline ignore for a "
                "branch-only release"
            )
    if sha and head != sha:
        raise ValueError(f"HEAD {head} does not match requested --sha {sha}")
    if not clean:
        raise ValueError(
            "worktree is dirty; commit or freeze before release "
            f"(status: {status_out.splitlines()[:5]})"
        )
    frozen_sha = sha or head or ""
    gate_json = target_dir / DEFAULT_GATE_JSON
    command = [
        sys.executable, GATE, f"--{mode}", "--release-sha", frozen_sha,
        "--json", "--evidence-out", str(gate_json),
    ]
    result = run(command, root, 7200.0)
    gate_payload: dict[str, Any] | None = None
    gate_error = ""
    try:
        start, end = result.stdout.find("{"), result.stdout.rfind("}")
        if start >= 0 and end > start:
            gate_payload = json.loads(result.stdout[start:end + 1])
        else:
            gate_error = "gate produced no JSON payload"
    except (json.JSONDecodeError, ValueError) as exc:
        gate_error = f"gate JSON unreadable: {type(exc).__name__}: {exc}"
    mainline_end = None
    if not offline:
        if mainline_start is not None:
            _git(root, run, "fetch", "origin", "workbench-v3")
        mainline_end = _git(root, run, "rev-parse", "origin/workbench-v3")
    freeze_payload = _write_bundle(
        target_dir,
        sha=frozen_sha,
        mode=mode,
        gate_command=command,
        gate_payload=gate_payload,
        gate_error=gate_error,
        mainline_start=mainline_start,
        mainline_end=mainline_end,
        expected_mainline=expected_mainline,
        tree_clean=clean,
        head_sha=head,
        gate_rc=result.returncode,
        tree_sha=tree_sha,
        branch=branch,
        github=_github_env(),
    )
    return freeze_payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze a release tree, run release_gate.py --release/--nightly "
            "with --release-sha, and write a gate evidence bundle."
        )
    )
    parser.add_argument("--sha", default=None,
                        help="frozen commit SHA (default: current HEAD)")
    parser.add_argument("--evidence-dir", type=Path, default=None,
                        help="evidence output directory "
                             "(default: artifacts/release-gate-2026-11-14)")
    parser.add_argument("--mode", choices=("release", "nightly"),
                        default="nightly")
    parser.add_argument(
        "--expected-mainline", choices=("require", "record", "ignore"),
        default="require",
        help="require: origin/workbench-v3 must equal the frozen SHA; "
             "record: record but do not enforce before the run; "
             "ignore: no fetch/mainline checks (CI/offline use only)",
    )
    parser.add_argument("--offline", action="store_true",
                        help="do not fetch/check origin/mainline (CI mode)")
    parser.add_argument("--overwrite", action="store_true",
                        help="allow writing into a non-empty evidence directory")
    parser.add_argument("--json", action="store_true",
                        help="print the freeze payload as JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload = freeze(
            sha=args.sha,
            evidence_dir=args.evidence_dir,
            mode=args.mode,
            expected_mainline=args.expected_mainline,
            offline=args.offline,
            overwrite=args.overwrite,
        )
    except ValueError as exc:
        print(f"release-freeze: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("release-freeze: interrupted", file=sys.stderr)
        return 130
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            "release-freeze: ok={ok} mode={mode} sha={sha} "
            "mainline_unchanged={unchanged} evidence={dir}".format(
                ok=payload.get("ok"), mode=payload.get("mode"),
                sha=payload.get("requested_sha"),
                unchanged=payload.get("mainline_unchanged"),
                dir=args.evidence_dir or "artifacts/release-gate-2026-11-14",
            )
        )
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
