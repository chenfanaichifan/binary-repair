#!/usr/bin/env python3
"""Unified autonomous-repair audit entry point.

Runs the committed static audit checks as subprocesses (never the long dynamic
suites), aggregates their status, and optionally writes a deterministic evidence
bundle (``summary.json`` / ``README.md`` / ``SHA256SUMS``).

The orchestration is injectable: tests pass a fake ``run`` callable instead of
executing the real scripts, so the test suite never runs a 10-minute check.

Modes
-----

``static`` (fast, default for CI-like smoke):
    ``check_universe_methodology.py --check``,
    ``run_autonomous_reflection.py --check``,
    ``verify_coverage_gate.py --static-only --json``.

``full``:
    all static checks plus
    ``audit_acceptance_models.py --check``,
    ``discover_capability_gaps.py --check``,
    ``meta_audit.py --json``,
    ``build_provider_coverage.py --check``.

Exit codes (explicit and tested)
--------------------------------

* ``0`` every required check passed (``not_run`` checks are not evidence, so a
  required ``not_run`` prevents this);
* ``1`` at least one required check failed (contract/evidence violation);
* ``2`` no check failed, but one or more required scripts/inputs are missing
  (recorded as explicit ``not_run``; nothing is faked).

Options ``--json`` prints the structured summary; ``--evidence-out DIR`` writes
the bundle (created on demand).  Without ``--evidence-out`` the audit is
read-only and writes no repository files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = 1
DEFAULT_TIMEOUT = 600.0

SUMMARY_JSON = "summary.json"
README = "README.md"
SHA256SUMS = "SHA256SUMS"


class CommandResult:
    """Minimal subprocess result used by the injected runner."""

    def __init__(
        self,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        timed_out: bool = False,
    ) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out


Runner = Callable[[Sequence[str], Path, float], CommandResult]


def run_command(command: Sequence[str], cwd: Path, timeout: float) -> CommandResult:
    try:
        completed = subprocess.run(
            list(command), cwd=str(cwd), capture_output=True, text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return CommandResult(1, "", f"timed out after {timeout}s", timed_out=True)
    except OSError as exc:
        return CommandResult(1, "", f"{type(exc).__name__}: {exc}")
    return CommandResult(completed.returncode, completed.stdout or "", completed.stderr or "")


CHECK_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "universe-methodology",
        "script": "scripts/check_universe_methodology.py",
        "args": ("--check",),
        "required": True,
        "modes": ("static", "full"),
    },
    {
        "id": "autonomous-reflection",
        "script": "scripts/run_autonomous_reflection.py",
        "args": ("--check",),
        "required": True,
        "modes": ("static", "full"),
    },
    {
        "id": "coverage-gate-static",
        "script": "scripts/verify_coverage_gate.py",
        "args": ("--static-only", "--json"),
        "required": True,
        "modes": ("static", "full"),
    },
    {
        "id": "acceptance-model-audit",
        "script": "scripts/audit_acceptance_models.py",
        "args": ("--check",),
        "required": True,
        "modes": ("full",),
    },
    {
        "id": "capability-gap-discovery",
        "script": "scripts/discover_capability_gaps.py",
        "args": ("--check",),
        "required": True,
        "modes": ("full",),
    },
    {
        "id": "meta-audit",
        "script": "scripts/meta_audit.py",
        "args": ("--json",),
        "required": True,
        "modes": ("full",),
    },
    {
        "id": "provider-coverage",
        "script": "scripts/build_provider_coverage.py",
        "args": ("--check",),
        "required": True,
        "modes": ("full",),
    },
    # Phase-8A shadow checks: advisory evidence only.  A missing script is an
    # explicit not_run and a shadow result never satisfies a required check.
    {
        "id": "repair-readiness-audit",
        "script": "scripts/audit_repair_readiness.py",
        "args": ("--json",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "ground-truth-benchmark",
        "script": "scripts/build_ground_truth_benchmark.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "independent-verifier",
        "script": "scripts/verify_repair.py",
        "args": ("--selftest",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8b-baseline-audit",
        "script": "scripts/audit_phase8b_verifier_semantics.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8b-real-verification",
        "script": "scripts/check_phase8b_verification.py",
        "args": ("--json",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    # Phase-8C shadow checks: public-only evidence.  Hidden corpus and real
    # Lima runs stay reference-host evidence and never satisfy a required check.
    {
        "id": "phase8c-baseline-audit",
        "script": "scripts/audit_phase8c_readiness.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8c-ground-truth-v2",
        "script": "scripts/migrate_ground_truth_v2.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8c-public-corpus",
        "script": "scripts/build_phase8c_corpus.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8c-contamination",
        "script": "scripts/audit_phase8c_contamination.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8c-quality",
        "script": "scripts/audit_phase8c_quality.py",
        "args": ("--public-only", "--check"),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8c-benchmark-artifact",
        "script": "scripts/run_phase8c_benchmark.py",
        "args": ("--check-artifact",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8c-release-evidence",
        "script": "scripts/audit_phase8c_evidence.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    # Phase-8D shadow checks: additive discovery/acceptance/governance evidence.
    # Hidden raw material is never read by CI; the hidden-attribution check only
    # validates the committed anonymous aggregate.
    {
        "id": "phase8d-capability-universe",
        "script": "scripts/build_phase8d_capability_universe.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-gap-registry",
        "script": "scripts/build_phase8d_gap_registry.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-acceptance-2",
        "script": "scripts/audit_acceptance_2.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-heap-malloc-abi",
        "script": "scripts/analyze_phase8d_heap_malloc_abi.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-hidden-attribution",
        "script": "scripts/run_phase8d_hidden_attribution.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-external-knowledge",
        "script": "scripts/scan_external_knowledge.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-metamorphic",
        "script": "scripts/run_metamorphic_discovery.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-discovery-registry",
        "script": "scripts/build_phase8d_discovery_registry.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-hidden-isolation",
        "script": "scripts/audit_hidden_isolation.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-promotion",
        "script": "scripts/evaluate_promotion.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
    {
        "id": "phase8d-experiments",
        "script": "scripts/build_phase8d_experiment_bundle.py",
        "args": ("--check",),
        "required": False,
        "shadow": True,
        "modes": ("full",),
    },
)


def checks_for_mode(mode: str) -> list[dict[str, Any]]:
    return [spec for spec in CHECK_SPECS if mode in spec["modes"]]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tail(text: str, limit: int = 400) -> str:
    payload = (text or "").strip()
    return payload if len(payload) <= limit else "..." + payload[-limit:]


def _parse_json(text: str) -> dict[str, Any] | None:
    payload = (text or "").strip()
    if not payload:
        return None
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        start, end = payload.find("{"), payload.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(payload[start:end + 1])
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def run_check(
    spec: dict[str, Any],
    *,
    root: Path,
    run: Runner,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Run one check without raising; a missing script is explicit ``not_run``."""
    script = root / spec["script"]
    command = [sys.executable, str(script), *spec["args"]]
    check: dict[str, Any] = {
        "id": spec["id"],
        "script": spec["script"],
        "args": list(spec["args"]),
        "required": bool(spec.get("required", True)),
        "shadow": bool(spec.get("shadow", False)),
        "status": "not_run",
        "exit_code": None,
        "detail": "",
    }
    if not script.is_file():
        check["detail"] = f"script is not present in this checkout: {spec['script']}"
        return check
    result = run(command, root, timeout)
    parsed = _parse_json(result.stdout)
    check["exit_code"] = result.returncode
    if result.timed_out:
        check["status"] = "failed"
        check["detail"] = f"timed out: {_tail(result.stderr)}"
    elif result.returncode == 2:
        # A check that reports its own explicit not_run (missing input) is not a
        # failure; it is aggregated as not_run and the audit exits 2.
        check["status"] = "not_run"
        detail = _tail(result.stderr) or _tail(result.stdout) or "exit 2 (not_run)"
        check["detail"] = f"not_run (exit 2): {detail}"
    elif result.returncode != 0:
        check["status"] = "failed"
        detail = _tail(result.stderr) or _tail(result.stdout) or "non-zero exit"
        check["detail"] = f"exit {result.returncode}: {detail}"
    else:
        check["status"] = "passed"
        if parsed is not None:
            ok = parsed.get("ok")
            check["detail"] = (
                f"exit 0; report ok={ok}" if ok is not None
                else "exit 0; report ok=<missing>"
            )
            if ok is False:
                check["status"] = "failed"
                check["detail"] = "exit 0 but the report says ok=false"
        else:
            check["detail"] = "exit 0 (no JSON report parsed)"
    return check


def audit(
    *,
    mode: str,
    root: Path = ROOT,
    run: Runner = run_command,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Aggregate every check for ``mode``; deterministic and write-free."""
    mode = mode if mode in {"static", "full"} else "full"
    checks = [
        run_check(spec, root=root, run=run, timeout=timeout)
        for spec in checks_for_mode(mode)
    ]
    required_checks = [check for check in checks if check["required"]]
    shadow_checks = [check for check in checks if check.get("shadow") is True]
    failed = [check for check in required_checks if check["status"] == "failed"]
    not_run = [
        {"id": check["id"], "reason": check["detail"]}
        for check in required_checks
        if check["status"] == "not_run"
    ]
    if failed:
        exit_code = 1
    elif not_run:
        exit_code = 2
    else:
        exit_code = 0
    shadow_summary = {
        "count": len(shadow_checks),
        "passed": [check["id"] for check in shadow_checks if check["status"] == "passed"],
        "failed": [check["id"] for check in shadow_checks if check["status"] == "failed"],
        "not_run": [check["id"] for check in shadow_checks if check["status"] == "not_run"],
        "counted_as_pass": False,
        "affects_exit_code": False,
    }
    limitations = [
        "not_run checks are not evidence: a missing script/input never counts as a pass",
        "shadow checks are advisory: they never count as a pass and never change the exit code",
        "this orchestration is static only; it does not run dynamic/Lima suites",
        "the audit never promotes capability or claims verified repair",
    ]
    if not_run:
        limitations.append(
            "a required check/input is missing; see not_run entries for the exact reason"
        )
    if shadow_summary["not_run"]:
        limitations.append(
            "one or more shadow checks are not_run (explicit, not a pass): "
            + ", ".join(shadow_summary["not_run"])
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "autonomous_repair_audit",
        "mode": mode,
        "ok": exit_code == 0,
        "exit_code": exit_code,
        "checks": checks,
        "failed": [check["id"] for check in failed],
        "not_run": not_run,
        "shadow_summary": shadow_summary,
        "limitations": limitations,
    }


def render_readme(payload: dict[str, Any]) -> str:
    lines = [
        "# Autonomous repair audit (2026-11-16)",
        "",
        "Unified static audit entry (`scripts/autonomous_repair_audit.py`). It",
        "orchestrates the committed checks as subprocesses and aggregates their",
        "status. It does not run dynamic/Lima suites and does not claim a repair",
        "capability or a verified disposition.",
        "",
        f"- mode: `{payload['mode']}`",
        f"- ok: `{payload['ok']}`",
        f"- exit code: `{payload['exit_code']}` (0 pass, 1 failed check, 2 required not_run)",
        "",
        "## Checks",
        "",
        "| id | status | required | shadow | detail |",
        "|---|---|---|---|---|",
    ]
    for check in payload["checks"]:
        lines.append(
            f"| `{check['id']}` | {check['status']} | {check['required']} | "
            f"{check.get('shadow', False)} | {check['detail'].replace('|', '/')} |"
        )
    shadow = payload.get("shadow_summary") or {}
    lines.extend(["", "## Shadow checks", ""])
    lines.append(
        f"- count: {shadow.get('count', 0)}; passed: {shadow.get('passed', [])}; "
        f"failed: {shadow.get('failed', [])}; not_run: {shadow.get('not_run', [])}"
    )
    lines.append("- shadow results are advisory: never counted as a pass and never"
                 " change the exit code")
    lines.extend(["", "## Not run", ""])
    if payload["not_run"]:
        for item in payload["not_run"]:
            lines.append(f"- `{item['id']}`: {item['reason']}")
    else:
        lines.append("- none")
    lines.extend(["", "## Limitations", ""])
    for limitation in payload["limitations"]:
        lines.append(f"- {limitation}")
    lines.append("")
    return "\n".join(lines)


def write_evidence(out_dir: Path, payload: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / SUMMARY_JSON).write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (out_dir / README).write_text(render_readme(payload) + "\n", encoding="utf-8")
    lines = [
        f"{_sha256_file(out_dir / SUMMARY_JSON)}  {SUMMARY_JSON}",
        f"{_sha256_file(out_dir / README)}  {README}",
    ]
    (out_dir / SHA256SUMS).write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_evidence(out_dir: Path) -> list[str]:
    """Validate the bundle's SHA256SUMS and basic summary schema."""
    violations: list[str] = []
    sums_path = out_dir / SHA256SUMS
    summary_path = out_dir / SUMMARY_JSON
    if not sums_path.is_file():
        return [f"{sums_path}: missing"]
    for raw in sums_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            violations.append(f"SHA256SUMS: cannot parse {line!r}")
            continue
        digest, name = parts
        target = out_dir / name.lstrip("*")
        if not target.is_file():
            violations.append(f"SHA256SUMS references missing file {name}")
        elif _sha256_file(target) != digest:
            violations.append(f"SHA256SUMS mismatch for {name}")
    if not summary_path.is_file():
        return violations + [f"{summary_path}: missing"]
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return violations + [f"{summary_path}: invalid JSON: {exc}"]
    if payload.get("kind") != "autonomous_repair_audit":
        violations.append("summary.json kind must be 'autonomous_repair_audit'")
    checks = payload.get("checks")
    if not isinstance(checks, list) or not checks:
        violations.append("summary.json checks must be a non-empty list")
    return violations


def main(argv: list[str] | None = None, *, run: Runner = run_command) -> int:
    parser = argparse.ArgumentParser(
        description="Unified static audit for autonomous-repair evidence (offline).",
    )
    parser.add_argument("--mode", choices=("full", "static"), default="full",
                        help="full (all static checks) or static (fast subset)")
    parser.add_argument("--json", action="store_true", help="print the summary as JSON")
    parser.add_argument("--evidence-out", type=Path, default=None,
                        help="optional evidence directory; nothing is written without it")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root (default: this checkout; tests only)")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    payload = audit(mode=args.mode, root=root, run=run)
    if args.evidence_out is not None:
        out_dir = args.evidence_out.resolve()
        write_evidence(out_dir, payload)
        payload = {**payload, "evidence_dir": str(out_dir)}
        violations = verify_evidence(out_dir)
        if violations:
            payload = {**payload, "evidence_violations": violations}
            if args.json:
                print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
            else:
                for violation in violations:
                    print(f"FAIL evidence: {violation}")
            return 1
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print(
            "autonomous-repair-audit: mode={mode} result={result} checks={checks} "
            "failed={failed} not_run={not_run} exit={exit}".format(
                mode=payload["mode"],
                result="PASS" if payload["ok"] else "NOT_OK",
                checks=len(payload["checks"]),
                failed=len(payload["failed"]),
                not_run=len(payload["not_run"]),
                exit=payload["exit_code"],
            )
        )
        for check in payload["checks"]:
            print(f"  {check['status'].upper():<7} {check['id']}: {check['detail']}")
        for item in payload["not_run"]:
            print(f"  NOT_RUN {item['id']}: {item['reason']}")
    return int(payload["exit_code"])


if __name__ == "__main__":
    sys.exit(main())
