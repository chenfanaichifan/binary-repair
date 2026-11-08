"""Shared fixtures for integration tests that consume tracked evidence bundles."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def copy_bundle(tmp_path: Path):
    """Return a helper that materializes a private copy of a tracked bundle.

    Ingest rewrites ``_v2-interface-scored.json`` inside the bundle it is given,
    and tracked evidence is byte-bound by SHA256SUMS. Tests therefore copy the
    package first and never hand ingest the tracked directory.

    The copy is verbatim: the evidence contains legitimate CRLF files
    (a1.routeb/v4-symbolic.json), so normalizing line endings here would break
    the package's own manifest.
    """

    def _copy(src: Path, name: str) -> Path:
        dst = tmp_path / name
        shutil.copytree(src, dst)
        return dst

    return _copy
