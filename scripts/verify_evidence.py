#!/usr/bin/env python3
"""Reproducible content-hash verification for fixtures and evidence bundles.

This checks SHA-256 *content* hashes (not git blob SHA-1 object ids):

* every fixture row in ``fixtures/PROVENANCE.json`` (path, size, sha256) and
  every source file recorded in ``source_sha256``;
* every ``SHA256SUMS`` entry in the committed evidence bundles.

Exit code is 0 only when every checked hash matches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLES = (
    "artifacts/binary-universal-v5-2026-11-13",
    "artifacts/ai-direct-binary-2026-11-13",
    "artifacts/ai-real-provider-2026-11-13",
    "artifacts/gate-blind-spots-2026-11-13",
    "artifacts/hard-case-benchmark-2026-11-13",
    "artifacts/fairness-ablation-2026-11-14",
    "artifacts/multi-model-probe-2026-11-14",
    "artifacts/ghidra-macos-2026-11-14",
    "artifacts/multi-model-matrix-2026-11-14",
    "artifacts/path-a-call-whitelist-2026-11-14",
    "artifacts/paradigm-a-loop-2026-11-14",
    "artifacts/paradigm-a-cwe121-2026-11-14",
    "artifacts/worktree-isolation-2026-11-14",
    "artifacts/siliconflow-key-2026-11-14",
    "artifacts/multi-model-matrix-intl-2026-11-14",
    "artifacts/symbol-resolver-2026-11-14",
    "artifacts/callee-context-2026-11-14",
    "artifacts/deepseek-matrix-2026-11-14",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_fixtures(root: Path = ROOT) -> dict[str, Any]:
    provenance = json.loads((root / "fixtures" / "PROVENANCE.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    failures = 0
    for fixture in provenance.get("fixtures", []):
        path = root / fixture["path"]
        observed = _sha256(path) if path.is_file() else None
        size = path.stat().st_size if path.is_file() else None
        ok = (
            isinstance(observed, str)
            and observed == fixture.get("sha256")
            and size == fixture.get("size")
        )
        failures += 0 if ok else 1
        rows.append({
            "name": fixture.get("name"),
            "path": fixture["path"],
            "ok": ok,
            "expected_sha256": fixture.get("sha256"),
            "observed_sha256": observed,
            "expected_size": fixture.get("size"),
            "observed_size": size,
        })
    source_rows: list[dict[str, Any]] = []
    for fixture in provenance.get("fixtures", []):
        for name, expected in (fixture.get("source_sha256") or {}).items():
            path = root / "fixtures" / "src" / name
            observed = _sha256(path) if path.is_file() else None
            ok = observed == expected
            failures += 0 if ok else 1
            source_rows.append({
                "name": name, "ok": ok,
                "expected_sha256": expected, "observed_sha256": observed,
            })
    return {
        "fixtures": rows,
        "sources": source_rows,
        "fixtures_ok": failures == 0,
        "fixture_count": len(rows),
        "source_count": len(source_rows),
    }


def verify_bundle(bundle: Path) -> dict[str, Any]:
    sums_path = bundle / "SHA256SUMS"
    rows: list[dict[str, Any]] = []
    failures = 0
    if not sums_path.is_file():
        return {"bundle": str(bundle.relative_to(ROOT)), "ok": False,
                "error": "SHA256SUMS missing", "files": []}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        name = name.strip()
        path = bundle / name
        observed = _sha256(path) if path.is_file() else None
        ok = observed == digest
        failures += 0 if ok else 1
        rows.append({"name": name, "ok": ok, "expected_sha256": digest,
                     "observed_sha256": observed})
    return {"bundle": str(bundle.relative_to(ROOT)), "ok": failures == 0,
            "file_count": len(rows), "files": rows}


def verify_all(root: Path = ROOT,
               bundles: list[str] | None = None) -> dict[str, Any]:
    fixture_result = verify_fixtures(root)
    bundle_results = [
        verify_bundle(root / relative) for relative in (bundles or DEFAULT_BUNDLES)
    ]
    ok = fixture_result["fixtures_ok"] and all(row["ok"] for row in bundle_results)
    return {
        "ok": ok,
        "hash_algorithm": "sha256",
        "note": "SHA-256 content hashes; git blob object ids are SHA-1 and are not compared",
        **fixture_result,
        "bundles": bundle_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--bundle", action="append", dest="bundles",
                        help="bundle directory relative to root (repeatable)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify_all(args.root, args.bundles)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"fixtures: {result['fixture_count']} rows, "
              f"sources: {result['source_count']} rows -> "
              f"{'PASS' if result['fixtures_ok'] else 'FAIL'}")
        for bundle in result["bundles"]:
            print(f"bundle {bundle['bundle']}: "
                  f"{bundle.get('file_count', 0)} files -> "
                  f"{'PASS' if bundle['ok'] else 'FAIL'}")
        print("overall:", "PASS" if result["ok"] else "FAIL")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
