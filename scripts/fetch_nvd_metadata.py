#!/usr/bin/env python3
"""Fetch and summarize one CVE from the NVD API 2.0 (no API key required)."""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cve")
    parser.add_argument("--out", type=Path, default=Path("var/datasets/nvd"))
    args = parser.parse_args()
    url = "https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=" + urllib.parse.quote(args.cve)
    req = urllib.request.Request(url, headers={"User-Agent": "BinaryRepair-local-metadata/1.0"})
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = json.load(response)
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / f"{args.cve}.json"
    target.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    vulns = raw.get("vulnerabilities") or []
    cve = (vulns[0].get("cve") if vulns else {}) or {}
    metrics = cve.get("metrics") or {}
    summary = {
        "cve": cve.get("id"),
        "published": cve.get("published"),
        "status": cve.get("vulnStatus"),
        "descriptions": [d.get("value") for d in cve.get("descriptions") or [] if d.get("lang") == "en"],
        "cwes": [d.get("value") for w in cve.get("weaknesses") or [] for d in w.get("description") or []],
        "cvss": {key: value for key, value in metrics.items() if isinstance(value, list)},
        "cache": str(target),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
