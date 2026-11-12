#!/usr/bin/env python3
"""Probe local binary/dataset toolchain availability. Never installs anything."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    "ghidra", "analyzeHeadless", "radare2", "r2", "rizin", "gdb", "objdump",
    "readelf", "nm", "strings", "clang", "gcc", "docker", "ollama", "node",
    "npx", "mutagen", "raverse",
]
MODULES = ["angr", "capstone", "lief", "z3", "elftools", "tree_sitter", "r2pipe"]


def main() -> None:
    report = {
        "schema": 1,
        "commands": {name: (shutil.which(name) or None) for name in COMMANDS},
        "modules": {name: bool(importlib.util.find_spec(name)) for name in MODULES},
        "notes": [
            "Absence is reported as unavailable, not installed automatically.",
            "Ghidra/Mutagen/RAVERSE require separate installation and, for LLM calls, API/Ollama access.",
            "Binary execution must happen in an isolated guest, never the host.",
        ],
    }
    out = ROOT / "knowledge" / "binary_toolchain.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
