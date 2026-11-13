#!/usr/bin/env python3
"""Syntax gates for tracked Python/JSON/JS/HTML/shell files.

This is intentionally dependency-free: CI must be able to run it before the
project dependencies are installed.  It tolerates a UTF-8 BOM (Python accepts
one at file start) and excludes vendored datasets and historical export kits.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git", ".venv", ".tmp", "__pycache__", ".pytest_cache", "node_modules",
    "datasets", "delivery", "var",
}
# Historical kits are evidence, not product code.  Their Python is still
# checked where tracked; this exclusion is only for very large exports.
EXCLUDED_PATH_PARTS = ("artifacts/p1-routea-kit-2026-11-07/kit",)


class _TemplateParser(HTMLParser):
    pass


def _iter_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT).as_posix()
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if any(part in rel for part in EXCLUDED_PATH_PARTS):
            continue
        yield path, rel


def _python_ok(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8-sig")
        ast.parse(text, filename=str(path))
        return None
    except (SyntaxError, UnicodeError) as exc:
        return f"{path.relative_to(ROOT)}: {type(exc).__name__}: {exc}"


def _json_ok(path: Path) -> str | None:
    try:
        json.loads(path.read_text(encoding="utf-8-sig"))
        return None
    except (json.JSONDecodeError, UnicodeError) as exc:
        return f"{path.relative_to(ROOT)}: JSONDecodeError: {exc}"


def _js_ok(path: Path) -> str | None:
    if shutil.which("node") is None:
        return None  # optional tool; Python/JSON/HTML/shell still enforced
    try:
        proc = subprocess.run(
            ["node", "--check", str(path)], capture_output=True, text=True,
            timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{path.relative_to(ROOT)}: node unavailable: {exc}"
    if proc.returncode != 0:
        return f"{path.relative_to(ROOT)}: node --check failed: {proc.stderr.strip()[:300]}"
    return None


def _html_ok(path: Path) -> str | None:
    try:
        _TemplateParser().feed(path.read_text(encoding="utf-8-sig"))
        return None
    except (HTMLParser, UnicodeError) as exc:
        return f"{path.relative_to(ROOT)}: HTML parser: {exc}"


def _shell_ok(path: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["bash", "-n", str(path)], capture_output=True, text=True,
            timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{path.relative_to(ROOT)}: bash unavailable: {exc}"
    if proc.returncode != 0:
        return f"{path.relative_to(ROOT)}: bash -n failed: {proc.stderr.strip()[:300]}"
    return None


def main() -> int:
    failures: list[str] = []
    checked = 0
    skipped_js = 0
    for path, rel in _iter_files():
        suffix = path.suffix.lower()
        result = None
        if suffix == ".py":
            result = _python_ok(path)
        elif suffix == ".json":
            result = _json_ok(path)
        elif suffix == ".js":
            if shutil.which("node") is None:
                skipped_js += 1
            else:
                result = _js_ok(path)
        elif suffix in {".html", ".htm"}:
            result = _html_ok(path)
        elif suffix in {".sh", ".bash"}:
            result = _shell_ok(path)
        if suffix in {".py", ".json", ".js", ".html", ".htm", ".sh", ".bash"}:
            checked += 1
        if result:
            failures.append(result)
    for item in failures:
        print("FAIL", item)
    print(f"checked={checked} failures={len(failures)} js_skipped={skipped_js}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
