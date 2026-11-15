"""Cross-binary benchmark manifest/fixture invariants (no model calls)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.containers import detect_container

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "fixtures" / "repair-benchmark"
CASES = json.loads((BENCH / "cases.json").read_text())["cases"]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_manifest_has_multiple_binaries_and_three_cwes():
    assert len({case["binary_id"] for case in CASES}) >= 4
    assert len({case["cwe"] for case in CASES}) >= 3
    assert {case["id"] for case in CASES} >= {
        "hard-multicall", "cwe121-unchecked-strcpy",
        "cwe122-heap-copy", "cwe787-index-write",
    }


def test_new_fixture_arch_and_poc_hash_match():
    for name in ("CWE122_heap_copy", "CWE787_index_write"):
        binary = BENCH / name / "original.elf"
        assert binary.is_file()
        assert detect_container(binary.read_bytes()).arch == "x86_64"
        build = json.loads((BENCH / name / "build.json").read_text())
        assert build["output"]["sha256"] == _sha(binary)
    for poc_name in ("repair-cwe122.json", "repair-cwe787.json"):
        poc = json.loads((ROOT / "fixtures" / "poc" / poc_name).read_text())
        fixture = ROOT / "fixtures" / "repair-benchmark" / (
            "CWE122_heap_copy" if "122" in poc_name else "CWE787_index_write"
        ) / "original.elf"
        assert poc["fixture_sha256"] == _sha(fixture)


def test_cases_are_x86_64_and_have_references():
    for case in CASES:
        assert case["arch"] == "x86_64"
        assert (ROOT / case["binary"]).is_file()
        assert (ROOT / case["poc"]).is_file()
        assert (ROOT / case["reference_fix"]).is_file()
