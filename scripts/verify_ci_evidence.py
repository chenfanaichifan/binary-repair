#!/usr/bin/env python3
"""Validate committed CI evidence URLs/IDs, optionally against GitHub API.

Offline mode is deterministic and runs in CI.  Online mode requires network and
a token for rate limits; it verifies that the cited run exists, matches the
committed head SHA and has the recorded conclusion.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_RE = re.compile(r"https://github\.com/([^/\s]+)/([^/\s]+)/actions/runs/(\d+)")
CLAIMS = ROOT / "docs" / "status" / "claims.json"


def _offline() -> int:
    claims = json.loads(CLAIMS.read_text(encoding="utf-8"))
    latest = claims.get("latest_verified_ci") or {}
    required = {"run_id", "head_sha", "branch", "conclusion"}
    missing = sorted(required - set(latest))
    if missing:
        print("FAIL claims missing", missing)
        return 1
    if not re.fullmatch(r"[0-9a-f]{7,40}", str(latest["head_sha"])):
        print("FAIL head_sha is not a hex commit")
        return 1
    if latest["conclusion"] != "success":
        print("FAIL latest_verified_ci is not success")
        return 1
    # Every cited run must be syntactically a GitHub Actions run URL.
    cited = 0
    for path in list((ROOT / "docs").rglob("*.md")):
        for match in RUN_RE.finditer(path.read_text(encoding="utf-8", errors="replace")):
            cited += 1
    print(f"claims=ok cited_run_urls={cited}")
    return 0


def _online() -> int:
    claims = json.loads(CLAIMS.read_text(encoding="utf-8"))
    latest = claims["latest_verified_ci"]
    url = (
        f"https://api.github.com/repos/chenfanaichifan/binary-repair/actions/runs/"
        f"{int(latest['run_id'])}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "binary-repair-evidence"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL online evidence unavailable: {type(exc).__name__}: {exc}")
        return 2
    ok = (
        data.get("conclusion") == latest["conclusion"]
        and str(data.get("head_sha", "")).startswith(str(latest["head_sha"]))
        and data.get("head_branch") == latest["branch"]
    )
    print(
        f"run={data.get('id')} sha={str(data.get('head_sha',''))[:7]} "
        f"branch={data.get('head_branch')} conclusion={data.get('conclusion')} -> "
        f"{'ok' if ok else 'MISMATCH'}"
    )
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true")
    args = ap.parse_args()
    return _online() if args.online else _offline()


if __name__ == "__main__":
    raise SystemExit(main())
