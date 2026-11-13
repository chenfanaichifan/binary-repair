"""v5 positive matrix: 32-bit x86 (ELF32 / PE32) is repaired and gated.

These tests are integration-level: analyzer, writer, guard injection, Unicorn
x86-32 runtime and the deterministic gate must all agree before a candidate is
released.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.services.binary_pipeline import (
    detect_format,
    repair_any,
    repair_binary,
    scan_binary,
)

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
CASES = {
    "elf-i386": (ROOT / "fixtures" / "elf" / "vuln-strcpy-x86.elf", "elf", "i386", ".elf"),
    "pe-i386": (ROOT / "fixtures" / "pe" / "vuln-strcpy-x86.exe", "pe", "i386", ".exe"),
}


def _read(path: Path) -> bytes:
    if not path.is_file():
        pytest.skip(f"fixture missing: {path}")
    return path.read_bytes()


@pytest.mark.parametrize("name", sorted(CASES))
def test_i386_scan_finds_exact_capacity(name):
    path, fmt, arch, _suffix = CASES[name]
    data = _read(path)
    assert detect_format(data)[:2] == (fmt, arch)
    payload = scan_binary(data)
    assert payload["schema_version"] == 4
    assert payload["format"] == fmt and payload["arch"] == arch
    assert payload["bits"] == 32
    assert payload["matrix"]["cell"] == f"{fmt}/i386/32/little"
    assert payload["repair_supported"] is True
    findings = payload["findings"]
    assert findings, payload
    assert findings[0]["kind"] == "unbounded_copy"
    assert findings[0]["capacity"] == 16
    assert findings[0]["patchable"] is True
    assert findings[0]["strategy"] == "guard"


@pytest.mark.parametrize("name", sorted(CASES))
def test_i386_repair_is_verified_by_emulated_runtime(name):
    path, fmt, arch, _suffix = CASES[name]
    data = _read(path)
    outcome = repair_any(data)
    assert outcome.candidate is not None, outcome.report.to_dict()
    assert outcome.download_allowed is True
    assert outcome.verified is True
    report = outcome.report
    assert report.format == fmt and report.arch == arch
    assert report.schema_version == 4
    assert report.disposition == "verified_patch"
    assert report.status == "patched"
    assert report.supported is True
    assert report.candidate_available is True
    assert report.matrix["cell"] == f"{fmt}/i386/32/little"
    assert report.actions and report.actions[0]["kind"] == "guard"
    assert report.strategy == "guard"
    assert report.capacity == 16
    assert report.delivery == {
        "download_allowed": True, "verified": True, "tier": "emulated_run",
    }
    verification = report.verification
    assert verification["tier"] == "emulated_run"
    assert verification["engine"] == "unicorn-i386"
    assert verification["gate"]["success"] is True
    assert verification["gate"]["outcome"] == "success_within_scope"
    assert verification["static_reparse"] is True
    # Unicorn ran the original-size cases and the over-capacity cases.
    cases = report.runtime.get("cases") or []
    assert {case["input_len"] for case in cases} >= {0, 1, 15, 16, 17, 64}
    assert report.runtime.get("verdict") == "pass"
    assert outcome.candidate != data
    assert detect_format(outcome.candidate)[:2] == (fmt, arch)


@pytest.mark.parametrize("name", sorted(CASES))
def test_i386_legacy_wrapper_static_only_is_labelled(name):
    path, _fmt, _arch, _suffix = CASES[name]
    patched, report = repair_binary(_read(path), verify=False)
    assert patched is not None
    assert report.disposition == "static_only_patch"
    assert report.status == "not_verified"
    assert report.delivery["verified"] is False
    assert report.delivery["download_allowed"] is True


def test_i386_cli_writes_verified_candidate(tmp_path):
    path, _fmt, _arch, suffix = CASES["pe-i386"]
    source = _read(path)
    out = tmp_path / f"fixed{suffix}"
    proc = subprocess.run(
        [str(PYTHON), str(ROOT / "scripts" / "repair_binary.py"),
         str(path), str(out), "--json"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.is_file()
    import json

    payload = json.loads(proc.stdout)
    assert payload["disposition"] == "verified_patch"
    assert payload["verified"] is True
    assert payload["output"] == str(out)
    assert out.read_bytes() != source
