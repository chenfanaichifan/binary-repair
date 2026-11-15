"""Tests for the Phase-8C C7 local external ingestion/quarantine."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import ingest_phase8c_external as ext  # noqa: E402

ARTIFACT = ROOT / "artifacts" / "phase8c-external-2026-11-16"
ARTIFACT_JSON = ARTIFACT / "external-ingestion.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate(root: Path) -> dict:
    binary = root / "bin" / "ext.elf"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"\x7fELF" + b"external" * 8)
    source = root / "bin" / "ext.c"
    source.write_bytes(b"int f(char *d, char *s){ strcpy(d,s); }\n")
    oracle = root / "bin" / "ext.poc.json"
    oracle.write_text(json.dumps({"schema_version": 1, "poc": []}),
                      encoding="utf-8")
    return {
        "sample_id": "external-sample-1",
        "split": "dev",
        "binary_path": "bin/ext.elf",
        "binary_sha256": _sha(binary),
        "target": {"kind": "symbol", "symbol": "f"},
        "oracle": {"manifest_path": "bin/ext.poc.json",
                   "sha256": _sha(oracle)},
        "source_refs": ["bin/ext.c"],
        "evidence_refs": ["external://test"],
        "license": {"name": "CC0-1.0", "url": "https://example.invalid/cc0"},
        "provenance": {"origin": "fake local fixture",
                       "acquired_at": "2026-11-16T00:00:00Z"},
    }


def test_committed_not_run_artifact_check_ok() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "ingest_phase8c_external.py"), "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "check OK" in result.stdout
    report = json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))
    assert report["status"] == "not_run"
    assert report["merge"]["public_merge_performed"] is False
    assert report["merge"]["hidden_merge_performed"] is False


def test_missing_root_is_not_run() -> None:
    report = ext.ingest(None)
    assert report["status"] == "not_run"
    assert report["merge"]["auto_merge_allowed"] is False


def test_valid_candidate_is_quarantined_not_merged(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"samples": [candidate]}), encoding="utf-8")
    report = ext.ingest(tmp_path)
    assert report["status"] == "ok"
    assert report["accepted"] == 1
    assert report["rejected"] == 0
    assert report["merge"] == {
        "public_merge_performed": False,
        "hidden_merge_performed": False,
        "auto_merge_allowed": False,
        "quarantine_only": True,
    }
    assert report["candidates"][0]["merge_allowed"] is False


def test_missing_license_provenance_and_hash_are_rejected(
        tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    candidate.pop("license")
    candidate.pop("provenance")
    candidate["binary_sha256"] = "0" * 64
    (tmp_path / "manifest.json").write_text(
        json.dumps({"samples": [candidate]}), encoding="utf-8")
    report = ext.ingest(tmp_path)
    assert report["accepted"] == 0
    assert report["rejected"] == 1
    reasons = " ".join(report["candidates"][0]["reasons"])
    assert "license" in reasons
    assert "provenance" in reasons
    assert "sha256" in reasons


def test_external_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    candidate = _candidate(tmp_path)
    binary = tmp_path / "bin" / "second.elf"
    binary.write_bytes(b"\x7fELF" + b"second" * 8)
    second = json.loads(json.dumps(candidate))
    second["binary_path"] = "bin/second.elf"
    second["binary_sha256"] = _sha(binary)
    (tmp_path / "manifest.json").write_text(
        json.dumps({"samples": [candidate, second]}), encoding="utf-8")
    report = ext.ingest(tmp_path)
    assert report["accepted"] == 1
    assert report["rejected"] == 1
    assert any("duplicate sample_id" in reason
               for reason in report["candidates"][1]["reasons"])


def test_no_network_ai_or_auto_merge_code() -> None:
    source = (SCRIPTS / "ingest_phase8c_external.py").read_text(
        encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for name in imported:
        assert not any(token in name for token in (
            "requests", "httpx", "urllib", "openai", "app.services.provider"))
    assert "public_merge_performed\": False" in source
    assert "hidden_merge_performed\": False" in source


@pytest.mark.parametrize("tamper", ["json", "readme", "sums"])
def test_check_detects_tampering(tmp_path: Path, tamper: str) -> None:
    target = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, target)
    if tamper == "json":
        path = target / "external-ingestion.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["status"] = "ok"
        report["accepted"] = 5
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    elif tamper == "readme":
        path = target / "README.md"
        path.write_text(path.read_text(encoding="utf-8") + "tamper\n",
                        encoding="utf-8")
    else:
        path = target / "SHA256SUMS"
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("0" * 64 + "  " + lines[0].split()[-1] + "\n"
                        + "\n".join(lines[1:]) + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "ingest_phase8c_external.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert result.returncode != 0
    assert "EXTERNAL-VIOLATION" in result.stdout
