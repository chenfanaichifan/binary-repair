#!/usr/bin/env python3
"""Markdown language policy: every tracked ``docs/**/*.md`` file must be ASCII.

The repository language policy keeps new product documentation ASCII-English so
release artifacts stay portable and reviewable. This checker scans every
Markdown document under ``docs/`` (recursively), reports the exact file, line
and column of each non-ASCII character, and fails closed: any non-allowlisted
non-ASCII character exits non-zero.

The allowlist is optional and supports two formats:

* **JSON** (preferred for governance)::

      {"allow": [
          {"path": "whitepaper-2026-11-14.md",
           "reason": "historical research paper, not product acceptance docs",
           "owner": "docs"}
      ]}

  Every entry requires a non-empty ``path``, ``reason`` and ``owner``. Paths
  are docs-relative (an optional ``docs/`` prefix is accepted) and exact: a
  JSON allowlist entry whose path no longer exists is a failure, so the list
  cannot silently rot. Duplicate paths are rejected.
* **Text** (legacy): one ``fnmatch`` pattern per line relative to the docs
  directory; ``#`` starts a comment and blank lines are ignored.

An allowlisted document is reported separately and does not fail the check, so
historical documents can be tracked as explicit debt instead of being silently
ignored. New documents are not on the allowlist and must stay ASCII.

Default behaviour with no ``--allowlist`` is a full scan (no exemptions); CI
passes the committed allowlist explicitly.

``--json`` prints ``{ok, docs_dir, file_count, allowlist_format, allowlisted,
allowlist_entries, allowlist_unknown, violations}``; exit code is 0 iff ok, 2
when the docs directory or allowlist is unusable.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCS_DIR = ROOT / "docs"
DEFAULT_ALLOWLIST = ROOT / "docs" / "operations" / "markdown-language-allowlist.json"


def iter_markdown(docs_dir: Path) -> list[Path]:
    """All Markdown files under ``docs_dir`` (recursive, sorted)."""
    return sorted(
        path for path in docs_dir.rglob("*.md") if path.is_file()
    )


def _normalize_relative_path(value: str) -> str:
    """Normalize a docs-relative path (accepts an optional ``docs/`` prefix)."""
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if text.startswith("docs/"):
        text = text[len("docs/"):]
    return text


def _entry(path: str, reason: str = "", owner: str = "") -> dict[str, str]:
    return {"path": path, "reason": reason, "owner": owner}


def _load_json_allowlist(raw: str) -> list[dict[str, str]]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("allowlist JSON must be an object")
    allow = payload.get("allow")
    if not isinstance(allow, list) or not allow:
        raise ValueError("allowlist JSON must contain a non-empty 'allow' list")
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(allow):
        if not isinstance(item, dict):
            raise ValueError(f"allow[{index}] is not an object")
        path = item.get("path")
        reason = item.get("reason")
        owner = item.get("owner")
        for field, value in (("path", path), ("reason", reason), ("owner", owner)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"allow[{index}] missing non-empty {field!r}")
        normalized = _normalize_relative_path(str(path))
        if (
            not normalized
            or normalized.startswith("/")
            or ".." in normalized.split("/")
        ):
            raise ValueError(
                f"allow[{index}] path must be docs-relative: {path!r}")
        if normalized in seen:
            raise ValueError(f"duplicate allowlist path: {normalized}")
        seen.add(normalized)
        entries.append({
            "path": normalized,
            "reason": str(reason).strip(),
            "owner": str(owner).strip(),
        })
    return entries


def load_allowlist(path: Path) -> tuple[list[dict[str, str]], str]:
    """Load a JSON or text allowlist; returns ``(entries, format)``.

    Raises ``OSError``/``UnicodeError`` for unreadable files and ``ValueError``
    for invalid JSON/text allowlist content.
    """
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".json" or raw.lstrip().startswith("{"):
        return _load_json_allowlist(raw), "json"
    entries = [
        _entry(line.strip())
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return entries, "text"


def normalize_allowlist(
    allowlist: Iterable[str | Mapping[str, Any]] = (),
) -> list[dict[str, str]]:
    """Normalize scan input items (plain pattern strings or entry mappings)."""
    entries: list[dict[str, str]] = []
    for item in allowlist:
        if isinstance(item, str):
            entries.append(_entry(item.strip()))
        elif isinstance(item, Mapping):
            entries.append(_entry(
                str(item.get("path", "")).strip(),
                str(item.get("reason", "")).strip(),
                str(item.get("owner", "")).strip(),
            ))
        else:  # pragma: no cover - defensive
            raise TypeError(f"allowlist item must be str or mapping: {item!r}")
    return entries


def is_allowlisted(relative_path: str, patterns: Iterable[str]) -> bool:
    """Match a docs-relative POSIX path against the allowlist patterns."""
    relative = relative_path.replace("\\", "/")
    basename = relative.rsplit("/", 1)[-1]
    for pattern in patterns:
        normalized = pattern.replace("\\", "/")
        if fnmatch.fnmatch(relative, normalized):
            return True
        # Wildcard patterns without a slash also match the basename at any
        # depth. A plain file name stays anchored at the docs root so an
        # allowlist entry cannot silently hide same-named nested documents.
        if "/" not in normalized and any(
            char in normalized for char in "*?["
        ) and fnmatch.fnmatch(basename, normalized):
            return True
    return False


def scan(
    docs_dir: Path,
    allowlist: Iterable[str | Mapping[str, Any]] = (),
    *,
    enforce_unknown: bool = False,
) -> dict[str, Any]:
    """Scan one docs tree and return the deterministic report payload."""
    entries = normalize_allowlist(allowlist)
    patterns = [item["path"] for item in entries]
    files = iter_markdown(docs_dir)
    relative_files = [path.relative_to(docs_dir).as_posix() for path in files]
    existing = set(relative_files)
    violations: list[dict[str, Any]] = []
    allowlisted: list[str] = []
    allowlist_unknown: list[str] = []
    if enforce_unknown:
        for pattern in patterns:
            if pattern not in existing:
                allowlist_unknown.append(pattern)
                violations.append({
                    "path": pattern,
                    "line": 0,
                    "column": 0,
                    "codepoint": None,
                    "detail": "allowlist path does not exist under docs",
                })
    for path, relative in zip(files, relative_files):
        if is_allowlisted(relative, patterns):
            allowlisted.append(relative)
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            violations.append({
                "path": relative,
                "line": 0,
                "column": 0,
                "codepoint": None,
                "detail": f"unreadable: {type(exc).__name__}: {exc}",
            })
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for column, char in enumerate(line, 1):
                if ord(char) > 127:
                    violations.append({
                        "path": relative,
                        "line": line_number,
                        "column": column,
                        "codepoint": f"U+{ord(char):04X}",
                        "detail": "non-ASCII character in Markdown document",
                    })
    return {
        "ok": not violations,
        "docs_dir": str(docs_dir),
        "file_count": len(files),
        "allowlist_format": None,
        "allowlisted": allowlisted,
        "allowlist_entries": patterns,
        "allowlist_unknown": allowlist_unknown,
        "violations": violations,
    }


def _format_text(report: dict[str, Any]) -> str:
    lines = [
        "markdown-language: ok={ok} docs={docs} files={files} "
        "allowlisted={allowlisted} unknown={unknown} violations={violations}"
        .format(
            ok=report["ok"],
            docs=report["docs_dir"],
            files=report["file_count"],
            allowlisted=len(report["allowlisted"]),
            unknown=len(report["allowlist_unknown"]),
            violations=len(report["violations"]),
        )
    ]
    for item in report["violations"]:
        if item.get("line"):
            lines.append(
                "FAIL {path}:{line}:{column}: {codepoint} {detail}".format(**item)
            )
        else:
            lines.append(
                "FAIL {path}: {detail}".format(**item)
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="fail on non-ASCII characters in docs/**/*.md")
    parser.add_argument(
        "--docs-dir", type=Path, default=DEFAULT_DOCS_DIR,
        help="docs directory to scan recursively (default: repository docs/)")
    parser.add_argument(
        "--allowlist", type=Path, default=None,
        help="optional JSON allowlist ({'allow': [{path, reason, owner}]}) or "
             "legacy text allowlist (one fnmatch pattern per line)")
    parser.add_argument(
        "--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    docs_dir = args.docs_dir
    if not docs_dir.is_dir():
        print(f"ERROR: docs directory unavailable: {docs_dir}", file=sys.stderr)
        return 2
    entries: list[dict[str, str]] = []
    allowlist_format: str | None = None
    if args.allowlist is not None:
        try:
            entries, allowlist_format = load_allowlist(args.allowlist)
        except (OSError, UnicodeError) as exc:
            print(
                f"ERROR: allowlist unavailable: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            return 2
        except ValueError as exc:
            print(f"ERROR: invalid allowlist: {exc}", file=sys.stderr)
            return 2
    report = scan(
        docs_dir, entries,
        enforce_unknown=allowlist_format == "json",
    )
    report["allowlist_format"] = allowlist_format
    report["allowlist_path"] = str(args.allowlist) if args.allowlist else ""
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True))
    else:
        print(_format_text(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
