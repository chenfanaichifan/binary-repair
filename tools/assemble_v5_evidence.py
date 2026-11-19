#!/usr/bin/env python3
"""Assemble a formal V5 clean-snapshot replay record (2026-11-19 specification).

Inputs are measured evidence, never verdicts:

* ``--restore-receipt``: the host-captured snapshot revert receipt (snapshot name
  and uid, vmsn sha256, vmrun command and exit code, power states, boot_id);
* ``--observed-manifest``: the broker's per-case behaviour manifest for the
  frozen candidate (case id, exit code, stdout/stderr hashes);
* ``--tests``: the approved test manifest directory (valid.json, optional
  invalid.json); expected hashes are recomputed from it;
* ``--replay``: the independent byte-replay envelope (build reproducibility);
* ``--review``: the independent reviewer row;
* ``--environment``: measured guest/tool environment fields.

The tool only assembles and validates; it never executes the candidate. Missing
or inconsistent evidence makes it exit non-zero instead of writing a pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.domain.v5 import (  # noqa: E402
    V5EvidenceError,
    manifest_files,
    manifest_sha256,
    validate_v5_evidence,
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path} is not a JSON object")
    return data


def _approved_cases(tests_dir: Path) -> dict[str, dict]:
    approved: dict[str, dict] = {}
    for name in ("valid.json", "invalid.json"):
        path = tests_dir / name
        if not path.is_file():
            continue
        payload = _load(path)
        for case in payload.get("tests") or []:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str):
                continue
            expected = case.get("expected")
            if not isinstance(expected, dict):
                continue
            approved[case["id"]] = {
                "return_code": int(expected.get("return_code", 0)),
                "stdout_sha256": hashlib.sha256(
                    str(expected.get("stdout", "")).encode("utf-8")
                ).hexdigest(),
                "stderr_sha256": hashlib.sha256(
                    str(expected.get("stderr", "")).encode("utf-8")
                ).hexdigest(),
            }
    if not approved:
        raise SystemExit(f"no approved test cases in {tests_dir}")
    return approved


def _observed_cases(manifest: dict) -> dict[str, dict]:
    observed: dict[str, dict] = {}
    for case in manifest.get("cases") or []:
        if not isinstance(case, dict):
            continue
        case_id = case.get("id") or case.get("case_id")
        if not isinstance(case_id, str):
            continue
        observed[case_id] = {
            "return_code": int(case.get("exit_code", case.get("return_code", 0))),
            "stdout_sha256": str(case.get("stdout_sha256", "")),
            "stderr_sha256": str(case.get("stderr_sha256", "")),
        }
    return observed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools/assemble_v5_evidence.py")
    parser.add_argument("--restore-receipt", type=Path, required=True)
    parser.add_argument("--observed-manifest", type=Path, required=True)
    parser.add_argument("--tests", type=Path, required=True)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--original-sha256", required=True)
    parser.add_argument("--contract-canonical-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    receipt = _load(args.restore_receipt)
    manifest = _load(args.observed_manifest)
    replay = _load(args.replay)
    review = _load(args.review)
    environment = _load(args.environment)
    approved = _approved_cases(args.tests)
    observed = _observed_cases(manifest)

    missing = sorted(set(approved) - set(observed))
    extra = sorted(set(observed) - set(approved))
    if missing or extra:
        raise SystemExit(
            f"observed cases do not match the approved manifest (missing={missing}, extra={extra})"
        )
    behavior = []
    for case_id, expected in approved.items():
        found = observed[case_id]
        ok = (
            found["return_code"] == expected["return_code"]
            and found["stdout_sha256"] == expected["stdout_sha256"]
            and found["stderr_sha256"] == expected["stderr_sha256"]
        )
        behavior.append(
            {
                "case_id": case_id,
                "expected_return_code": expected["return_code"],
                "expected_stdout_sha256": expected["stdout_sha256"],
                "expected_stderr_sha256": expected["stderr_sha256"],
                "observed_return_code": found["return_code"],
                "observed_stdout_sha256": found["stdout_sha256"],
                "observed_stderr_sha256": found["stderr_sha256"],
                "ok": ok,
            }
        )

    isolation = manifest.get("isolation") or manifest.get("environment", {}).get("isolation") or {}
    payload = {
        "schema_version": 1,
        "gate": "V5",
        "kind": "reproducibility",
        "scope": "replay",
        "state": "passed",
        "candidate_sha256": args.candidate_sha256,
        "original_sha256": args.original_sha256,
        "test_manifest_sha256": manifest_sha256(manifest_files(args.tests)),
        "contract_canonical_sha256": args.contract_canonical_sha256,
        "environment": environment,
        "restore_receipt": receipt,
        "behavior": behavior,
        "isolation": isolation,
        "replay": replay,
        "review": review,
        "not_claimed": [
            "a binary-level proof is not claimed",
            "one approved clean snapshot and one route were replayed; this is not a general guarantee",
        ],
    }
    try:
        evidence = validate_v5_evidence(
            payload,
            candidate_sha256=args.candidate_sha256,
            original_sha256=args.original_sha256,
            test_manifest_sha256=payload["test_manifest_sha256"],
        )
    except V5EvidenceError as exc:
        raise SystemExit(f"formal V5 evidence rejected: {exc}") from exc

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "out": str(args.out),
                "out_sha256": _sha256_file(args.out),
                "candidate_sha256": evidence.candidate_sha256,
                "test_manifest_sha256": evidence.test_manifest_sha256,
                "snapshot": evidence.restore_receipt.snapshot_name,
                "boot_id": evidence.restore_receipt.boot_id,
                "cases": len(evidence.behavior),
                "reviewed_by": evidence.review.reviewed_by,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
