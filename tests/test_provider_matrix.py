"""Provider matrix: record schema, aggregate math, target-strict fields, honesty.

The tests use the ``--client reference`` scripted provider and a fake provider
client; no network call is made.  One smoke test runs the real CLI over two
cases with the scripted reference provider (PoC/regression execution may use the
native/qemu/Lima guest runner; it is not required to succeed for the artifact
schema to be valid).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_provider_matrix as pm  # noqa: E402

DEFAULT_COST_BASIS = pm.COST_BASIS


def _cases() -> list[dict]:
    return json.loads(
        (ROOT / "fixtures" / "hard-cases" / "cases.json").read_text(encoding="utf-8")
    )["cases"]


def _case(case_id: str) -> dict:
    return next(case for case in _cases() if case["id"] == case_id)


def _record(
    case_id: str,
    *,
    strict_disposition: str = "analysis_only",
    strict_expected: str = "analysis_only",
    strict_in_scope: bool = False,
    whole_disposition: str = "rejected",
    whole_verified: bool = False,
    reference_status: str = "source_only",
    reference_verified: bool | None = None,
    ai_attempted: bool = False,
    ai_verified: bool = False,
    ai_in_scope: bool = False,
    ai_status: str = "not_attempted",
) -> dict:
    ai_checks = {"poc_gate": "pass" if ai_verified else "no_candidate"}
    return {
        "schema_version": pm.SCHEMA_VERSION,
        "case_id": case_id,
        "family": "synthetic",
        "case": {},
        "input_sha256": "0" * 64,
        "provider": {"provider": "fake"},
        "model": "fake-model",
        "seed": None,
        "cost": None,
        "elapsed_ms": 1,
        "target_policy": {
            "whole_image_baseline": "whole_image",
            "target_strict_baseline": "target_strict",
            "ai_target": "target",
        },
        "target_scope": {"name": case_id, "va": 1, "end": 2, "source": "symbol"},
        "target_scope_check": "passed" if ai_in_scope else "not_run",
        "target_in_scope": ai_in_scope,
        "baseline_whole_image": {
            "attempted": True,
            "disposition": whole_disposition,
            "verified": whole_verified,
        },
        "baseline": {},
        "baseline_target_strict": {
            "attempted": True,
            "disposition": strict_disposition,
            "verified": False,
            "expected": strict_expected,
            "matches_expected": strict_disposition == strict_expected,
            "target_scope": {"name": case_id, "va": 1, "end": 2, "source": "symbol"},
            "target_in_scope": strict_in_scope,
            "target_scope_check": "passed" if strict_in_scope else "not_run",
            "actions": [],
        },
        "reference_fix": {
            "attempted": True,
            "status": reference_status,
            "verified": reference_verified,
        },
        "ai_target": {
            "attempted": ai_attempted,
            "status": ai_status,
            "attempts": [{"verified": ai_verified}] if ai_attempted else [],
            "verified": ai_verified,
            "target_in_scope": ai_in_scope,
            "target_scope": {"name": case_id, "va": 1, "end": 2, "source": "symbol"},
            "target_scope_check": "passed" if ai_in_scope else "not_run",
            "checks_summary": ai_checks,
            "candidate_sha256": "a" * 64 if ai_verified else None,
        },
        "inconclusive_reasons": [],
        "limitations": [],
    }


# ---------------------------------------------------------------------------
# Aggregate math
# ---------------------------------------------------------------------------


def test_aggregate_rates_and_reason_counts():
    records = [
        _record("c1", whole_disposition="rejected", reference_status="verified",
                reference_verified=True, strict_in_scope=True,
                ai_attempted=True, ai_verified=True,
                ai_in_scope=True, ai_status="accepted"),
        _record("c2", whole_disposition="analysis_only", reference_status="source_only"),
        _record("c3", strict_disposition="rejected", strict_expected="analysis_only",
                whole_disposition="rejected", reference_status="gate_fail",
                reference_verified=False, ai_attempted=True, ai_status="invalid"),
    ]
    for record in records:
        record["inconclusive_reasons"] = pm._record_reasons(record)
    aggregate = pm._aggregate(records, elapsed_ms=1234)

    assert aggregate["cases"] == 3
    assert aggregate["baseline_whole_image_verified"] == 0
    assert aggregate["baseline_target_strict_expected_matches"] == 2
    assert aggregate["target_strict_pass_rate"] == pytest.approx(2 / 3)
    assert aggregate["target_scope_resolved"] == 3
    assert aggregate["target_scope_resolved_rate"] == pytest.approx(1.0)
    assert aggregate["target_in_scope"] == 1  # only c1's strict baseline
    assert aggregate["target_in_scope_rate"] == pytest.approx(1 / 3)
    assert aggregate["ai_attempts"] == 2
    assert aggregate["ai_target_verified"] == 1
    assert aggregate["ai_target_verified_rate"] == pytest.approx(1 / 3)
    assert aggregate["ai_target_in_scope"] == 1
    assert aggregate["ai_target_in_scope_rate"] == pytest.approx(1 / 3)
    # c1 (verified) and c3 (gate_fail) were both executed; c2 is source_only.
    assert aggregate["reference_evaluated"] == 2
    assert aggregate["reference_verified"] == 1
    assert aggregate["reference_source_only"] == 1
    assert aggregate["elapsed_ms"] == 1234
    assert aggregate["cost_total"] is None
    reasons = aggregate["inconclusive_failure_reasons"]
    assert reasons["whole_image:rejected"] == 2
    assert reasons["whole_image:analysis_only"] == 1
    assert reasons["ai:invalid/no_candidate"] == 1
    # A successful dimension is not reported as an inconclusive/failure reason.
    assert "ai_verified" not in reasons


def test_aggregate_is_zero_safe_on_empty_records():
    aggregate = pm._aggregate([], elapsed_ms=0)
    assert aggregate["cases"] == 0
    assert aggregate["target_strict_pass_rate"] == 0.0
    assert aggregate["target_in_scope_rate"] == 0.0
    assert aggregate["ai_target_verified_rate"] == 0.0
    assert aggregate["inconclusive_failure_reasons"] == {}


# ---------------------------------------------------------------------------
# Record schema / target-strict fields
# ---------------------------------------------------------------------------


def test_case_record_contains_contract_t4_fields(tmp_path):
    case = _case("cwe121-unchecked-strcpy")
    provider = {
        "requested": "real",
        "provider": "deepseek",
        "model_requested": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "configured": True,
        "errors": [],
    }
    record = pm._case_record(
        case, provider=provider, seed=None, whole_image_supported=True,
    )
    for key in (
        "provider", "model", "seed", "cost", "elapsed_ms", "target_policy",
        "target_scope", "target_scope_check", "target_in_scope",
        "baseline_target_strict", "ai_target", "ai_result", "reference_fix",
        "inconclusive_reasons", "limitations",
    ):
        assert key in record, key
    assert record["model"] == "deepseek-chat"
    assert record["seed"] is None
    assert record["cost"] is None
    assert isinstance(record["elapsed_ms"], int)
    assert set(record["target_policy"]) == {
        "whole_image_baseline", "target_strict_baseline", "ai_target",
    }
    strict = record["baseline_target_strict"]
    for key in (
        "attempted", "disposition", "verified", "expected", "matches_expected",
        "target_scope", "target_in_scope", "target_scope_check", "actions",
    ):
        assert key in strict, key
    expected = (
        case.get("baseline_expected_target_strict") or case["baseline_expected"]
    )
    assert strict["expected"] == expected
    assert strict["matches_expected"] is True
    assert strict["disposition"] in {"analysis_only", "rejected", "unsupported"}
    assert record["baseline_whole_image"]["allow_whole_image_requested"] is True
    assert record["baseline_whole_image"]["allow_whole_image_supported"] is True
    # No model was called in this pure deterministic phase.
    assert record["ai_target"]["attempted"] is False
    assert record["ai_target"]["verified"] is False
    assert record["reference_fix"]["status"] == "source_only"
    assert record["reference_fix"]["verified"] is None


def test_sha256sums_helper_matches_files(tmp_path):
    out = tmp_path / "artifacts"
    out.mkdir()
    (out / "README.md").write_text("readme\n", encoding="utf-8")
    (out / "summary.json").write_text("{}\n", encoding="utf-8")
    (out / "per-case").mkdir()
    (out / "per-case" / "c1.json").write_text("{}\n", encoding="utf-8")
    files = [out / "README.md", out / "summary.json", out / "per-case" / "c1.json"]
    sums_path = pm.write_sha256sums(out, files)
    entries = pm.parse_sha256sums(sums_path)
    assert set(entries) == {"README.md", "summary.json", "per-case/c1.json"}
    assert "SHA256SUMS" not in entries
    for path in files:
        assert entries[path.relative_to(out).as_posix()] == hashlib.sha256(
            path.read_bytes()
        ).hexdigest()


# ---------------------------------------------------------------------------
# Fake provider (no network) through the real orchestration path
# ---------------------------------------------------------------------------


class _FakeProviderClient:
    """Chat client returning invalid assembly JSON; never touches the network."""

    provider_name = "fakeprov"
    base_url = "http://127.0.0.1:9/never-called"
    model = "fake-model"

    def __init__(self) -> None:
        self.calls = 0

    def chat_json(self, messages, **kwargs):
        self.calls += 1
        return SimpleNamespace(
            content=json.dumps({"schema_version": 1, "assembly": "this is not assembly"}),
            model=self.model,
            usage={"prompt_tokens": 3, "completion_tokens": 4,
                   "total_tokens": 7, "latency_ms": 5},
            request_id="fake-request",
        )


def test_fake_provider_run_records_provider_fields_and_honest_failure(
    tmp_path, monkeypatch,
):
    import app.services.assistant_llm as assistant_llm

    fake = _FakeProviderClient()
    monkeypatch.setattr(assistant_llm, "client_from_env", lambda *a, **k: fake)
    monkeypatch.setattr(
        pm.hb, "_provider_config_metadata",
        lambda: {"provider": "fakeprov", "title": "fake", "base_url": fake.base_url,
                 "model": "fake-model", "configured": True, "errors": []},
    )
    import argparse

    args = argparse.Namespace(
        out=tmp_path / "matrix",
        client="real",
        case="cwe121-unchecked-strcpy",
        repeats=1,
        contract_level="full",
        max_seconds=600,
        max_calls=5,
        preflight=True,
        provider_tag="fake-provider",
        seed=None,
    )
    assert pm.run_matrix(args) == 0

    out = tmp_path / "matrix"
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["provider_status"] == "ok"
    assert summary["provider"]["provider"] == "fakeprov"
    assert summary["provider"]["model_requested"] == "fake-model"
    assert summary["provider"]["preflight"]["ok"] is True
    assert summary["seed"] is None and summary["seed_supported"] is False
    assert summary["cost"]["total"] is None
    assert summary["budget"]["calls_used"] == 2  # preflight + one AI call
    assert summary["budget"]["stopped_early"] is False

    record = json.loads(
        (out / "per-case" / "cwe121-unchecked-strcpy.json").read_text(encoding="utf-8")
    )
    attempt = record["ai_target"]["attempts"][0]
    # The fake provider returns a well-formed envelope with non-assembly bytes:
    # the model call is "accepted", but injection/PoC fails and nothing is
    # ever counted as a success.
    assert attempt["status"] == "accepted"
    assert attempt["assembly_returned"] is True
    assert attempt["verified"] is False
    assert attempt["candidate_sha256"] is None
    assert attempt["injection"]["error"]
    assert attempt["usage"]["total_tokens"] == 7
    assert attempt["provider_calls"] == 1
    assert record["ai_target"]["verified"] is False
    assert fake.calls == 2

    # Artifact contract: README/summary/per-case/SHA256SUMS present and valid.
    assert (out / "README.md").is_file()
    entries = pm.parse_sha256sums(out / "SHA256SUMS")
    assert set(entries) == {
        "README.md", "summary.json", "per-case/cwe121-unchecked-strcpy.json",
    }
    for name, digest in entries.items():
        assert digest == hashlib.sha256((out / name).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# CLI smoke: scripted reference provider over two cases (no real API)
# ---------------------------------------------------------------------------


def _run_cli(*argv: str, env: dict | None = None):
    import os
    import subprocess

    child_env = dict(os.environ)
    if env:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "run_provider_matrix.py"), *argv],
        cwd=ROOT, capture_output=True, text=True, timeout=900, env=child_env,
    )


def test_reference_cli_smoke_over_two_cases(tmp_path):
    out = tmp_path / "ref-matrix"
    proc = _run_cli(
        "--out", str(out), "--client", "reference", "--case",
        "inline-byte-loop,hard-loop16",
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["kind"] == "provider_matrix"
    assert summary["provider_status"] == "reference"
    assert summary["aggregate"]["cases"] == 2
    assert len(summary["cases"]) == 2
    assert {row["case_id"] for row in summary["cases"]} == {
        "inline-byte-loop", "hard-loop16",
    }
    assert summary["target_strict_pass_rate"] == pytest.approx(1.0)
    for row in summary["cases"]:
        assert "target_in_scope_rate" in summary  # top-level alias present
        assert row["baseline_target_strict_matches_expected"] is True
        assert row["reference_status"] in {"verified", "source_only", "gate_fail"}
        assert row["ai_status"] == "reference"
    record = json.loads(
        (out / "per-case" / "inline-byte-loop.json").read_text(encoding="utf-8")
    )
    ai = record["ai_target"]
    assert ai["attempted"] is True
    assert ai["verified"] in {True, False}
    assert ai["checks_summary"]["poc_gate"] in {"pass", "fail", "no_candidate"}
    assert ai["target_scope_check"] in {"passed", "failed", "not_run"}
    assert record["target_scope_check"] == ai["target_scope_check"]
    assert record["cost"] is None
    assert record["seed"] is None
    assert record["provider"]["requested"] == "reference"
    entries = pm.parse_sha256sums(out / "SHA256SUMS")
    assert entries
    for name, digest in entries.items():
        assert digest == hashlib.sha256((out / name).read_bytes()).hexdigest()


def test_cli_unavailable_provider_records_honest_partial_evidence(tmp_path):
    """No usable provider: AI phase unavailable, deterministic evidence still produced."""
    out = tmp_path / "unavailable-matrix"
    proc = _run_cli(
        "--out", str(out),
        "--client", "real",
        "--case", "cwe121-unchecked-strcpy,uaf-noinput",
        env={
            "BINARYREPAIR_PROVIDER": "dashscope",
            "DASHSCOPE_API_KEY": "",
            "BAILIAN_API_KEY": "",
            "BINARYREPAIR_DASHSCOPE_API_KEY": "",
        },
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["provider_status"] == "unavailable"
    assert summary["unavailable_reason"]
    assert "llm_client_not_configured" in summary["unavailable_reason"]
    assert summary["aggregate"]["ai_called"] == 0
    assert summary["aggregate"]["ai_target_verified"] == 0
    assert summary["aggregate"]["cases"] == 2
    for row in summary["cases"]:
        assert row["ai_verified"] is False
        assert row["ai_status"] == "unavailable"
        assert row["baseline_target_strict_matches_expected"] is True
    assert any("provider" in item.lower() for item in summary["limitations"])
    # Deterministic evidence is still complete for every case.
    for case_id in ("cwe121-unchecked-strcpy", "uaf-noinput"):
        record = json.loads(
            (out / "per-case" / f"{case_id}.json").read_text(encoding="utf-8")
        )
        assert record["baseline_whole_image"]["attempted"] is True
        assert record["baseline_target_strict"]["attempted"] is True
        assert record["ai_target"]["attempted"] is False
        assert record["ai_target"]["status"] == "unavailable"
        assert record["ai_target"]["verified"] is False
        assert record["reference_fix"]["attempted"] is True
    entries = pm.parse_sha256sums(out / "SHA256SUMS")
    assert entries
    for name, digest in entries.items():
        assert digest == hashlib.sha256((out / name).read_bytes()).hexdigest()
