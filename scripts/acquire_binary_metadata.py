#!/usr/bin/env python3
"""Acquire dataset *metadata* (not binaries) and write an audited summary.

BinPool: binpool_info.json contains CVE/CWE/function/binary-path metadata.
CveBinarySheet: cve-map/*.json contains CVE/component/function/patch metadata.
Pre-built binary archives are external (Zenodo/Kaggle/OneDrive) and are not
silently downloaded here because of size, access requirements and licensing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINPOOL_INFO = "https://raw.githubusercontent.com/SimaArasteh/binpool/main/binpool_info.json"
CVEBINARYSHEET_REPO = "https://github.com/xmoezzz/CveBinarySheet"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def summarize(binpool_info: Path, cve_map: Path) -> dict:
    bp = json.loads(binpool_info.read_text(encoding="utf-8")) if binpool_info.is_file() else {}
    bp_files = []
    bp_cwes = {}
    for cve, item in bp.items():
        if not isinstance(item, dict):
            continue
        bp_files.extend(item.get("binaries") or [])
        for cwe in item.get("cwes") or []:
            bp_cwes[cwe] = bp_cwes.get(cwe, 0) + 1
    entries = 0
    components = set()
    map_files = sorted(cve_map.glob("*.json")) if cve_map.is_dir() else []
    for path in map_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            for component, rows in data.items():
                components.add(component)
                if isinstance(rows, list):
                    entries += len(rows)
        elif isinstance(data, list):
            entries += len(data)
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "binpool": {
            "cves": len(bp),
            "binary_paths_claimed": len(bp_files),
            "unique_binary_paths": len(set(bp_files)),
            "cwe_counts": dict(sorted(bp_cwes.items(), key=lambda kv: (-kv[1], kv[0]))[:20]),
            "metadata_sha256": sha256(binpool_info) if binpool_info.is_file() else None,
            "source": "https://github.com/SimaArasteh/binpool",
            "binaries": "external Zenodo archive; not downloaded by this script",
        },
        "cvebinarysheet": {
            "cve_json_files": len(map_files),
            "entries": entries,
            "components": len(components),
            "source": "https://github.com/xmoezzz/CveBinarySheet",
            "binaries": "external Kaggle/OneDrive archives; not downloaded by this script",
        },
        "nvd": {
            "status": "not downloaded",
            "use": "CVE description/CVSS/CWE/CPE enrichment; fetch via NVD API or local cache",
        },
        "limits": [
            "Metadata counts are not evidence that a binary is vulnerable.",
            "Binaries must be obtained from the dataset's official archive and handled in an isolated guest.",
            "No execution, decompilation or model training was performed by this metadata script.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binpool-info", type=Path, default=Path("/tmp/binpool_meta/binpool_info.json"))
    parser.add_argument("--cve-map", type=Path, default=Path("/tmp/cvebinarysheet_meta/cve-map"))
    parser.add_argument("--out", type=Path, default=ROOT / "knowledge" / "binary_dataset_summary.json")
    args = parser.parse_args()
    summary = summarize(args.binpool_info, args.cve_map)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
