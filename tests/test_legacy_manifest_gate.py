"""P1 legacy-gate convergence: a PoC/regression manifest can never be accepted.

The legacy stack/emulated verification gate models one evidence family only
(reviewed stack template + emulated capacity/boundary runtime).  External-PoC
evidence belongs to the unified evidence-profile gate, so this module pins:

* ``build_verification(external_poc=...)`` records an explicit required
  ``manifest.legacy_gate_unsupported`` failure -- fail closed, never a silent
  drop, never a success;
* manifest-less legacy calls keep every existing check id/status/outcome
  (byte-for-byte packet digest) unchanged;
* the review/API write paths route manifest requests through the unified
  evidence-profile gate only and disclose it as
  ``report.universal["manifest_routing"] == "unified"``; the manifest-less
  legacy path says ``"legacy_readonly"``;
* a manifest-bearing request can never surface a legacy packet, even if a
  regression elsewhere produced one.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import CSRF_TOKEN, SESSION_TOKEN, app
from app.services import binary_pipeline, poc_runner
from app.services.binary_repair_engine import repair_elf
from app.services.binary_review import (
    MANIFEST_ROUTING_LEGACY,
    MANIFEST_ROUTING_UNIFIED,
    run_direct_repair,
)
from app.services.binary_verification import build_verification

ROOT = Path(__file__).resolve().parents[1]
VULN = ROOT / "artifacts" / "vuln-elf" / "vuln.elf"
MARCX = ROOT / "fixtures" / "elf" / "vuln-capacity-confusion-x86_64.elf"
CAPACITY_MANIFEST = ROOT / "fixtures" / "poc" / "marcx-capacity.json"
HEAP = ROOT / "fixtures" / "hard-cases" / "vuln-heap-malloc-x86_64.elf"
HEAP_MANIFEST = ROOT / "fixtures" / "poc" / "heap-malloc.json"

# Captured from the pre-convergence tree: the exact legacy check set for the
# reviewed strict template.  Existing callers must keep every id/status and the
# packet digest unchanged.
STRICT_BASELINE_CHECKS = [
    ("format", "passed"),
    ("candidate.present", "passed"),
    ("candidate.identity.original", "passed"),
    ("candidate.identity.patched", "passed"),
    ("patch.scope", "passed"),
    ("runtime.available", "passed"),
    ("runtime.cases", "passed"),
    ("runtime.no_overflow", "passed"),
    ("runtime.boundary_semantics", "passed"),
    ("strict.reviewed_template", "passed"),
    ("profile.declared", "passed"),
    ("profile.required_checks", "passed"),
]
STRICT_BASELINE_SHA256 = (
    "0a0fec9ffe2aaff21d64475624614dd7e42808d5349406ccae31b9c2764a5c50"
)

# Captured baseline for the emulated bounds-only legacy mode.
BOUNDS_BASELINE_CHECKS = [
    ("format", "passed"),
    ("candidate.present", "passed"),
    ("candidate.identity.original", "passed"),
    ("candidate.identity.patched", "passed"),
    ("patch.scope", "passed"),
    ("runtime.available", "passed"),
    ("runtime.cases", "passed"),
    ("runtime.no_overflow", "passed"),
    ("profile.declared", "passed"),
    ("profile.required_checks", "passed"),
]
BOUNDS_BASELINE_SHA256 = (
    "2cc6b73b5c9e1a52a600d2f470736d65f07465155f1dacf07a4b5b7a8fede89f"
)

POC_FAILURE_TITLE = "external PoC evidence must use the unified evidence-profile gate"


def _strict_case():
    raw = VULN.read_bytes()
    patched, report = repair_elf(raw)
    assert patched is not None
    return raw, patched, report


def _bounds_case():
    original = b"\x02" * 16
    patched = b"\x03" * 16
    cases = [
        {
            "input_len": size,
            "exit_code": 0,
            "stdout_len": 7,
            "stderr_len": 0,
            "stack_sentinel_intact": True,
            "error": None,
        }
        for size in (0, 1, 16, 17)
    ]
    report = SimpleNamespace(
        original_sha256=hashlib.sha256(original).hexdigest(),
        patched_sha256=hashlib.sha256(patched).hexdigest(),
        format="elf64-little",
        arch="x86_64",
        supported=True,
        mode="bounds-only",
        strict=False,
        capacity=16,
        strategy="immediate",
        offsets=[4],
        findings=[],
        runtime={"available": True, "engine": "unicorn-x86-64", "cases": cases},
        limitations=[],
    )
    return original, patched, report


def _checks(verification):
    return [
        (str(item["id"]), str(item["status"]))
        for item in verification.packet["checks"]
    ]


def _check_ids(verification):
    return {str(item["id"]) for item in verification.packet["checks"]}


def _statuses(verification):
    return {
        str(item["id"]): str(item["status"])
        for item in verification.packet["checks"]
    }


class _FakePocEvidence:
    """PocEvidence stand-in for the unified external-PoC profile (no VM)."""

    def __init__(self, status: str = "pass") -> None:
        candidate_ok = status == "pass"
        self.payload = {
            "schema_version": 1,
            "status": status,
            "runner": "limactl",
            "tier": "emulated_run" if status in {"pass", "fail"} else "",
            "poc": [
                {"case_id": "poc", "kind": "poc", "executable": "original",
                 "crashed": True, "expected_ok": True},
                {"case_id": "poc", "kind": "poc", "executable": "candidate",
                 "crashed": status == "fail", "expected_ok": candidate_ok},
            ],
            "regression": [
                {"case_id": "benign", "kind": "regression",
                 "executable": "original", "exit_code": 0, "expected_ok": True},
                {"case_id": "benign", "kind": "regression",
                 "executable": "candidate", "exit_code": 0, "expected_ok": True},
            ],
            "limitations": [],
        }

    def to_dict(self) -> dict:
        return dict(self.payload)


def _patch_poc_runner(monkeypatch, status: str = "pass") -> None:
    evidence = _FakePocEvidence(status)
    monkeypatch.setattr(poc_runner, "run_poc", lambda *a, **k: evidence)


class _FakeNativePocEvidence:
    """Full native-PoC evidence stand-in (heap guard profile, no VM)."""

    def to_dict(self) -> dict:
        def case(kind: str, executable: str, exit_code: int | None,
                 crashed: bool, stdout: str) -> dict:
            return {
                "case_id": "case",
                "kind": kind,
                "executable": executable,
                "exit_code": exit_code,
                "crashed": crashed,
                "stdout": stdout,
                "stderr": "",
                "stdout_hex": stdout.encode().hex(),
                "timed_out": False,
                "error": None,
                "expected_ok": True,
            }

        return {
            "schema_version": 1,
            "status": "pass",
            "runner": "limactl",
            "tier": "emulated_run",
            "stdout_signature": "matched",
            "no_input": False,
            "original_sha256": "",
            "candidate_sha256": "",
            "poc": [
                case("poc", "original", 134, True, ""),
                case("poc", "candidate", 0, False, "AAAAAAAAAAAAAAA\n"),
            ],
            "regression": [
                case("regression", "original", 0, False, "hi\n"),
                case("regression", "candidate", 0, False, "hi\n"),
            ],
            "limitations": [],
        }


def _heap_manifest() -> dict:
    return json.loads(HEAP_MANIFEST.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. build_verification: external PoC evidence fails closed
# ---------------------------------------------------------------------------


def test_build_verification_external_poc_is_failed_closed():
    raw, patched, report = _strict_case()
    verification = build_verification(
        report,
        original=raw,
        patched=patched,
        external_poc={"schema_version": 1},
    )

    statuses = _statuses(verification)
    assert statuses.get("manifest.legacy_gate_unsupported") == "failed"
    manifest_check = next(
        item
        for item in verification.packet["checks"]
        if item["id"] == "manifest.legacy_gate_unsupported"
    )
    assert manifest_check["required"] is True
    assert manifest_check["detail"] == POC_FAILURE_TITLE

    # Fail closed: the legacy gate can never verify with manifest evidence and
    # no candidate can be claimed.
    assert verification.gate.success is False
    assert verification.gate.outcome != "success_within_scope"
    assert verification.gate.outcome in {"rejected", "unsupported"}
    assert verification.gate.evidence_sha256 is None
    assert manifest_check["id"] in {
        item["check_id"] for item in verification.packet["missing"]
    }
    # Explicit disclosure in the human-reviewable limitations, not a silent drop.
    assert any(
        "external-PoC evidence model" in text
        and "unified evidence-profile gate" in text
        for text in verification.packet["limitations"]
    )


def test_build_verification_external_poc_gate_is_rejected_for_a_good_candidate():
    raw, patched, report = _strict_case()
    verification = build_verification(
        report, original=raw, patched=patched, external_poc={"schema_version": 1}
    )
    # A candidate that would otherwise pass still cannot be accepted.
    assert verification.gate.outcome == "rejected"
    assert verification.gate.required_not_run == 0


def test_build_verification_empty_manifest_mapping_still_fails_closed():
    raw, patched, report = _strict_case()
    verification = build_verification(
        report, original=raw, patched=patched, external_poc={}
    )
    assert verification.gate.success is False
    assert _statuses(verification)["manifest.legacy_gate_unsupported"] == "failed"


def test_build_verification_report_carried_manifest_backstop():
    raw, patched, report = _strict_case()
    report.external_poc = {"schema_version": 1}
    verification = build_verification(report, original=raw, patched=patched)
    assert verification.gate.success is False
    assert _statuses(verification)["manifest.legacy_gate_unsupported"] == "failed"


# ---------------------------------------------------------------------------
# 2. Manifest-less legacy calls are byte-for-byte unchanged
# ---------------------------------------------------------------------------


def test_build_verification_manifest_less_strict_path_unchanged():
    raw, patched, report = _strict_case()
    verification = build_verification(report, original=raw, patched=patched)

    assert _checks(verification) == STRICT_BASELINE_CHECKS
    # The packet digest pins every field the gate saw (scope, payload, checks,
    # limitations); it must not move for manifest-less callers.
    assert verification.packet["report_sha256"] == STRICT_BASELINE_SHA256
    assert verification.gate.success is True
    assert verification.gate.outcome == "success_within_scope"
    assert verification.gate.required_checks == len(STRICT_BASELINE_CHECKS)
    assert "manifest.legacy_gate_unsupported" not in _check_ids(verification)
    assert "scope.target_scope" not in _check_ids(verification)


def test_build_verification_manifest_less_bounds_only_path_unchanged():
    original, patched, report = _bounds_case()
    verification = build_verification(report, original=original, patched=patched)

    assert _checks(verification) == BOUNDS_BASELINE_CHECKS
    assert verification.packet["report_sha256"] == BOUNDS_BASELINE_SHA256
    assert verification.gate.success is True
    assert verification.gate.outcome == "success_within_scope"
    assert "manifest.legacy_gate_unsupported" not in _check_ids(verification)


def test_build_verification_defaults_do_not_change_existing_packet():
    raw, patched, report = _strict_case()
    baseline = build_verification(report, original=raw, patched=patched)
    explicit = build_verification(
        report,
        original=raw,
        patched=patched,
        external_poc=None,
        target_scope=None,
    )
    assert explicit.packet == baseline.packet
    assert explicit.gate == baseline.gate


# ---------------------------------------------------------------------------
# 2b. target_scope is accepted but cannot change legacy semantics
# ---------------------------------------------------------------------------


def test_build_verification_target_scope_note_is_non_required():
    raw, patched, report = _strict_case()
    verification = build_verification(
        report,
        original=raw,
        patched=patched,
        target_scope={"name": "main", "va": 0x1000, "end": 0x1100,
                      "source": "symbol"},
    )
    target_check = next(
        item
        for item in verification.packet["checks"]
        if item["id"] == "scope.target_scope"
    )
    assert target_check["required"] is False
    assert target_check["status"] == "not_run"
    # Legacy outcome is unchanged: the note is informational only.
    assert verification.gate.success is True
    assert verification.gate.outcome == "success_within_scope"
    assert verification.packet["report_sha256"] != STRICT_BASELINE_SHA256


def test_build_verification_signature_exposes_manifest_contract():
    parameters = set(inspect.signature(build_verification).parameters)
    assert {"external_poc", "target_scope"} <= parameters


# ---------------------------------------------------------------------------
# 3. Review path: manifest requests are unified-only
# ---------------------------------------------------------------------------


def test_review_path_manifest_routes_to_unified_profile_packet(monkeypatch):
    """A manifest request is judged by the unified evidence-profile gate only.

    The heap-guard fixture always takes the container-neutral generic path, so
    this is stable against pipeline routing changes around the legacy engine.
    """
    monkeypatch.setattr(
        poc_runner, "run_poc", lambda *a, **k: _FakeNativePocEvidence()
    )
    outcome = run_direct_repair(
        HEAP.read_bytes(), poc_manifest=_heap_manifest(),
        allow_whole_image=True,
    )

    packet = outcome.verification.packet
    ids = _check_ids(outcome.verification)
    statuses = _statuses(outcome.verification)

    # Unified evidence-profile packet, never a legacy packet.
    assert packet["schema_version"] == 2
    assert packet["scope"]["profile"] == "native_poc"
    for check_id in ("profile.declared", "profile.evidence", "profile.required_checks"):
        assert check_id in ids, check_id
    assert statuses["profile.evidence"] == "passed"
    assert statuses["profile.required_checks"] == "passed"
    assert "poc.native.available" in ids
    assert "strict.reviewed_template" not in ids
    assert "runtime.boundary_semantics" not in ids
    assert "manifest.legacy_gate_unsupported" not in ids

    # Routing is disclosed on the engine report and in the serialized payload.
    assert outcome.report.universal["manifest_routing"] == MANIFEST_ROUTING_UNIFIED
    assert outcome.decision["success"] is True
    payload = outcome.to_payload(filename="heap-fixed.elf")
    assert payload["manifest_routing"] == MANIFEST_ROUTING_UNIFIED
    assert payload["report"]["universal"]["manifest_routing"] == MANIFEST_ROUTING_UNIFIED
    assert payload["decision"]["success"] is True
    assert payload["patched_base64"]


def test_review_path_manifest_less_elf_is_legacy_readonly():
    outcome = run_direct_repair(VULN.read_bytes(), allow_whole_image=True)

    packet = outcome.verification.packet
    ids = _check_ids(outcome.verification)
    assert packet["schema_version"] == 1
    assert "strict.reviewed_template" in ids
    assert "profile.evidence" not in ids
    assert outcome.report.universal["manifest_routing"] == MANIFEST_ROUTING_LEGACY

    payload = outcome.to_payload(filename="vuln-fixed.elf")
    assert payload["manifest_routing"] == MANIFEST_ROUTING_LEGACY
    # The legacy report object itself does not serialize ``universal``; the
    # payload adds the routing explicitly for audit/CI.
    assert payload["report"]["universal"]["manifest_routing"] == MANIFEST_ROUTING_LEGACY


def test_review_path_manifest_never_surfaces_a_legacy_packet(monkeypatch):
    """Defensive backstop: even a regressed producer cannot leak a legacy packet."""
    legacy_packet = {
        "schema_version": 1,
        "scope": {"format": "elf", "arch": "x86_64"},
        "checks": [
            {"id": "format", "title": "format", "required": True,
             "status": "passed", "detail": ""},
            {"id": "strict.reviewed_template", "title": "template",
             "required": True, "status": "passed", "detail": ""},
        ],
        "missing": [],
        "limitations": [],
        "report_sha256": "0" * 64,
    }
    legacy_gate = {
        "success": True,
        "outcome": "success_within_scope",
        "reason": "",
        "required_checks": 2,
        "required_not_run": 0,
        "evidence_sha256": "0" * 64,
    }

    class _FakeOutcome:
        candidate = b"\x7fELF-regressed"
        report = SimpleNamespace(
            verification={"packet": legacy_packet, "gate": legacy_gate},
            universal={},
            format="elf",
            arch="x86_64",
            mode="strict",
            strategy="strict-template",
            limitations=[],
            error=None,
        )

    monkeypatch.setattr(binary_pipeline, "repair_any", lambda *a, **k: _FakeOutcome())
    outcome = run_direct_repair(VULN.read_bytes(), poc_manifest={"schema_version": 1})

    statuses = _statuses(outcome.verification)
    assert statuses.get("manifest.legacy_gate_unsupported") == "failed"
    assert "strict.reviewed_template" not in _check_ids(outcome.verification)
    assert outcome.verification.gate.success is False
    assert outcome.verification.gate.outcome == "rejected"
    assert outcome.decision["success"] is False
    assert outcome.report.universal["manifest_routing"] == MANIFEST_ROUTING_UNIFIED


# ---------------------------------------------------------------------------
# 4. HTTP review API: manifest upload is unified-only
# ---------------------------------------------------------------------------


def _client() -> TestClient:
    client = TestClient(app, base_url="http://127.0.0.1")
    response = client.get("/?token=" + SESSION_TOKEN)
    assert response.status_code == 200
    return client


def _post(client: TestClient, data: bytes, name: str, manifest: bytes | None = None):
    files = {"binary": (name, data, "application/octet-stream")}
    if manifest is not None:
        files["poc_manifest"] = (
            "marcx-capacity.json", manifest, "application/json"
        )
    return client.post(
        "/api/binary/repair-review",
        files=files,
        data={
            "csrf": CSRF_TOKEN,
            "ai_review": "0",
            # Manifest evidence is still unified-only; whole-image runs need the
            # explicit opt-in under the P0 safe default.
            "allow_whole_image": "1",
        },
    )


def test_api_manifest_upload_routes_unified(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    _patch_poc_runner(monkeypatch, "pass")
    client = _client()
    response = _post(
        client,
        MARCX.read_bytes(),
        "marcx",
        CAPACITY_MANIFEST.read_bytes(),
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["manifest_routing"] == MANIFEST_ROUTING_UNIFIED
    assert payload["report"]["universal"]["manifest_routing"] == MANIFEST_ROUTING_UNIFIED
    statuses = {
        check["id"]: check["status"] for check in payload["verification"]["checks"]
    }
    # A unified evidence-profile packet, never the legacy packet.
    for check_id in ("profile.declared", "profile.evidence", "profile.required_checks"):
        assert statuses.get(check_id) == "passed", check_id
    assert "strict.reviewed_template" not in statuses
    assert "runtime.boundary_semantics" not in statuses
    assert "manifest.legacy_gate_unsupported" not in statuses
    assert payload["decision"]["success"] is True
    assert payload["patched_base64"]


def test_api_manifest_validation_error_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("BINARYREPAIR_DATA_DIR", str(tmp_path / "var"))
    client = _client()
    for bad in (b"not json", b"[]", b'{"x": 1}' + b" " * (64 * 1024)):
        response = _post(client, VULN.read_bytes(), "vuln.elf", bad)
        assert response.status_code == 422, (bad[:30], response.status_code)
