#!/usr/bin/env python3
"""Classify one C file with the runtime candidate memory (no code execution)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.overflow_ai import memory


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    code = args.path.read_text(encoding="utf-8")
    print(json.dumps(memory().classify(code), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
