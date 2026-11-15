"""Tests for the Phase-8C C5 contamination audit."""
from __future__ import annotations

import ast
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

import audit_phase8c_contamination as contam  # noqa: E402

ARTIFACT = ROOT / "artifacts" / "phase8c-contamination-2026-11-16"
ARTIFACT_JSON = ARTIFACT / "contamination.json"


def _write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _manifest(tmp_path: Path, samples: list[dict]) -> Path:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"sample_count": len(samples),
                                "samples": samples}), encoding="utf-8")
    return path


def test_committed_public_artifact_check_ok() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "audit_phase8c_contamination.py"),
         "--check"], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "check OK" in result.stdout


def test_public_artifact_is_clean_and_has_expected_counts() -> None:
    report = json.loads(ARTIFACT_JSON.read_text(encoding="utf-8"))
    assert report["kind"] == contam.KIND
    assert report["mode"] == "public_only"
    assert report["status"] == "ok"
    assert report["verdict"] == "clean"
    assert report["counts"]["public_core"] == 28
    assert report["counts"]["public_runtime"] == 20
    assert report["counts"]["public_analysis_only"] == 8
    assert report["counts"]["public_samples"] == 32
    assert report["hidden"]["requested"] is False
    assert report["hidden"]["content_included_in_report"] is False
    assert report["exact_duplicates"]
    assert all(item["severity"] == "note"
               for item in report["exact_duplicates"]
               + report["near_duplicates"])
    assert "PHASE8C_HIDDEN_ROOT" not in json.dumps(report)


def test_exact_duplicate_same_target_is_contaminated(tmp_path: Path) -> None:
    binary = _write(tmp_path / "a.elf", b"\x7fELF" + b"A" * 64)
    digest = contam._sha256_file(binary)
    samples = [
        {"sample_id": "dup-a", "split": "dev",
         "binary_path": str(binary), "binary_sha256": digest,
         "target": {"kind": "symbol", "symbol": "f"}},
        {"sample_id": "dup-b", "split": "validation",
         "binary_path": str(binary), "binary_sha256": digest,
         "target": {"kind": "symbol", "symbol": "f"}},
    ]
    report = contam.audit(_manifest(tmp_path, samples))
    assert report["verdict"] == "contaminated"
    assert any(item["resolution"] == "exact_binary_duplicate_same_target"
               for item in report["exact_duplicates"])


def test_same_binary_different_target_is_allowed_note(tmp_path: Path) -> None:
    binary = _write(tmp_path / "a.elf", b"\x7fELF" + b"B" * 64)
    digest = contam._sha256_file(binary)
    samples = [
        {"sample_id": "same-a", "split": "dev",
         "binary_path": str(binary), "binary_sha256": digest,
         "target": {"kind": "symbol", "symbol": "one"}},
        {"sample_id": "same-b", "split": "validation",
         "binary_path": str(binary), "binary_sha256": digest,
         "target": {"kind": "symbol", "symbol": "two"}},
    ]
    report = contam.audit(_manifest(tmp_path, samples))
    assert report["verdict"] == "clean"
    assert any(item["resolution"] == "same_binary_different_target_allowed"
               for item in report["exact_duplicates"])


def test_near_duplicate_source_is_flagged(tmp_path: Path) -> None:
    source_a = _write(tmp_path / "a.c",
                      b"int f(char *d, char *s) { strcpy(d, s); } /*a*/\n")
    source_b = _write(tmp_path / "b.c",
                      b"int f(char *d, char *s) { strcpy(d, s); } /*b*/\n")
    binary_a = _write(tmp_path / "a.elf", b"\x7fELF" + b"C" * 32)
    binary_b = _write(tmp_path / "b.elf", b"\x7fELF" + b"D" * 32)
    samples = [
        {"sample_id": "near-a", "split": "dev",
         "binary_path": str(binary_a),
         "binary_sha256": contam._sha256_file(binary_a),
         "source_refs": [str(source_a)],
         "target": {"kind": "symbol", "symbol": "f"}},
        {"sample_id": "near-b", "split": "validation",
         "binary_path": str(binary_b),
         "binary_sha256": contam._sha256_file(binary_b),
         "source_refs": [str(source_b)],
         "target": {"kind": "symbol", "symbol": "g"}},
    ]
    report = contam.audit(_manifest(tmp_path, samples))
    assert report["verdict"] in {"suspicious", "contaminated"}
    assert any(item["kind"] == "source_text"
               for item in report["near_duplicates"])


def test_hidden_root_missing_is_not_run(tmp_path: Path) -> None:
    report = contam.audit(hidden_root=tmp_path / "missing-hidden")
    assert report["mode"] == "hidden"
    assert report["status"] == "not_run"
    assert report["hidden"]["reason"]
    assert report["hidden"]["content_included_in_report"] is False


def test_hidden_mode_reads_synthetic_root_without_leaking_paths(
        tmp_path: Path) -> None:
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    binary = _write(hidden / "sample.elf", b"\x7fELF" + b"E" * 32)
    manifest = _manifest(hidden, [
        {"sample_id": "hidden-a", "split": "hidden",
         "binary_path": str(binary),
         "binary_sha256": contam._sha256_file(binary),
         "target": {"kind": "symbol", "symbol": "f"},
         "oracle": {"kinds": ["external_poc"]}},
    ])
    (hidden / "manifest.json").write_bytes(manifest.read_bytes())
    report = contam.audit(hidden_root=hidden)
    assert report["mode"] == "hidden"
    assert report["status"] == "ok"
    assert report["counts"]["hidden_samples"] == 1
    assert str(hidden) not in json.dumps(report)


def test_no_network_or_ai_imports() -> None:
    source = (SCRIPTS / "audit_phase8c_contamination.py").read_text(
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
    assert "repair_any" not in source


@pytest.mark.parametrize("tamper", ["json", "readme", "sums"])
def test_check_detects_tampering(tmp_path: Path, tamper: str) -> None:
    target = tmp_path / "artifact"
    shutil.copytree(ARTIFACT, target)
    if tamper == "json":
        path = target / "contamination.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        report["verdict"] = "contaminated"
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
        [sys.executable, str(SCRIPTS / "audit_phase8c_contamination.py"),
         "--check", "--artifact-dir", str(target)],
        cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert result.returncode != 0
    assert "CONTAMINATION-VIOLATION" in result.stdout
