"""Reviewed duplicated-capacity-check repair end to end.

The legacy ELF x86-64 engine cannot express a runtime-length copy behind an
inlined range check.  The pipeline therefore falls back to the reviewed
``capacity`` strategy, whose only runtime evidence is a supplied PoC/regression
manifest executed by a native/emulated guest runtime.  These tests cover:

* the fail-closed gate without a manifest (``not_verified``, never success);
* a passing differential (``verified_patch`` + candidate bytes);
* a failing differential (``rejected``);
* an unavailable runner (``not_run``, never fabricated);
* the ``patch.capacity`` check re-deriving every rewritten region from bytes
  (tampered candidate/original bytes fail, missing actions fail);
* explicit ``strategy="capacity"`` requests and engine fail-closed errors.

``run_poc`` is monkeypatched so the tests never need a VM.  The engine runs on
the repo-relative fixtures, not on a host path.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

import app.services.binary_pipeline as pipeline
import app.services.poc_runner as poc_runner
from app.services.binary_pipeline import repair_any
from app.services.repair.capacity import repair_capacity_confusion
from app.services.unified_verification import build

ROOT = Path(__file__).resolve().parents[1]
MARCX = ROOT / "fixtures" / "elf" / "vuln-capacity-confusion-x86_64.elf"
MARCX_ORIGINAL_SHA256 = (
    "72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5"
)
MARCX_PATCHED_SHA256 = (
    "93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2"
)


def _fixture() -> bytes:
    if not MARCX.is_file():
        pytest.skip(f"fixture missing: {MARCX}")
    return MARCX.read_bytes()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _FakePocEvidence:
    """Minimal PocEvidence stand-in with the documented ``to_dict`` shape."""

    def __init__(self, status: str) -> None:
        self.status = status
        self.payload = {
            "schema_version": 1,
            "status": status,
            "runner": "limactl",
            "tier": "emulated_run" if status in {"pass", "fail"} else "",
            "original_sha256": MARCX_ORIGINAL_SHA256,
            "candidate_sha256": MARCX_PATCHED_SHA256 if status != "unavailable" else None,
            "poc": [],
            "regression": [],
            "limitations": [],
        }
        if status in {"pass", "fail"}:
            candidate_ok = status == "pass"
            self.payload["poc"] = [
                {
                    "case_id": "poc-overflow",
                    "kind": "poc",
                    "executable": "original",
                    "exit_code": -6,
                    "crashed": True,
                    "expected_ok": True,
                },
                {
                    "case_id": "poc-overflow",
                    "kind": "poc",
                    "executable": "candidate",
                    "exit_code": 1,
                    "crashed": False,
                    "expected_ok": candidate_ok,
                },
            ]
            self.payload["regression"] = [
                {
                    "case_id": "benign",
                    "kind": "regression",
                    "executable": "original",
                    "exit_code": 0,
                    "crashed": False,
                    "expected_ok": True,
                },
                {
                    "case_id": "benign",
                    "kind": "regression",
                    "executable": "candidate",
                    "exit_code": 0,
                    "crashed": False,
                    "expected_ok": True,
                },
            ]
        if status == "unavailable":
            self.payload["limitations"] = [
                "no native/qemu runner for this format/arch on this host; "
                "PoC was not executed"
            ]

    def to_dict(self) -> dict:
        return dict(self.payload)


def _fake_runner(monkeypatch, status: str) -> None:
    evidence = _FakePocEvidence(status)
    monkeypatch.setattr(poc_runner, "run_poc", lambda *args, **kwargs: evidence)


# ---------------------------------------------------------------------------
# Pipeline disposition rules
# ---------------------------------------------------------------------------


def test_capacity_fallback_without_manifest_is_not_verified():
    data = _fixture()
    outcome = repair_any(data, verify=True)
    report = outcome.report

    assert outcome.candidate is None
    assert outcome.download_allowed is False
    assert outcome.verified is False
    assert report.disposition == "not_verified"
    assert report.strategy == "capacity"
    assert report.mode == "capacity-check"
    assert report.status == "not_verified"
    assert report.supported is False
    assert report.matrix["cell"] == "elf/x86_64/64/little"
    assert report.patched_sha256 == MARCX_PATCHED_SHA256
    assert report.actions and report.actions[0]["kind"] == "capacity_check_rewrite"
    assert report.actions[0]["offset"] == 8409
    assert report.findings  # the detected site metadata

    packet = report.verification["packet"]
    statuses = {check["id"]: check["status"] for check in packet["checks"]}
    assert statuses["patch.capacity"] == "passed"
    assert statuses["runtime.evidence"] == "not_run"
    assert report.verification["gate"]["success"] is False
    assert report.verification["gate"]["outcome"] == "inconclusive"
    assert packet["scope"]["runtime_tier"] == "static_only"
    assert packet["scope"]["runtime_verdict"] == "not_run"


def test_capacity_fallback_is_static_only_when_explicitly_opted_in():
    outcome = repair_any(_fixture(), verify=True, allow_static_only=True)
    report = outcome.report
    assert outcome.candidate is not None
    assert outcome.verified is False
    assert outcome.download_allowed is True
    assert report.disposition == "static_only_patch"
    assert report.delivery["tier"] == "static_only"
    assert report.warnings


def test_capacity_fallback_with_passing_manifest_is_verified(monkeypatch):
    _fake_runner(monkeypatch, "pass")
    outcome = repair_any(_fixture(), verify=True, poc_manifest={"schema_version": 1})
    report = outcome.report

    assert outcome.candidate is not None
    assert outcome.download_allowed is True
    assert outcome.verified is True
    assert report.disposition == "verified_patch"
    assert report.status == "patched"
    assert report.supported is True
    assert report.candidate_available is True
    assert report.strategy == "capacity"
    assert report.mode == "capacity-check"
    assert _sha(outcome.candidate) == MARCX_PATCHED_SHA256
    assert report.patched_sha256 == MARCX_PATCHED_SHA256
    assert report.poc["status"] == "pass"
    assert report.delivery == {
        "download_allowed": True,
        "verified": True,
        "tier": "emulated_run",
    }

    packet = report.verification["packet"]
    statuses = {check["id"]: check["status"] for check in packet["checks"]}
    assert statuses["patch.capacity"] == "passed"
    assert statuses["runtime.evidence"] == "passed"
    assert statuses["runtime.tier"] == "passed"
    assert statuses["runtime.contract"] == "passed"
    assert statuses["poc.native.available"] == "passed"
    assert statuses["poc.native.original_failure"] == "passed"
    assert statuses["poc.native.candidate_pass"] == "passed"
    assert statuses["poc.native.regression"] == "passed"
    assert packet["scope"]["runtime_tier"] == "emulated_run"
    assert packet["scope"]["runtime_verdict"] == "pass"
    assert packet["capacity"]["actions"] == report.actions
    assert report.verification["gate"]["success"] is True
    assert report.verification["gate"]["outcome"] == "success_within_scope"
    assert report.verification["engine"] == "capacity-check"


def test_capacity_fallback_with_failing_differential_is_rejected(monkeypatch):
    _fake_runner(monkeypatch, "fail")
    outcome = repair_any(_fixture(), verify=True, poc_manifest={"schema_version": 1})
    report = outcome.report

    assert outcome.candidate is None
    assert outcome.download_allowed is False
    assert report.disposition == "rejected"
    assert report.status == "not_verified"
    statuses = {
        check["id"]: check["status"]
        for check in report.verification["packet"]["checks"]
    }
    assert statuses["runtime.evidence"] == "failed"
    assert statuses["runtime.contract"] == "failed"
    assert report.verification["gate"]["outcome"] == "rejected"


def test_capacity_fallback_with_unavailable_runner_stays_not_run(monkeypatch):
    _fake_runner(monkeypatch, "unavailable")
    outcome = repair_any(_fixture(), verify=True, poc_manifest={"schema_version": 1})
    report = outcome.report

    assert outcome.candidate is None
    assert report.disposition == "not_verified"
    statuses = {
        check["id"]: check["status"]
        for check in report.verification["packet"]["checks"]
    }
    assert statuses["runtime.evidence"] == "not_run"
    assert statuses["poc.native.available"] == "not_run"
    assert statuses["poc.native.original_failure"] == "not_run"
    assert report.verification["gate"]["outcome"] == "inconclusive"


def test_explicit_capacity_strategy_is_supported(monkeypatch):
    _fake_runner(monkeypatch, "pass")
    outcome = repair_any(
        _fixture(), strategy="capacity", verify=True,
        poc_manifest={"schema_version": 1},
    )
    assert outcome.verified is True
    assert outcome.report.strategy == "capacity"
    assert outcome.report.matrix["cell"] == "elf/x86_64/64/little"


def test_explicit_capacity_strategy_without_site_is_analysis_only(monkeypatch):
    data = _fixture()
    monkeypatch.setattr(
        pipeline, "_capacity_engine",
        lambda: (lambda _data: (None, _NoSiteReport())),
    )
    outcome = repair_any(data, strategy="capacity", verify=True)
    assert outcome.candidate is None
    assert outcome.report.disposition == "analysis_only"
    assert outcome.report.strategy == "capacity"
    assert outcome.report.error


class _NoSiteReport:
    actions: list = []
    sites: list = []
    message_actions: list = []
    limitations = ["no inlined range-check block matched the reviewed shape"]

    def to_dict(self) -> dict:
        return {
            "strategy": "capacity",
            "mode": "unsupported",
            "supported": False,
            "status": "unsupported",
            "actions": [],
            "sites": [],
            "message_actions": [],
            "limitations": list(self.limitations),
        }


def test_capacity_engine_error_fails_closed(monkeypatch):
    def _boom(_data: bytes):
        raise RuntimeError("simulated engine failure")

    monkeypatch.setattr(pipeline, "_capacity_engine", lambda: _boom)
    outcome = repair_any(_fixture(), verify=True)
    assert outcome.candidate is None
    assert outcome.report.disposition == "analysis_only"
    assert any(
        "capacity-check engine error" in item
        for item in outcome.report.limitations
    )


def test_capacity_does_not_replace_the_legacy_strict_template(monkeypatch):
    legacy = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
    if not legacy.is_file():
        pytest.skip(f"fixture missing: {legacy}")
    outcome = repair_any(legacy.read_bytes(), verify=True)
    assert outcome.verified is True
    assert outcome.report.strategy == "strict-template"
    assert "patch.capacity" not in {
        check["id"] for check in outcome.report.verification["packet"]["checks"]
    }


# ---------------------------------------------------------------------------
# patch.capacity re-derivation (independent of the pipeline)
# ---------------------------------------------------------------------------


def _capacity_build(candidate: bytes, *, capacity: dict, **overrides):
    data = _fixture()
    patched, _report = repair_capacity_confusion(data)
    assert patched is not None
    actions = list(overrides.pop("actions", capacity.get("actions") or []))
    kwargs = dict(
        format_name="elf",
        arch="x86_64",
        original=data,
        candidate=candidate,
        actions=[dict(action) for action in actions],
        runtime=None,
        reparse_ok=True,
        original_sha256=_sha(data),
        patched_sha256=_sha(candidate),
        external_poc=_FakePocEvidence("pass").to_dict(),
        capacity=capacity,
    )
    kwargs.update(overrides)
    return data, build(**kwargs)


def test_patch_capacity_check_passes_on_untampered_bytes():
    data = _fixture()
    patched, report = repair_capacity_confusion(data)
    assert patched is not None
    _data, verification = _capacity_build(patched, capacity=report.to_dict())
    statuses = {check["id"]: check["status"] for check in verification.packet["checks"]}
    assert statuses["patch.capacity"] == "passed"
    assert verification.gate.success is True
    detail = next(
        check["detail"] for check in verification.packet["checks"]
        if check["id"] == "patch.capacity"
    )
    assert "0x4020d9" in detail
    assert "ebx->r12d" in detail


def test_patch_capacity_check_fails_when_candidate_bytes_are_tampered():
    data = _fixture()
    patched, report = repair_capacity_confusion(data)
    assert patched is not None
    payload = report.to_dict()
    tampered = bytearray(patched)
    offset = payload["actions"][0]["offset"]
    tampered[offset] ^= 0xFF
    _data, verification = _capacity_build(bytes(tampered), capacity=payload)
    statuses = {check["id"]: check["status"] for check in verification.packet["checks"]}
    assert statuses["patch.capacity"] == "failed"
    assert verification.gate.success is False
    assert verification.gate.outcome == "rejected"


def test_patch_capacity_check_fails_when_original_bytes_are_tampered():
    data = _fixture()
    patched, report = repair_capacity_confusion(data)
    assert patched is not None
    payload = report.to_dict()
    mangled = bytearray(data)
    mangled[payload["actions"][0]["offset"]] ^= 0xFF
    _data, verification = _capacity_build(
        patched, capacity=payload, original=bytes(mangled),
        original_sha256=_sha(bytes(mangled)),
    )
    statuses = {check["id"]: check["status"] for check in verification.packet["checks"]}
    assert statuses["patch.capacity"] == "failed"


def test_patch_capacity_check_fails_without_actions():
    patched, report = repair_capacity_confusion(_fixture())
    assert patched is not None
    payload = dict(report.to_dict())
    payload["actions"] = []
    _data, verification = _capacity_build(patched, capacity=payload)
    statuses = {check["id"]: check["status"] for check in verification.packet["checks"]}
    assert statuses["patch.capacity"] == "failed"
    capacity_check = next(
        check for check in verification.packet["checks"]
        if check["id"] == "patch.capacity"
    )
    assert "no rewrite action was recorded" in capacity_check["detail"]


def test_patch_capacity_check_fails_on_stale_after_hex():
    patched, report = repair_capacity_confusion(_fixture())
    assert patched is not None
    payload = dict(report.to_dict())
    payload["actions"] = [dict(action) for action in payload["actions"]]
    payload["actions"][0]["after_hex"] = payload["actions"][0]["before_hex"]
    _data, verification = _capacity_build(patched, capacity=payload)
    statuses = {check["id"]: check["status"] for check in verification.packet["checks"]}
    assert statuses["patch.capacity"] == "failed"


# ---------------------------------------------------------------------------
# Real guest integration (skipped when no native/qemu/Lima runner is available)
# ---------------------------------------------------------------------------


def _guest_runner_available() -> bool:
    try:
        from app.services.guest_runner import find_guest_runner

        return find_guest_runner("x86_64") is not None
    except Exception:  # noqa: BLE001 - missing runner is a skip, not a failure
        return False


@pytest.mark.skipif(
    not _guest_runner_available(),
    reason="no native/qemu/Lima runner for x86_64 ELF on this host",
)
def test_capacity_repair_with_real_manifest_is_verified():
    """Real PoC/regression manifest through the native/emulated guest runner."""
    import json

    manifest_path = ROOT / "fixtures" / "poc" / "marcx-capacity.json"
    if not manifest_path.is_file():
        pytest.skip(f"fixture missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    outcome = repair_any(_fixture(), verify=True, poc_manifest=manifest)
    report = outcome.report

    assert outcome.verified is True, report.verification["gate"]
    assert outcome.candidate is not None
    assert report.disposition == "verified_patch"
    assert report.strategy == "capacity"
    assert report.poc["status"] == "pass"
    assert report.poc["runner"]
    assert report.poc["tier"] in {"native_run", "emulated_run"}
    assert _sha(outcome.candidate) == MARCX_PATCHED_SHA256
    statuses = {
        check["id"]: check["status"]
        for check in report.verification["packet"]["checks"]
    }
    assert statuses["patch.capacity"] == "passed"
    assert statuses["runtime.evidence"] == "passed"
    assert statuses["poc.native.original_failure"] == "passed"
    assert statuses["poc.native.candidate_pass"] == "passed"
    assert statuses["poc.native.regression"] == "passed"
    assert report.verification["packet"]["scope"]["runtime_verdict"] == "pass"
