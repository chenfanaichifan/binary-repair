#!/usr/bin/env python3
"""Canonical name for the provisional handoff -> INTERFACE v1 converter.

The implementation is shared with scripts/normalize_handoff.py; this file is
the published entry point requested by M1/M3. It does not relax the checker.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from normalize_handoff import main

if __name__ == "__main__":
    raise SystemExit(main())
