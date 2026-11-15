from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_artifacts  # noqa: E402


def test_audit_case_reports_hashes_without_runs() -> None:
    case = {
        "id": "hard-multicall",
        "binary": "fixtures/hard-cases/vuln-hardcases-c-x86_64.elf",
        "poc": "fixtures/poc/hard-multicall.json",
    }
    result = audit_artifacts.audit_case(case, [], None)
    assert result["case_id"] == "hard-multicall"
    assert result["status"] == "ARTIFACT_MISSING_CONFIRMED"
    assert result["original"]["sha256"]
    assert result["poc"]["sha256"]
