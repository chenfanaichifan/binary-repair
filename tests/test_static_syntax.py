"""Repository-wide syntax gate (BOM-aware AST/JSON/JS/HTML/shell)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repository_syntax_is_clean():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_static_syntax.py")],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "failures=0" in result.stdout
