#!/usr/bin/env python3
"""Repository secret scanner (CI/pre-commit ready, offline, no network).

Mirrors the workspace handoff scanner: it reports masked locations only and
never prints a secret value. Previously-allowlisted values are stored as SHA-256
digests only.

Exit codes: 0 = clean, 1 = candidates found, 2 = usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

# Known/allowlisted values are digests only (never plaintext).
KNOWN_SHA256 = {
    "71448a2ad01e50ebed0b32b9bd3f174190cb640ce889d2492a41484f804f9bfc",
    "552be0a9b0dac10f57f031b89def021c8f79abf3a75913ff3eebcd2eb7b60877",
}

PATTERN = re.compile(
    r"(?<![A-Za-z0-9_\-])("
    r"sk-[A-Za-z0-9_\-]{16,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AIza[0-9A-Za-z_\-]{35}"
    r"|-----BEGIN (?:RSA|OPENSSH|EC|PRIVATE) ?[A-Z ]*PRIVATE KEY-----"
    r")"
)
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
             "datasets", "backup", "delivery/zh"}
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf",
                 ".zip", ".gz", ".bz2", ".xz", ".7z", ".bin", ".elf", ".exe"}
MAX_BYTES = 2_000_000


def mask(value: str) -> str:
    if len(value) <= 8:
        return value[:2] + "***"
    return value[:5] + "..." + value[-2:]


def iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in SKIP_DIRS for part in rel.split("/")[:-1]):
            continue
        if rel.startswith("delivery/zh/"):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        files.append(path)
    return files


def scan_file(path: Path, root: Path) -> list[tuple[str, int, str, str]]:
    try:
        if path.stat().st_size > MAX_BYTES:
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    hits = []
    rel = path.relative_to(root).as_posix()
    for lineno, line in enumerate(text.splitlines(), 1):
        for match in PATTERN.finditer(line):
            value = match.group(0)
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
            if digest in KNOWN_SHA256:
                continue
            if "PRIVATE KEY" in value:
                hits.append((rel, lineno, "PRIVATE_KEY_BLOCK", ""))
                continue
            context = PATTERN.sub("<REDACTED>", line.strip())[:160]
            hits.append((rel, lineno, mask(value), context))
    return hits


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="masked secret scan (offline)")
    parser.add_argument("paths", nargs="*", default=["."],
                        help="files or directories to scan (default: repository root)")
    parser.add_argument("--show-context", action="store_true",
                        help="print the matching line with the secret replaced by <REDACTED>")
    args = parser.parse_args(argv)

    roots = [Path(p) for p in (args.paths or ["."])]
    total = 0
    for root in roots:
        if not root.exists():
            print("SKIP missing", root)
            continue
        base = root if root.is_dir() else root.parent
        files = iter_files(root) if root.is_dir() else [root]
        for path in files:
            for rel, lineno, masked, context in scan_file(path, base):
                total += 1
                print("HIT %s:%d %s" % (rel, lineno, masked))
                if args.show_context and context:
                    print("    ctx: %s" % context)
    print("== total candidates:", total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
