"""Phase-8B B5/B6: pipeline patch-plan generation and plan-aware gate tests."""
from __future__ import annotations

import functools
import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

STACK = ROOT / "fixtures" / "elf" / "vuln-strcpy-x86_64.elf"
STACK_POC = ROOT / "fixtures" / "poc" / "elf-x86_64-strcpy.json"
HEAP = ROOT / "fixtures" / "elf" / "vuln-capacity-confusion-x86_64.elf"
HEAP_POC = ROOT / "fixtures" / "poc" / "marcx-capacity.json"
PATCH_PLAN_SCHEMA = ROOT / "contracts" / "patch-plan.schema.json"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@functools.lru_cache(maxsize=None)
def _stack_outcome():
    from app.services.binary_pipeline import repair_any
    from app.services.poc_runner import load_manifest

    if not STACK.is_file() or not STACK_POC.is_file():
        pytest.skip("stack fixture/poc missing")
    data = STACK.read_bytes()
    return data, repair_any(
        data, poc_manifest=load_manifest(STACK_POC), target="vuln_copy",
        require_target=True,
    )


@functools.lru_cache(maxsize=None)
def _heap_outcome():
    from app.services.binary_pipeline import repair_any
    from app.services.poc_runner import load_manifest

    if not HEAP.is_file() or not HEAP_POC.is_file():
        pytest.skip("heap fixture/poc missing")
    data = HEAP.read_bytes()
    return data, repair_any(
        data, poc_manifest=load_manifest(HEAP_POC),
        target={"va": 0x4020D9, "end": 0x4020E9}, require_target=True,
    )


def test_guard_candidate_emits_replayable_plan():
    jsonschema = pytest.importorskip("jsonschema")
    original, outcome = _stack_outcome()
    report = outcome.report
    plan = report.patch_plan
    assert outcome.verified is True and outcome.candidate is not None
    assert isinstance(plan, dict), report.error
    schema = json.loads(PATCH_PLAN_SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(plan), key=str)
    assert not errors, [error.message for error in errors]
    assert plan["target_sha256"] == _sha(original)
    assert plan["candidate_sha256"] == _sha(outcome.candidate)
    assert plan["scope_policy"] == "target_scoped_associated"
    reasons = [operation["reason"] for operation in plan["operations"]]
    assert "header_update" in reasons
    assert "reviewed_site" in reasons
    assert "guard_cave" in reasons
    reviewed = next(op for op in plan["operations"] if op["reason"] == "reviewed_site")
    assert reviewed["size"] == 5 and reviewed["after_hex"][:2] == "e8"
    insert = next(op for op in plan["operations"] if op["kind"] == "insert")
    cave = plan["cave"]
    assert cave and cave["executable"] is True and cave["method"]
    assert insert["size"] > cave["size"] > 0
    assert plan["abi_blocks"] and plan["abi_blocks"][0]["size"] > 0
    checks = {
        check["id"]: check["status"]
        for check in report.verification["packet"]["checks"]
    }
    assert checks["patch.rewrite"] == "passed"
    assert checks["patch.target_scope"] == "passed"


def test_capacity_candidate_emits_associated_plan():
    jsonschema = pytest.importorskip("jsonschema")
    original, outcome = _heap_outcome()
    report = outcome.report
    plan = report.patch_plan
    assert outcome.verified is True and outcome.candidate is not None
    schema = json.loads(PATCH_PLAN_SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(plan), key=str)
    assert not errors, [error.message for error in errors]
    assert plan["candidate_sha256"] == _sha(outcome.candidate)
    reasons = [operation["reason"] for operation in plan["operations"]]
    assert "reviewed_site" in reasons and "rodata_message" in reasons
    message = next(op for op in plan["operations"] if op["reason"] == "rodata_message")
    assert message["authorization_ref"], "associated rodata change must be authorized"
    assert plan["scope_policy"] == "target_scoped_associated"
    assert len(plan["abi_blocks"]) == 1
    assert plan["abi_blocks"][0]["size"] > 16, "ABI block must be the real function range"


def test_tampered_plan_is_rejected_by_the_gate():
    from app.services.unified_verification import build

    original, outcome = _heap_outcome()
    plan = json.loads(json.dumps(outcome.report.patch_plan))
    plan["operations"][0]["after_hex"] = "00" + plan["operations"][0]["after_hex"][2:]
    verification = build(
        format_name="elf", arch="x86_64", original=original,
        candidate=outcome.candidate, actions=outcome.report.actions,
        runtime=None, reparse_ok=True,
        original_sha256=_sha(original), patched_sha256=_sha(outcome.candidate),
        external_poc=outcome.report.poc, profile="native_poc_rewrite",
        rewrite_actions=outcome.report.actions,
        capacity=outcome.report.verification["packet"].get("capacity"),
        target_scope=outcome.report.universal.get("target_scope"),
        patch_plan=plan,
    )
    checks = {check["id"]: check for check in verification.packet["checks"]}
    assert checks["patch.rewrite"]["status"] == "failed"
    assert verification.gate.success is False


def test_plan_requires_authorization_for_associated_change():
    from app.services.unified_verification import build

    original, outcome = _heap_outcome()
    plan = json.loads(json.dumps(outcome.report.patch_plan))
    message = next(op for op in plan["operations"] if op["reason"] == "rodata_message")
    message.pop("authorization_ref", None)
    verification = build(
        format_name="elf", arch="x86_64", original=original,
        candidate=outcome.candidate, actions=outcome.report.actions,
        runtime=None, reparse_ok=True,
        original_sha256=_sha(original), patched_sha256=_sha(outcome.candidate),
        external_poc=outcome.report.poc, profile="native_poc_rewrite",
        rewrite_actions=outcome.report.actions,
        capacity=outcome.report.verification["packet"].get("capacity"),
        target_scope=outcome.report.universal.get("target_scope"),
        patch_plan=plan,
    )
    checks = {check["id"]: check for check in verification.packet["checks"]}
    assert checks["patch.rewrite"]["status"] == "failed"
    assert verification.gate.success is False


def test_cave_must_be_executable_and_mapped():
    from app.services.unified_verification import build

    original, outcome = _stack_outcome()
    plan = json.loads(json.dumps(outcome.report.patch_plan))
    plan["cave"]["executable"] = False
    verification = build(
        format_name="elf", arch="x86_64", original=original,
        candidate=outcome.candidate, actions=outcome.report.actions,
        runtime=None, reparse_ok=True,
        original_sha256=_sha(original), patched_sha256=_sha(outcome.candidate),
        external_poc=outcome.report.poc, profile="native_poc",
        target_scope=outcome.report.universal.get("target_scope"),
        patch_plan=plan,
    )
    checks = {check["id"]: check for check in verification.packet["checks"]}
    assert checks["patch.rewrite"]["status"] == "failed"
    assert verification.gate.success is False


def test_no_plan_candidate_keeps_legacy_gate_behavior():
    """Without a plan the legacy checks are emitted unchanged (no plan check)."""
    from app.services.unified_verification import build

    original, outcome = _heap_outcome()
    without_plan = build(
        format_name="elf", arch="x86_64", original=original,
        candidate=outcome.candidate, actions=outcome.report.actions,
        runtime=None, reparse_ok=True,
        original_sha256=_sha(original), patched_sha256=_sha(outcome.candidate),
        external_poc=outcome.report.poc, profile="native_poc_rewrite",
        rewrite_actions=outcome.report.actions,
        capacity=outcome.report.verification["packet"].get("capacity"),
        target_scope=outcome.report.universal.get("target_scope"),
    )
    with_plan = build(
        format_name="elf", arch="x86_64", original=original,
        candidate=outcome.candidate, actions=outcome.report.actions,
        runtime=None, reparse_ok=True,
        original_sha256=_sha(original), patched_sha256=_sha(outcome.candidate),
        external_poc=outcome.report.poc, profile="native_poc_rewrite",
        rewrite_actions=outcome.report.actions,
        capacity=outcome.report.verification["packet"].get("capacity"),
        target_scope=outcome.report.universal.get("target_scope"),
        patch_plan=outcome.report.patch_plan,
    )
    legacy_ids = {check["id"] for check in without_plan.packet["checks"]}
    plan_ids = {check["id"] for check in with_plan.packet["checks"]}
    assert "patch.rewrite" in legacy_ids
    assert plan_ids >= legacy_ids
    assert len(with_plan.packet["checks"]) >= len(without_plan.packet["checks"])
    assert without_plan.gate.success is True
    assert with_plan.gate.success is True
