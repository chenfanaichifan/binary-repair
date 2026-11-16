#!/usr/bin/env python3
"""D05: attribute hidden no-candidate outcomes to pipeline stages.

Runs the private Phase-8C hidden lane with stage diagnostics enabled and writes:

* ``artifacts/phase8d-hidden-attribution-2026-11-17/aggregate.json`` -- public,
  counts-only stage/reason distributions (no hidden ids, paths, bytes or raw
  report strings);
* ``artifacts/phase8d-hidden-attribution-2026-11-17/private/stage-attribution.json``
  -- private per-sample details, retained under a git-ignored private directory;
* a public README and ``SHA256SUMS`` covering only the public aggregate/README.

The Phase-8C frozen results and hidden aggregate are never rewritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services import benchmark_runner  # noqa: E402

PUBLIC_DIR = Path("artifacts/phase8d-hidden-attribution-2026-11-17")
PUBLIC_AGGREGATE = PUBLIC_DIR / "aggregate.json"
PUBLIC_README = PUBLIC_DIR / "README.md"
PUBLIC_SUMS = PUBLIC_DIR / "SHA256SUMS"
PRIVATE_REPORT = PUBLIC_DIR / "private" / "stage-attribution.json"
GENERATED_AT = "2026-11-17T00:00:00Z"
KIND = "phase8d_hidden_no_candidate_attribution"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _privacy_problems(payload: Any, path: str = "$") -> list[str]:
    """Reject per-sample ids, paths, bytes or raw report strings."""

    problems: list[str] = []
    forbidden = {
        "opaque_sample_id", "sample_id", "binary_path", "oracle_path",
        "reference_fix_path", "binary_sha256", "candidate_sha256",
        "raw_report", "report",
    }
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key) in forbidden:
                problems.append(f"{path}.{key} is a private field")
            problems.extend(_privacy_problems(value, f"{path}.{key}"))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            problems.extend(_privacy_problems(value, f"{path}[{index}]"))
    elif isinstance(payload, str):
        if "/" in payload or "\\" in payload:
            problems.append(f"{path} contains a path separator")
        if len(payload) == 64 and all(ch in "0123456789abcdef" for ch in payload):
            # Commitment/public-manifest hashes are expected top-level fields;
            # an unrecognized opaque 64-hex string is not publishable here.
            if path not in {"$.commitment_sha256", "$.public_manifest_sha256",
                            "$.hidden_manifest_sha256"}:
                problems.append(f"{path} looks like an opaque digest")
    return problems


def _public_payload(hidden: dict[str, Any]) -> dict[str, Any]:
    stage = hidden.get("stage_attribution")
    if not isinstance(stage, dict):
        raise RuntimeError("hidden lane did not return stage attribution")
    return {
        "schema_version": 1,
        "kind": KIND,
        "generated_at": GENERATED_AT,
        "benchmark_id": "phase8d-hidden-attribution",
        "commitment_sha256": hidden.get("commitment_sha256"),
        "public_manifest_sha256": (hidden.get("hidden_aggregate_file") or {}).get(
            "public_manifest_sha256"),
        "hidden_manifest_sha256": hidden.get("hidden_manifest_sha256"),
        "sample_count": stage.get("sample_count"),
        "runtime_count": stage.get("runtime_count"),
        "analysis_only_count": stage.get("analysis_only_count"),
        "runtime_no_candidate_count": stage.get("runtime_no_candidate_count"),
        "runtime_candidate_count": stage.get("runtime_candidate_count"),
        "no_candidate_reason_counts": stage.get("no_candidate_reason_counts"),
        "first_blocking_stage_counts": stage.get("first_blocking_stage_counts"),
        "stage_status_counts": stage.get("stage_status_counts"),
        "analysis_only_no_candidate_expected": stage.get(
            "analysis_only_no_candidate_expected"),
        "limitations": [
            "public aggregate contains only counts and distribution; hidden sample "
            "ids, paths, bytes and raw reports are not published",
            "attribution is derived from deterministic engine reports; "
            "not_reached stages are not proof the stage would fail",
            "analysis-only samples are excluded from runtime no-candidate reasons "
            "and reported by count only",
        ],
    }


def _verify_public(public: Path) -> list[str]:
    problems: list[str] = []
    for path in (public / "aggregate.json", public / "README.md",
                 public / "SHA256SUMS"):
        if not path.is_file():
            problems.append(f"missing public file: {path.name}")
    if problems:
        return problems
    payload = json.loads((public / "aggregate.json").read_text(encoding="utf-8"))
    if payload.get("kind") != KIND:
        problems.append("aggregate kind mismatch")
    if payload.get("runtime_no_candidate_count") != sum(
        (payload.get("no_candidate_reason_counts") or {}).values()):
        problems.append("no_candidate_reason_counts do not sum to runtime_no_candidate_count")
    if payload.get("runtime_no_candidate_count") != sum(
        (payload.get("first_blocking_stage_counts") or {}).values()):
        problems.append("first_blocking_stage_counts do not sum to runtime_no_candidate_count")
    if payload.get("runtime_no_candidate_count", 0) + payload.get(
        "runtime_candidate_count", 0) != payload.get("runtime_count", 0):
        problems.append("runtime counts do not add up")
    for stage, counts in (payload.get("stage_status_counts") or {}).items():
        if sum(counts.values()) != payload.get("runtime_count"):
            problems.append(f"stage_status_counts[{stage}] does not sum to runtime_count")
    problems.extend(_privacy_problems(payload))
    listed: dict[str, str] = {}
    for line in (public / "SHA256SUMS").read_text(encoding="ascii").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        listed[name.strip()] = digest
    for name, digest in listed.items():
        path = public / name
        if not path.is_file() or _sha(path) != digest:
            problems.append(f"sha mismatch for {name}")
    return problems


def _write(args: argparse.Namespace) -> int:
    hidden_root = Path(args.hidden_root).expanduser()
    hidden = benchmark_runner.run_hidden_lane(
        hidden_root,
        root=ROOT,
        verifier_spec="none",
        collect_stage_attribution=True,
    )
    if not hidden.get("hidden_aggregate"):
        print(json.dumps({
            "ok": False,
            "error": "hidden lane did not run",
            "limitations": hidden.get("limitations"),
        }, indent=2))
        return 2
    public_dir = ROOT / PUBLIC_DIR
    public_dir.mkdir(parents=True, exist_ok=True)
    private_path = ROOT / PRIVATE_REPORT
    private_path.parent.mkdir(parents=True, exist_ok=True)
    (private_path.parent / ".gitignore").write_text("private/\n", encoding="ascii")
    private_payload = hidden.get("private_report") or {}
    private_path.write_text(
        json.dumps(private_payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    payload = _public_payload(hidden)
    (ROOT / PUBLIC_AGGREGATE).write_bytes(
        (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("ascii"))
    (ROOT / PUBLIC_README).write_text(
        "# Phase-8D hidden no-candidate stage attribution\n\n"
        f"- public manifest sha256: `{payload['public_manifest_sha256']}`\n"
        f"- hidden commitment sha256: `{payload['commitment_sha256']}`\n"
        f"- samples: {payload['sample_count']} = runtime {payload['runtime_count']}"
        f" + analysis-only {payload['analysis_only_count']}\n"
        f"- runtime no-candidate: {payload['runtime_no_candidate_count']}; "
        f"runtime candidates: {payload['runtime_candidate_count']}\n"
        f"- first blocking stages: `{payload['first_blocking_stage_counts']}`\n"
        f"- no-candidate reasons: `{payload['no_candidate_reason_counts']}`\n\n"
        "This public aggregate contains counts only. Per-sample diagnostics are "
        "retained under `private/` and are not published.\n",
        encoding="ascii",
    )
    lines = []
    for name in ("README.md", "aggregate.json"):
        path = public_dir / name
        lines.append(f"{_sha(path)}  {name}\n")
    (ROOT / PUBLIC_SUMS).write_text("".join(sorted(lines)), encoding="ascii")
    problems = _verify_public(public_dir)
    print(json.dumps({
        "ok": not problems,
        "public_dir": str(PUBLIC_DIR),
        "private_report": str(PRIVATE_REPORT),
        "problems": problems,
        "summary": {key: payload[key] for key in (
            "sample_count", "runtime_count", "analysis_only_count",
            "runtime_no_candidate_count", "runtime_candidate_count",
            "no_candidate_reason_counts", "first_blocking_stage_counts",
        )},
    }, indent=2, sort_keys=True))
    return 0 if not problems else 1


def _check() -> int:
    public_dir = ROOT / PUBLIC_DIR
    problems = _verify_public(public_dir)
    print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
    return 0 if not problems else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hidden-root",
                        default=os.environ.get("PHASE8C_HIDDEN_ROOT")
                        or str(Path.home() / ".binaryrepair/phase8c-hidden"))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        return _check()
    if args.write:
        return _write(args)
    print(json.dumps({"ok": False, "error": "choose --write or --check"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
