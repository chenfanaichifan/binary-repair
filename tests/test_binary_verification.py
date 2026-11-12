"""Deterministic verification packet and gate for direct ELF repairs."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services import binary_repair_engine as engine
from app.services.binary_repair_engine import repair_elf
from app.services.binary_verification import build_verification

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
PE = ROOT / "fixtures" / "pe" / "cli-64.exe"


def _build(raw: bytes):
    patched, report = repair_elf(raw)
    return patched, report, build_verification(report, original=raw, patched=patched)


def test_strict_fixture_passes_with_complete_evidence():
    patched, report, verification = _build(VULN.read_bytes())
    assert patched is not None
    assert report.mode == "strict"
    assert verification.gate.success is True
    assert verification.gate.outcome == "success_within_scope"
    assert verification.gate.required_checks >= 8
    assert verification.gate.required_not_run == 0
    assert verification.gate.evidence_sha256 == verification.packet["report_sha256"]
    statuses = {item["id"]: item["status"] for item in verification.packet["checks"]}
    assert statuses["format"] == "passed"
    assert statuses["candidate.present"] == "passed"
    assert statuses["runtime.no_overflow"] == "passed"
    assert statuses["strict.reviewed_template"] == "passed"
    assert verification.packet["missing"] == []
    assert verification.packet["candidate"]["patched_equals_original"] is False


def test_unsupported_input_is_unsupported_and_has_no_candidate():
    patched, report, verification = _build(PE.read_bytes())
    assert patched is None
    assert report.supported is False
    assert verification.gate.success is False
    assert verification.gate.outcome == "unsupported"
    assert verification.gate.evidence_sha256 is None
    assert verification.packet["candidate"]["present"] is False
    assert "format" in {item["check_id"] for item in verification.packet["missing"]}


def test_missing_runtime_evidence_is_inconclusive(monkeypatch):
    monkeypatch.setattr(
        engine,
        "_runtime_summary",
        lambda patched, capacity: {"available": False, "error": "simulated evidence gap"},
    )
    patched, report, verification = _build(VULN.read_bytes())
    assert patched is not None
    assert report.status == "patched"
    assert verification.gate.success is False
    assert verification.gate.outcome == "inconclusive"
    assert verification.gate.required_not_run >= 1
    assert verification.gate.evidence_sha256 is None
    missing = {item["check_id"] for item in verification.packet["missing"]}
    assert {"runtime.available", "runtime.cases", "runtime.no_overflow"} <= missing


def test_runtime_sentinel_failure_rejects(monkeypatch):
    def broken_runtime(patched: bytes, capacity: int | None) -> dict:
        return {
            "available": True,
            "engine": "fake-runtime",
            "cases": [
                {
                    "input_len": size,
                    "exit_code": 0 if size <= int(capacity or 0) else 1,
                    "stdout_len": 7,
                    "stderr_len": 0 if size <= int(capacity or 0) else 30,
                    "stack_sentinel_intact": size != int(capacity or 0) + 1,
                    "error": None,
                }
                for size in (0, 1, int(capacity or 0), int(capacity or 0) + 1)
            ],
        }

    monkeypatch.setattr(engine, "_runtime_summary", broken_runtime)
    patched, _report, verification = _build(VULN.read_bytes())
    assert patched is not None
    assert verification.gate.success is False
    assert verification.gate.outcome == "rejected"
    assert verification.gate.evidence_sha256 is None


def test_candidate_bytes_mismatch_is_not_success():
    raw = VULN.read_bytes()
    patched, report = repair_elf(raw)
    assert patched is not None
    verification = build_verification(report, original=raw, patched=patched + b"X")
    assert verification.gate.success is False
    statuses = {item["id"]: item["status"] for item in verification.packet["checks"]}
    assert statuses["candidate.identity.patched"] == "failed"
    assert statuses["patch.scope"] == "failed"


def test_report_hash_is_stable_and_evidence_sensitive(monkeypatch):
    raw = VULN.read_bytes()
    _patched, _report, first = _build(raw)
    _patched2, _report2, second = _build(raw)
    assert first.packet["report_sha256"] == second.packet["report_sha256"]

    monkeypatch.setattr(
        engine,
        "_runtime_summary",
        lambda patched, capacity: {
            "available": True,
            "engine": "fake-runtime",
            "cases": [
                {
                    "input_len": 0,
                    "exit_code": 0,
                    "stdout_len": 7,
                    "stderr_len": 0,
                    "stack_sentinel_intact": True,
                    "error": None,
                }
            ],
        },
    )
    _patched3, _report3, third = _build(raw)
    assert third.packet["report_sha256"] != first.packet["report_sha256"]


def test_packet_hashes_bind_to_original_bytes():
    raw = VULN.read_bytes()
    _patched, _report, verification = _build(raw)
    assert verification.packet["candidate"]["original_sha256"] == hashlib.sha256(raw).hexdigest()
