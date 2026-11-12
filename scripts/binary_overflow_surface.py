#!/usr/bin/env python3
"""Read-only binary attack-surface inventory for overflow review.

This is deliberately not a vulnerability detector. It resolves imported
symbols with nm and reports overflow-relevant libc/API imports plus nearby
symbol names. Capacity/provenance still require DWARF, decompilation,
symbolic execution or runtime evidence.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

UNSAFE = {
    "strcpy": "CWE-121/122 unbounded copy",
    "strcat": "CWE-119/121/122 unbounded append",
    "sprintf": "CWE-120 unbounded format",
    "gets": "CWE-242 unbounded input",
    "memcpy": "length must be validated",
    "memmove": "length must be validated",
    "printf": "format string risk if data is used as format",
    "malloc": "allocation capacity must be tracked",
    "read": "length must be validated",
    "recv": "length must be validated",
    "strncpy": "may omit NUL; verify capacity",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    path = args.path.resolve()
    nm = subprocess.run(["nm", "-u", str(path)], text=True, capture_output=True, timeout=30)
    imports = []
    for line in nm.stdout.splitlines():
        token = line.strip().split()[-1] if line.strip() else ""
        token = token.lstrip("_")
        if token in UNSAFE and token not in [item["symbol"] for item in imports]:
            imports.append({"symbol": token, "risk": UNSAFE[token]})
    strings = subprocess.run(["strings", "-a", str(path)], text=True, capture_output=True, timeout=30)
    format_like = [s for s in strings.stdout.splitlines() if "%n" in s or "%s" in s][:20]
    payload = {
        "path": str(path),
        "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
        "imports": imports,
        "format_like_strings": format_like,
        "limits": [
            "Import surface only; no capacity, provenance or reachability proof.",
            "Stripped/static binaries may hide imports; decompilation and DWARF are still required.",
            "Do not call this a vulnerability verdict.",
        ],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
