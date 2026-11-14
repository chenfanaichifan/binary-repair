#!/usr/bin/env python3
"""Validate committed CI/release evidence claims (offline; online opt-in).

Two schema generations are understood:

* **legacy** ``claims.latest_verified_ci`` (run_id/head_sha/branch/conclusion)
  remains accepted for pre-phase-6 commits and historical evidence;
* **v2** ``claims.ci_evidence`` separates the hosted GitHub CI run, the
  self-hosted nightly Lima gate (which may be ``not_run`` with an owner
  sign-off) and the local frozen-tree gate.  A hosted run may target the gated
  SHA directly or an ancestor, provided the only delta is an explicit
  ``docs_only_delta`` whose paths are limited to claims/release/evidence docs.

The offline mode is deterministic and runs in CI.  ``--online`` verifies the
hosted GitHub Actions run against the public API (no token is required for
public repositories; rate limits surface as a typed failure).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
RUN_RE = re.compile(r"https://github\.com/([^/\s]+)/([^/\s]+)/actions/runs/(\d+)")
SHA_RE = re.compile(r"[0-9a-f]{7,40}")
DIGEST_RE = re.compile(r"[0-9a-f]{64}")
ALLOWED_DELTA_PREFIXES = (
    "docs/status/claims.json",
    "docs/release-",
    "docs/acceptance/ci-",
    "artifacts/release-gate-",
)


def _load(claims_path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        claims = json.loads(claims_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{claims_path}: {type(exc).__name__}: {exc}"
    if not isinstance(claims, dict):
        return None, f"{claims_path}: claims.json is not an object"
    return claims, ""


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _check_delta(delta: dict[str, Any], gated_sha: str, head_sha: str) -> list[str]:
    violations: list[str] = []
    if not delta:
        return [
            "ci_evidence.hosted_ci.docs_only_delta is required when the hosted "
            "run SHA differs from the gated SHA"
        ]
    from_sha = str(delta.get("from_sha") or "")
    to_sha = str(delta.get("to_sha") or "")
    if from_sha != gated_sha:
        violations.append(
            "docs_only_delta.from_sha must equal ci_evidence.gated_sha")
    if to_sha != head_sha:
        violations.append("docs_only_delta.to_sha must equal hosted head_sha")
    paths = delta.get("paths")
    if not isinstance(paths, list) or not paths:
        violations.append("docs_only_delta.paths must be a non-empty list")
        return violations
    for path in paths:
        value = str(path)
        if not any(value.startswith(prefix) for prefix in ALLOWED_DELTA_PREFIXES):
            violations.append(
                f"docs_only_delta path is not evidence/docs-only: {value!r}")
    return violations


def _validate_v2(claims: dict[str, Any], root: Path) -> tuple[list[str], dict[str, Any]]:
    violations: list[str] = []
    evidence = _as_dict(claims.get("ci_evidence"))
    detail: dict[str, Any] = {"schema": 2}
    if evidence.get("schema_version") != 2:
        violations.append("ci_evidence.schema_version is not 2")
    gated_sha = str(evidence.get("gated_sha") or "")
    if not SHA_RE.fullmatch(gated_sha):
        violations.append("ci_evidence.gated_sha is not a commit SHA")
    hosted = _as_dict(evidence.get("hosted_ci"))
    detail["hosted_run_id"] = hosted.get("run_id")
    for field in ("workflow", "run_id", "run_url", "head_sha", "conclusion",
                  "scope"):
        if not hosted.get(field):
            violations.append(f"ci_evidence.hosted_ci.{field} is missing")
    run_url = str(hosted.get("run_url") or "")
    if run_url and not RUN_RE.fullmatch(run_url):
        violations.append(
            "ci_evidence.hosted_ci.run_url is not a GitHub Actions run URL")
    if hosted.get("conclusion") not in (None, "success"):
        violations.append(
            "ci_evidence.hosted_ci.conclusion is not success: "
            f"{hosted.get('conclusion')!r}")
    head_sha = str(hosted.get("head_sha") or "")
    if not SHA_RE.fullmatch(head_sha):
        violations.append("ci_evidence.hosted_ci.head_sha is not a commit SHA")
    if head_sha and gated_sha and head_sha != gated_sha:
        violations.extend(_check_delta(
            _as_dict(hosted.get("docs_only_delta")), gated_sha, head_sha))
    elif head_sha and gated_sha and head_sha == gated_sha:
        delta = _as_dict(hosted.get("docs_only_delta"))
        if delta:
            violations.extend(_check_delta(delta, gated_sha, head_sha))
    self_hosted = _as_dict(evidence.get("self_hosted_nightly"))
    detail["self_hosted_status"] = self_hosted.get("status")
    if self_hosted.get("status") not in {"not_run", "success"}:
        violations.append(
            "ci_evidence.self_hosted_nightly.status must be not_run or success")
    if self_hosted.get("status") == "not_run":
        if not str(self_hosted.get("reason") or "").strip():
            violations.append(
                "ci_evidence.self_hosted_nightly.reason is empty for not_run")
        signoff = str(self_hosted.get("signoff") or "")
        if not signoff:
            violations.append(
                "ci_evidence.self_hosted_nightly.signoff is missing for not_run")
        elif not (root / signoff).is_file():
            violations.append(
                "ci_evidence.self_hosted_nightly.signoff file is missing: "
                f"{signoff}")
    elif self_hosted.get("status") == "success":
        if not RUN_RE.fullmatch(str(self_hosted.get("run_url") or "")):
            violations.append(
                "self_hosted_nightly run_url missing for status=success")
    local = _as_dict(evidence.get("local_gate"))
    detail["local_gate_status"] = local.get("status")
    if local.get("status") != "passed":
        violations.append("ci_evidence.local_gate.status must be passed")
    local_sha = str(local.get("frozen_sha") or "")
    if local_sha != gated_sha:
        violations.append(
            "ci_evidence.local_gate.frozen_sha must equal gated_sha")
    gate_sha = str(local.get("gate_evidence_sha256") or "")
    evidence_branch = str(local.get("evidence_branch") or "")
    evidence_tag = str(local.get("evidence_tag") or "")
    if gate_sha:
        if not DIGEST_RE.fullmatch(gate_sha):
            violations.append(
                "ci_evidence.local_gate.gate_evidence_sha256 is not a sha256")
    elif not (evidence_branch and evidence_tag):
        violations.append(
            "ci_evidence.local_gate needs gate_evidence_sha256 or "
            "evidence_branch+evidence_tag (the gate bundle is written after "
            "the claims commit)")
    legacy = _as_dict(claims.get("latest_verified_ci"))
    if legacy:
        if str(legacy.get("head_sha") or "") != head_sha:
            violations.append(
                "latest_verified_ci.head_sha must mirror hosted_ci.head_sha")
        if int(legacy.get("run_id") or 0) != int(hosted.get("run_id") or 0):
            violations.append(
                "latest_verified_ci.run_id must mirror hosted_ci.run_id")
        if legacy.get("conclusion") != "success":
            violations.append("latest_verified_ci.conclusion is not success")
    return violations, detail


def _offline(claims_path: Path, root: Path) -> int:
    claims, error = _load(claims_path)
    if error or claims is None:
        print(f"FAIL {error}")
        return 1
    if "ci_evidence" in claims:
        violations, detail = _validate_v2(claims, root)
        if violations:
            print("FAIL ci_evidence v2 violations:")
            for violation in violations:
                print(f"  - {violation}")
            return 1
        hosted = _as_dict(_as_dict(claims.get("ci_evidence")).get("hosted_ci"))
        print(
            "claims=ok schema=v2 hosted_run_id={run} hosted_run_url={url} "
            "self_hosted={sh} local_gate={local} cited_run_urls={cited}".format(
                run=detail.get("hosted_run_id"),
                url=hosted.get("run_url"),
                sh=detail.get("self_hosted_status"),
                local=detail.get("local_gate_status"),
                cited=_cited_run_urls(),
            )
        )
        return 0
    # Legacy schema (pre-phase-6 commits): keep validating the historical run.
    latest = claims.get("latest_verified_ci") or {}
    required = {"run_id", "head_sha", "branch", "conclusion"}
    missing = sorted(required - set(latest))
    if missing:
        print("FAIL claims missing", missing)
        return 1
    if not SHA_RE.fullmatch(str(latest["head_sha"])):
        print("FAIL head_sha is not a hex commit")
        return 1
    if latest["conclusion"] != "success":
        print("FAIL latest_verified_ci is not success")
        return 1
    print(f"claims=ok schema=legacy cited_run_urls={_cited_run_urls()}")
    return 0


def _cited_run_urls() -> int:
    cited = 0
    for path in list((ROOT / "docs").rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        cited += len(RUN_RE.findall(text))
    return cited


def _fetch_run(run_id: int) -> dict[str, Any] | None:
    url = (
        "https://api.github.com/repos/chenfanaichifan/binary-repair/actions/"
        f"runs/{int(run_id)}"
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": "binary-repair-evidence"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except Exception as exc:  # noqa: BLE001 - online mode reports typed failure
        print(f"FAIL online evidence unavailable: {type(exc).__name__}: {exc}")
        return None
    return payload if isinstance(payload, dict) else None


def _online(claims_path: Path, root: Path) -> int:
    claims, error = _load(claims_path)
    if error or claims is None:
        print(f"FAIL {error}")
        return 1
    evidence = _as_dict(claims.get("ci_evidence"))
    hosted = _as_dict(evidence.get("hosted_ci"))
    if evidence:
        run_id = int(hosted.get("run_id") or 0)
        expected_head = str(hosted.get("head_sha") or "")
        expected_conclusion = str(hosted.get("conclusion") or "")
    else:
        legacy = claims.get("latest_verified_ci") or {}
        run_id = int(legacy.get("run_id") or 0)
        expected_head = str(legacy.get("head_sha") or "")
        expected_conclusion = str(legacy.get("conclusion") or "")
    if not run_id:
        print("FAIL online mode needs a run id (hosted_ci.run_id)")
        return 1
    data = _fetch_run(run_id)
    if data is None:
        return 2
    actual_conclusion = data.get("conclusion")
    actual_head = str(data.get("head_sha") or "")
    ok = (
        actual_conclusion == expected_conclusion
        and actual_head.startswith(expected_head)
    )
    print(
        f"run={data.get('id')} sha={actual_head[:7]} "
        f"conclusion={actual_conclusion} -> {'ok' if ok else 'MISMATCH'}"
    )
    return 0 if ok else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate committed CI/release evidence claims.")
    parser.add_argument("--online", action="store_true",
                        help="verify the hosted run against the GitHub API")
    parser.add_argument(
        "--claims", type=Path,
        default=ROOT / "docs" / "status" / "claims.json",
        help="claims.json path (default: repository claims)",
    )
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root for signoff file checks")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return (_online(args.claims, args.root) if args.online
            else _offline(args.claims, args.root))


if __name__ == "__main__":
    raise SystemExit(main())
