"""Tests for scripts/check_markdown_language.py (offline, tmp-dir fixtures)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_markdown_language as markdown  # noqa: E402

TEXT_ALLOWLIST = ROOT / "docs" / "operations" / "markdown-language-allowlist.txt"
JSON_ALLOWLIST = ROOT / "docs" / "operations" / "markdown-language-allowlist.json"
NEW_GOVERNANCE_DOCS = (
    "docs/acceptance/non-goal-roadmap-2026-11-15.md",
    "docs/acceptance/platform-limits-2026-11-15.md",
    "docs/release/CI-SIGNOFF-2026-11-15.md",
)


def _write_doc(root: Path, relative: str, text: str) -> Path:
    path = root / "docs" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_allowlist(root: Path, lines: list[str], name: str = "allowlist.txt") -> Path:
    path = root / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _write_json_allowlist(root: Path, entries: list[dict]) -> Path:
    path = root / "allowlist.json"
    path.write_text(json.dumps({"allow": entries}), encoding="utf-8")
    return path


def _entry(path: str, *, reason: str = "historical", owner: str = "docs") -> dict:
    return {"path": path, "reason": reason, "owner": owner}


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_markdown_language.py"),
         *args],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )


def _current_non_ascii_docs() -> set[str]:
    docs = ROOT / "docs"
    found: set[str] = set()
    for path in docs.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        if any(ord(char) > 127 for char in text):
            found.add(path.relative_to(docs).as_posix())
    return found


# ---------------------------------------------------------------------------
# Core scan behaviour
# ---------------------------------------------------------------------------


def test_clean_docs_tree_passes(tmp_path: Path) -> None:
    _write_doc(tmp_path, "index.md", "# Index\n\nASCII only.\n")
    _write_doc(tmp_path, "nested/readme.md", "- one\n- two\n")
    report = markdown.scan(tmp_path / "docs")
    assert report["ok"] is True
    assert report["file_count"] == 2
    assert report["violations"] == []
    assert report["allowlisted"] == []
    assert report["allowlist_unknown"] == []


def test_non_ascii_document_fails_with_location(tmp_path: Path) -> None:
    _write_doc(tmp_path, "bad.md", "line one\ncaf\u00e9\n")
    report = markdown.scan(tmp_path / "docs")
    assert report["ok"] is False
    assert report["file_count"] == 1
    violation = report["violations"][0]
    assert violation["path"] == "bad.md"
    assert violation["line"] == 2
    assert violation["column"] == 4
    assert violation["codepoint"] == "U+00E9"


# ---------------------------------------------------------------------------
# Text allowlist (legacy format kept for the existing CI step)
# ---------------------------------------------------------------------------


def test_text_allowlist_suppresses_a_known_legacy_document(tmp_path: Path) -> None:
    _write_doc(tmp_path, "legacy/old.md", "caf\u00e9\n")
    _write_doc(tmp_path, "new.md", "ASCII\n")
    allowlist = _write_allowlist(tmp_path, ["legacy/old.md"])
    entries, fmt = markdown.load_allowlist(allowlist)
    assert fmt == "text"
    report = markdown.scan(tmp_path / "docs", entries)
    assert report["ok"] is True
    assert report["allowlisted"] == ["legacy/old.md"]


def test_text_allowlist_does_not_hide_new_documents(tmp_path: Path) -> None:
    _write_doc(tmp_path, "legacy/old.md", "caf\u00e9\n")
    _write_doc(tmp_path, "new/bad.md", "na\u00efve\n")
    allowlist = _write_allowlist(tmp_path, ["legacy/*.md"])
    entries, _fmt = markdown.load_allowlist(allowlist)
    report = markdown.scan(tmp_path / "docs", entries)
    assert report["ok"] is False
    assert [item["path"] for item in report["violations"]] == ["new/bad.md"]


def test_text_allowlist_parsing_skips_comments_and_blanks(tmp_path: Path) -> None:
    allowlist = _write_allowlist(
        tmp_path, ["# legacy docs", "", "legacy/old.md", "  # indented comment"]
    )
    entries, fmt = markdown.load_allowlist(allowlist)
    assert fmt == "text"
    assert [item["path"] for item in entries] == ["legacy/old.md"]


def test_allowlist_pattern_semantics() -> None:
    assert markdown.is_allowlisted("legacy/old.md", ["legacy/old.md"]) is True
    assert markdown.is_allowlisted("legacy/old.md", ["legacy/*.md"]) is True
    assert markdown.is_allowlisted("legacy/old.md", ["old.md"]) is False
    assert markdown.is_allowlisted("old.md", ["old.md"]) is True
    assert markdown.is_allowlisted("nested/old.md", ["*.md"]) is True
    assert markdown.is_allowlisted("legacy/old.md", ["other.md"]) is False


# ---------------------------------------------------------------------------
# JSON allowlist (governance format with path/reason/owner)
# ---------------------------------------------------------------------------


def test_json_allowlist_loads_reason_and_owner(tmp_path: Path) -> None:
    allowlist = _write_json_allowlist(tmp_path, [
        _entry("legacy/old.md", reason="historical research paper", owner="docs"),
    ])
    entries, fmt = markdown.load_allowlist(allowlist)
    assert fmt == "json"
    assert entries == [{
        "path": "legacy/old.md",
        "reason": "historical research paper",
        "owner": "docs",
    }]


def test_json_allowlist_normalizes_docs_prefix(tmp_path: Path) -> None:
    allowlist = _write_json_allowlist(tmp_path, [
        _entry("docs/legacy/old.md"),
    ])
    entries, _fmt = markdown.load_allowlist(allowlist)
    assert entries[0]["path"] == "legacy/old.md"


def test_json_allowlist_suppresses_known_document(tmp_path: Path) -> None:
    _write_doc(tmp_path, "legacy/old.md", "caf\u00e9\n")
    allowlist = _write_json_allowlist(tmp_path, [_entry("legacy/old.md")])
    entries, _fmt = markdown.load_allowlist(allowlist)
    report = markdown.scan(tmp_path / "docs", entries, enforce_unknown=True)
    assert report["ok"] is True
    assert report["allowlisted"] == ["legacy/old.md"]


def test_json_allowlist_does_not_hide_new_document(tmp_path: Path) -> None:
    _write_doc(tmp_path, "legacy/old.md", "caf\u00e9\n")
    _write_doc(tmp_path, "new/bad.md", "na\u00efve\n")
    allowlist = _write_json_allowlist(tmp_path, [_entry("legacy/old.md")])
    entries, _fmt = markdown.load_allowlist(allowlist)
    report = markdown.scan(tmp_path / "docs", entries, enforce_unknown=True)
    assert report["ok"] is False
    assert [item["path"] for item in report["violations"]] == ["new/bad.md"]


def test_json_allowlist_unknown_path_fails(tmp_path: Path) -> None:
    _write_doc(tmp_path, "legacy/old.md", "caf\u00e9\n")
    allowlist = _write_json_allowlist(tmp_path, [
        _entry("legacy/old.md"),
        _entry("legacy/deleted.md"),
    ])
    entries, _fmt = markdown.load_allowlist(allowlist)
    report = markdown.scan(tmp_path / "docs", entries, enforce_unknown=True)
    assert report["ok"] is False
    assert report["allowlist_unknown"] == ["legacy/deleted.md"]
    assert any(
        item["path"] == "legacy/deleted.md"
        and "does not exist" in item["detail"]
        for item in report["violations"]
    )


def test_json_allowlist_missing_fields_rejected(tmp_path: Path) -> None:
    for entry in (
        {"path": "legacy/old.md", "owner": "docs"},
        {"path": "legacy/old.md", "reason": "why"},
        {"reason": "why", "owner": "docs"},
        {"path": "legacy/old.md", "reason": "", "owner": "docs"},
    ):
        allowlist = _write_json_allowlist(tmp_path, [entry])
        try:
            markdown.load_allowlist(allowlist)
        except ValueError as exc:
            assert "missing non-empty" in str(exc)
        else:  # pragma: no cover - must fail
            raise AssertionError(f"invalid entry accepted: {entry}")


def test_json_allowlist_rejects_bad_structure(tmp_path: Path) -> None:
    for payload in ("not json", "[]", "{}", '{"allow": []}', '{"allow": {}}'):
        path = tmp_path / "allowlist.json"
        path.write_text(payload, encoding="utf-8")
        try:
            markdown.load_allowlist(path)
        except ValueError:
            continue
        raise AssertionError(f"invalid allowlist accepted: {payload}")


def test_json_allowlist_rejects_duplicate_path(tmp_path: Path) -> None:
    allowlist = _write_json_allowlist(tmp_path, [
        _entry("legacy/old.md"),
        _entry("legacy/old.md"),
    ])
    try:
        markdown.load_allowlist(allowlist)
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:  # pragma: no cover - must fail
        raise AssertionError("duplicate allowlist path accepted")


# ---------------------------------------------------------------------------
# CLI behaviour
# ---------------------------------------------------------------------------


def test_cli_json_fails_on_non_ascii(tmp_path: Path) -> None:
    _write_doc(tmp_path, "bad.md", "caf\u00e9\n")
    result = _run_cli("--docs-dir", str(tmp_path / "docs"), "--json")
    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["file_count"] == 1
    assert payload["violations"][0]["codepoint"] == "U+00E9"
    assert payload["allowlist_format"] is None


def test_cli_passes_clean_tree_with_text_allowlist(tmp_path: Path) -> None:
    _write_doc(tmp_path, "bad.md", "caf\u00e9\n")
    allowlist = _write_allowlist(tmp_path, ["bad.md"])
    result = _run_cli(
        "--docs-dir", str(tmp_path / "docs"),
        "--allowlist", str(allowlist), "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["allowlist_format"] == "text"
    assert payload["allowlisted"] == ["bad.md"]


def test_cli_json_allowlist_unknown_path_exits_1(tmp_path: Path) -> None:
    _write_doc(tmp_path, "bad.md", "caf\u00e9\n")
    allowlist = _write_json_allowlist(tmp_path, [_entry("missing.md")])
    result = _run_cli(
        "--docs-dir", str(tmp_path / "docs"),
        "--allowlist", str(allowlist), "--json",
    )
    assert result.returncode == 1, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["allowlist_format"] == "json"
    assert payload["allowlist_unknown"] == ["missing.md"]


def test_cli_invalid_json_allowlist_exits_2(tmp_path: Path) -> None:
    _write_doc(tmp_path, "bad.md", "caf\u00e9\n")
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text('{"allow": [{"path": "bad.md"}]}', encoding="utf-8")
    result = _run_cli(
        "--docs-dir", str(tmp_path / "docs"),
        "--allowlist", str(allowlist),
    )
    assert result.returncode == 2
    assert "invalid allowlist" in result.stderr


def test_cli_missing_docs_dir_exits_2(tmp_path: Path) -> None:
    result = _run_cli("--docs-dir", str(tmp_path / "missing"), "--json")
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# Repository policy: committed allowlists stay in sync and CI can be green
# ---------------------------------------------------------------------------


def test_new_governance_docs_are_ascii() -> None:
    for relative in NEW_GOVERNANCE_DOCS:
        path = ROOT / relative
        assert path.is_file(), relative
        text = path.read_text(encoding="utf-8")
        assert all(ord(char) < 128 for char in text), relative


def test_committed_allowlists_match_current_legacy_docs() -> None:
    current = _current_non_ascii_docs()
    text_lines = [
        line.strip() for line in TEXT_ALLOWLIST.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    json_entries, fmt = markdown.load_allowlist(JSON_ALLOWLIST)
    assert fmt == "json"
    assert set(text_lines) == current
    assert {entry["path"] for entry in json_entries} == current
    for entry in json_entries:
        assert entry["owner"] == "docs"
        assert entry["reason"].strip()
    assert any(
        entry["reason"] == "historical research paper, not product acceptance docs"
        for entry in json_entries
    )


def test_cli_with_committed_json_allowlist_is_green() -> None:
    result = _run_cli(
        "--allowlist", str(JSON_ALLOWLIST), "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["violations"] == []
    assert payload["allowlist_format"] == "json"
    assert payload["allowlisted"] == sorted(_current_non_ascii_docs())


def test_cli_with_committed_text_allowlist_is_green() -> None:
    result = _run_cli(
        "--allowlist", str(TEXT_ALLOWLIST), "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["allowlist_format"] == "text"


def test_default_full_scan_has_no_exemptions() -> None:
    result = _run_cli("--json")
    payload = json.loads(result.stdout)
    assert payload["allowlist_format"] is None
    assert payload["allowlist_entries"] == []
    assert payload["allowlisted"] == []
    # The repository still carries historical non-ASCII documents, so the
    # default (no allowlist) run fails closed instead of hiding them.
    assert payload["ok"] is False
    assert payload["violations"]
    assert result.returncode == 1
