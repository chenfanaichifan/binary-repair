from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_artifacts_is_not_gitignored() -> None:
    """A hand-off only one worktree can read is not a hand-off."""
    lines = {
        line.strip()
        for line in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "/artifacts/" not in lines
    assert "artifacts/" not in lines


def test_artifacts_readme_and_manifest_are_in_the_tree() -> None:
    readme = (REPO / "artifacts" / "README.md").read_text(encoding="utf-8")
    manifest = (REPO / "artifacts" / "MANIFEST.md").read_text(encoding="utf-8")
    assert "SHA256SUMS" in readme
    assert "not just the worktree" in readme or "not just the" in readme
    # The manifest must name both roots, or a reader cannot tell where a
    # historical package lives versus a new one.
    assert "dist/" in manifest and "artifacts/" in manifest


def test_no_blanket_archive_ignore_rules() -> None:
    """`*.zip` style rules must not silently swallow a artifacts package."""
    lines = [
        line.strip()
        for line in (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    ]
    assert "*.zip" not in lines
    assert "*.bundle" not in lines
