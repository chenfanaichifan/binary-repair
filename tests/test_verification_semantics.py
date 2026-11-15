"""Tests for the pure Phase-8B verification semantics (plan replay/scope/ABI)."""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services import verification_semantics as semantics  # noqa: E402

ORIGINAL = bytes(range(256)) * 4


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _redirect(site_va: int, cave_va: int) -> bytes:
    return b"\xe9" + struct.pack("<i", cave_va - (site_va + 5))


def _container(*, rodata: bool = True) -> dict:
    sections = [
        {"name": ".text", "va": 0x401000, "size": 256, "offset": 0, "executable": True},
    ]
    if rodata:
        sections.append({"name": ".rodata", "va": 0x402000, "size": 128,
                         "offset": 256, "executable": False})
    return {
        "format": "elf", "arch": "x86_64", "bits": 64, "endian": "little",
        "sections": sections,
        "symbols": [{"va": 0x401000, "name": "vuln_fn"}],
    }


def _plan(original: bytes, candidate: bytes, operations: list[dict], **overrides) -> dict:
    plan = {
        "schema_version": 1,
        "candidate_id": "cand-test-semantics",
        "target_sha256": _sha(original),
        "candidate_sha256": _sha(candidate),
        "strategy": "reviewed_site",
        "scope_policy": "target_scoped",
        "target_scope": {"policy": "target_scoped", "name": "vuln_fn",
                         "va": 0x401000, "end": 0x401100},
        "operations": operations,
        "cave": None,
        "relocations": [],
        "abi_blocks": [],
        "oracle": None,
        "limitations": [],
    }
    plan.update(overrides)
    return plan


def _write(offset: int, before: bytes, after: bytes, **overrides) -> dict:
    operation = {
        "kind": "write",
        "original_offset": offset,
        "candidate_offset": None,
        "size": len(before),
        "before_hex": before.hex(),
        "after_hex": after.hex(),
        "site_va": 0x401020,
        "reason": "reviewed_site",
        "authorization_ref": None,
    }
    operation.update(overrides)
    return operation


def _equal_size_case():
    candidate = bytearray(ORIGINAL)
    candidate[32:40] = b"\x90" * 8
    candidate = bytes(candidate)
    operation = _write(32, ORIGINAL[32:40], candidate[32:40])
    return ORIGINAL, candidate, [_plan(ORIGINAL, candidate, [operation])], [operation]


def _resized_case():
    site_va = 0x401020
    redirect = _redirect(site_va, 0x500000)
    candidate = bytearray(ORIGINAL)
    candidate[32:37] = redirect
    appended = b"\x00" * 8 + b"\x31\xc0\xc3"
    candidate.extend(appended)
    candidate = bytes(candidate)
    operations = [
        _write(32, ORIGINAL[32:37], redirect),
        {"kind": "insert", "original_offset": len(ORIGINAL),
         "candidate_offset": len(ORIGINAL), "size": len(appended),
         "before_hex": "", "after_hex": appended.hex(), "site_va": site_va,
         "reason": "guard_cave", "authorization_ref": None},
    ]
    cave = {"va": 0x500000, "size": 3, "executable": True, "method": "test"}
    plan = _plan(ORIGINAL, candidate, operations,
                 scope_policy="target_scoped_associated",
                 target_scope={"policy": "target_scoped_associated", "name": "vuln_fn",
                               "va": 0x401000, "end": 0x401100},
                 cave=cave)
    return ORIGINAL, candidate, plan, operations


# ---------------------------------------------------------------------------
# Plan hash / structural validation
# ---------------------------------------------------------------------------


def test_canonical_plan_hash_is_stable_and_tamper_sensitive() -> None:
    _original, _candidate, plans, _ = _equal_size_case()
    plan = plans[0]
    first = semantics.canonical_plan_sha256(plan)
    second = semantics.canonical_plan_sha256(json.loads(json.dumps(plan)))
    assert first == second and len(first) == 64
    tampered = json.loads(json.dumps(plan))
    tampered["strategy"] = "changed"
    assert semantics.canonical_plan_sha256(tampered) != first


def test_invalid_plan_structure_fails() -> None:
    _original, candidate, plans, _ = _equal_size_case()
    bad = dict(plans[0])
    bad["schema_version"] = 2
    result = semantics.replay_plan(ORIGINAL, candidate, bad, _container())
    assert result["ok"] is False
    assert any("schema_version" in problem for problem in result["problems"])


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def test_equal_size_write_plan_replays_exactly() -> None:
    original, candidate, plans, _ = _equal_size_case()
    result = semantics.replay_plan(original, candidate, plans[0], _container())
    assert result["ok"] is True, result["problems"]
    assert result["changed_ranges"] == [{
        "original_offset": 32, "candidate_offset": 32, "size": 8, "kind": "write",
    }]
    assert result["plan_sha256"] == semantics.canonical_plan_sha256(plans[0])


def test_resized_insert_cave_plan_replays_exactly() -> None:
    original, candidate, plan, _ = _resized_case()
    result = semantics.replay_plan(original, candidate, plan, _container())
    assert result["ok"] is True, result["problems"]
    kinds = [item["kind"] for item in result["changed_ranges"]]
    assert kinds == ["write", "insert"]
    assert result["cave"]["executable"] is True


def test_after_hex_mismatch_fails_replay() -> None:
    original, candidate, plans, _ = _equal_size_case()
    tampered = json.loads(json.dumps(plans[0]))
    tampered["operations"][0]["after_hex"] = "00" + tampered["operations"][0]["after_hex"][2:]
    result = semantics.replay_plan(original, candidate, tampered, _container())
    assert result["ok"] is False
    assert any("candidate" in problem or "output" in problem for problem in result["problems"])


def test_before_hex_mismatch_fails_replay() -> None:
    original, candidate, plans, _ = _equal_size_case()
    tampered = json.loads(json.dumps(plans[0]))
    tampered["operations"][0]["before_hex"] = "00" * 8
    result = semantics.replay_plan(original, candidate, tampered, _container())
    assert result["ok"] is False
    assert any("before_hex" in problem for problem in result["problems"])


def test_undeclared_change_fails_replay() -> None:
    original, candidate, plans, _ = _equal_size_case()
    missing = json.loads(json.dumps(plans[0]))
    missing["operations"] = []
    result = semantics.replay_plan(original, candidate, missing, _container())
    assert result["ok"] is False


def test_overlapping_operations_fail_replay() -> None:
    original = ORIGINAL
    candidate = bytearray(original)
    candidate[32:40] = b"\x90" * 8
    candidate[36:44] = b"\xcc" * 8
    candidate = bytes(candidate)
    operations = [
        _write(32, original[32:40], candidate[32:40]),
        _write(36, original[36:44], candidate[36:44]),
    ]
    result = semantics.replay_plan(original, candidate, _plan(original, candidate, operations),
                                   _container())
    assert result["ok"] is False
    assert any("overlap" in problem for problem in result["problems"])


def test_out_of_bounds_operation_fails_replay() -> None:
    original, candidate, plans, _ = _equal_size_case()
    bad = json.loads(json.dumps(plans[0]))
    bad["operations"][0]["original_offset"] = len(original) - 4
    bad["operations"][0]["size"] = 8
    bad["operations"][0]["before_hex"] = original[-4:].hex() + "00" * 4
    bad["operations"][0]["after_hex"] = "90" * 8
    result = semantics.replay_plan(original, candidate, bad, _container())
    assert result["ok"] is False


def test_no_reviewed_site_is_rejected() -> None:
    original, candidate, plans, _ = _equal_size_case()
    bad = json.loads(json.dumps(plans[0]))
    bad["operations"][0]["reason"] = "header_update"
    bad["operations"][0]["authorization_ref"] = "test"
    result = semantics.replay_plan(original, candidate, bad, _container())
    assert result["ok"] is False
    assert any("reviewed_site" in problem for problem in result["problems"])


def test_noop_write_is_rejected() -> None:
    original = ORIGINAL
    candidate = bytearray(original)
    candidate[32:40] = b"\x90" * 8
    candidate = bytes(candidate)
    operation = _write(32, original[32:40], original[32:40])
    result = semantics.replay_plan(original, candidate, _plan(original, candidate, [operation]),
                                   _container())
    assert result["ok"] is False
    assert any("no-op" in problem for problem in result["problems"])


# ---------------------------------------------------------------------------
# Associated changes
# ---------------------------------------------------------------------------


def _associated_case():
    original = ORIGINAL
    candidate = bytearray(original)
    candidate[32:40] = b"\x90" * 8
    candidate[260:268] = bytes((byte ^ 0xFF) for byte in original[260:268])
    candidate = bytes(candidate)
    operations = [
        _write(32, original[32:40], candidate[32:40]),
        {
            "kind": "write", "original_offset": 260, "candidate_offset": None,
            "size": 8, "before_hex": original[260:268].hex(),
            "after_hex": candidate[260:268].hex(), "site_va": None,
            "reason": "rodata_message", "authorization_ref": "test:rodata-message",
        },
    ]
    plan = _plan(original, candidate, operations,
                 scope_policy="target_scoped_associated",
                 target_scope={"policy": "target_scoped_associated", "name": "vuln_fn",
                               "va": 0x401000, "end": 0x401100})
    return original, candidate, plan, operations


def test_associated_rodata_change_is_replayed_and_section_checked() -> None:
    original, candidate, plan, _ = _associated_case()
    result = semantics.replay_plan(original, candidate, plan, _container())
    assert result["ok"] is True, result["problems"]
    assert result["changed_ranges"][1]["kind"] == "associated"
    assert result["associated_changes"] == [{
        "kind": "rodata_message", "offset": 260, "size": 8,
        "section": ".rodata", "authorization_ref": "test:rodata-message",
    }]


def test_associated_change_requires_authorization_ref() -> None:
    original, candidate, plan, _ = _associated_case()
    plan = json.loads(json.dumps(plan))
    plan["operations"][1]["authorization_ref"] = None
    result = semantics.replay_plan(original, candidate, plan, _container())
    assert result["ok"] is False
    assert any("authorization_ref" in problem for problem in result["problems"])


def test_rodata_message_cannot_target_executable_section() -> None:
    original, candidate, plan, _ = _associated_case()
    changed = bytearray(candidate)
    changed[40:48] = bytes((byte ^ 0x55) for byte in original[40:48])
    changed = bytes(changed)
    plan = json.loads(json.dumps(plan))
    plan["candidate_sha256"] = _sha(changed)
    plan["operations"][1]["original_offset"] = 40
    plan["operations"][1]["size"] = 8
    plan["operations"][1]["before_hex"] = original[40:48].hex()
    plan["operations"][1]["after_hex"] = changed[40:48].hex()
    result = semantics.replay_plan(original, changed, plan, _container())
    assert result["ok"] is False
    assert any("executable" in problem for problem in result["problems"])


def test_associated_scope_policy_required() -> None:
    original, candidate, plan, _ = _associated_case()
    plan = json.loads(json.dumps(plan))
    plan["scope_policy"] = "target_scoped"
    plan["target_scope"]["policy"] = "target_scoped"
    result = semantics.replay_plan(original, candidate, plan, _container())
    assert result["ok"] is True  # replay itself is fine; scope validation is separate
    scope = semantics.validate_scope(plan, result, _container())
    assert scope["status"] == "failed"
    assert any("target_scoped_associated" in problem for problem in scope["problems"])


# ---------------------------------------------------------------------------
# Scope validation
# ---------------------------------------------------------------------------


def test_scope_passes_for_reviewed_site_in_target_function() -> None:
    original, candidate, plans, _ = _equal_size_case()
    replay = semantics.replay_plan(original, candidate, plans[0], _container())
    scope = semantics.validate_scope(plans[0], replay, _container())
    assert scope["status"] == "passed", scope["problems"]


def test_scope_escape_is_failed() -> None:
    original = ORIGINAL
    candidate = bytearray(original)
    candidate[260:268] = bytes((byte ^ 0xFF) for byte in original[260:268])
    candidate = bytes(candidate)
    operation = _write(260, original[260:268], candidate[260:268], site_va=0x402000)
    plan = _plan(original, candidate, [operation])
    replay = semantics.replay_plan(original, candidate, plan, _container())
    assert replay["ok"] is True
    scope = semantics.validate_scope(plan, replay, _container())
    assert scope["status"] == "failed"
    assert any("escapes" in problem for problem in scope["problems"])


def test_guard_cave_requires_executable_cave_and_redirect() -> None:
    original, candidate, plan, _ = _resized_case()
    replay = semantics.replay_plan(original, candidate, plan, _container())
    scope = semantics.validate_scope(plan, replay, _container())
    assert scope["status"] == "passed", scope["problems"]

    non_exec = json.loads(json.dumps(plan))
    non_exec["cave"]["executable"] = False
    scope = semantics.validate_scope(non_exec, replay, _container())
    assert scope["status"] == "failed"

    no_redirect = json.loads(json.dumps(plan))
    no_redirect["operations"][0]["after_hex"] = "90" * 5
    # Replay already fails for that operation; construct a matching replay shape.
    replay_no_redirect = json.loads(json.dumps(replay))
    replay_no_redirect["ok"] = True
    replay_no_redirect["problems"] = []
    scope = semantics.validate_scope(no_redirect, replay_no_redirect, _container())
    assert scope["status"] == "failed"
    assert any("reachable" in problem for problem in scope["problems"])


def test_whole_image_and_analysis_only_never_verified() -> None:
    original, candidate, plans, _ = _equal_size_case()
    replay = semantics.replay_plan(original, candidate, plans[0], _container())
    whole = json.loads(json.dumps(plans[0]))
    whole["scope_policy"] = "whole_image"
    whole["target_scope"] = {"policy": "whole_image"}
    scope = semantics.validate_scope(whole, replay, _container())
    assert scope["status"] == "failed"
    analysis = json.loads(json.dumps(plans[0]))
    analysis["scope_policy"] = "analysis_only"
    analysis["target_scope"] = {"policy": "analysis_only"}
    scope = semantics.validate_scope(analysis, replay, _container())
    assert scope["status"] == "not_run"


def test_unresolved_symbol_scope_is_not_run() -> None:
    original, candidate, plans, _ = _equal_size_case()
    unresolved = json.loads(json.dumps(plans[0]))
    unresolved["target_scope"] = {"policy": "target_scoped", "name": "unknown_symbol"}
    replay = semantics.replay_plan(original, candidate, unresolved, _container())
    scope = semantics.validate_scope(unresolved, replay, _container())
    assert scope["status"] == "not_run"


# ---------------------------------------------------------------------------
# ABI derivation
# ---------------------------------------------------------------------------


def test_abi_blocks_derive_from_plan_with_evidence_sha() -> None:
    original, candidate, plans, _ = _equal_size_case()
    plan = json.loads(json.dumps(plans[0]))
    plan["abi_blocks"] = [{
        "function": "vuln_fn", "va": 0x401000, "size": 64, "arch": "x86_64",
        "evidence_sha256": _sha(candidate[0:64]),
    }]
    result = semantics.derive_abi_blocks(plan, original, candidate, _container(), {})
    assert result["status"] == "ok"
    assert result["blocks"][0]["source"] == "plan.abi_blocks"
    assert result["blocks"][0]["file_offset"] == 0

    tampered = json.loads(json.dumps(plan))
    tampered["abi_blocks"][0]["evidence_sha256"] = "0" * 64
    replay = semantics.replay_plan(original, candidate, tampered, _container())
    assert replay["ok"] is False
    assert any("evidence_sha256" in problem for problem in replay["problems"])


def test_abi_blocks_fall_back_to_metadata_block() -> None:
    original, candidate, plans, _ = _equal_size_case()
    plan = plans[0]
    result = semantics.derive_abi_blocks(
        plan, original, candidate, _container(),
        {"arch": "x86_64", "abi_block": {"offset": 32, "size": 8}},
    )
    assert result["status"] == "ok"
    assert result["blocks"][0]["source"] == "metadata.abi_block"


def test_abi_blocks_derive_from_symbol_backed_function() -> None:
    original, candidate, plans, _ = _equal_size_case()
    result = semantics.derive_abi_blocks(
        plans[0], original, candidate, _container(), {"arch": "x86_64"},
    )
    assert result["status"] == "ok"
    assert result["blocks"][0]["source"] == "symbol_function"
    assert result["blocks"][0]["function"] == "vuln_fn"
    assert result["blocks"][0]["size"] == 256


def test_abi_blocks_not_run_without_any_source() -> None:
    original, candidate, plans, _ = _equal_size_case()
    container = {"format": "elf", "arch": "x86_64", "bits": 64, "endian": "little",
                 "sections": [{"name": ".text", "va": 0x401000, "size": 256,
                               "offset": 0, "executable": True}],
                 "symbols": []}
    result = semantics.derive_abi_blocks(plans[0], original, candidate, container,
                                         {"arch": "x86_64"})
    assert result["status"] == "not_run"
    assert result["blocks"] == []


def test_abi_blocks_derive_from_guard_cave_inserted_bytes() -> None:
    original, candidate, plan, _ = _resized_case()
    container = {"format": "elf", "arch": "x86_64", "bits": 64, "endian": "little",
                 "sections": [{"name": ".text", "va": 0x401000, "size": 256,
                               "offset": 0, "executable": True}],
                 "symbols": []}
    result = semantics.derive_abi_blocks(plan, original, candidate, container,
                                         {"arch": "x86_64"})
    assert result["status"] == "ok"
    assert result["blocks"][0]["source"] == "cave.inserted"
    assert bytes.fromhex(result["blocks"][0]["block_hex"]) == b"\x31\xc0\xc3"


# ---------------------------------------------------------------------------
# Real B1 artifact replay (read-only)
# ---------------------------------------------------------------------------


def _b1_heap_plan() -> tuple[bytes, bytes, dict]:
    sample = ROOT / "artifacts/phase8b-baseline-2026-11-16/disagreement-heap-capacity-x86_64"
    if not sample.is_dir():
        import pytest

        pytest.skip("B1 heap artifact is not present in this checkout")
    original = (sample / "original.elf").read_bytes()
    candidate = (sample / "candidate.bin").read_bytes()
    outcome = json.loads((sample / "outcome.json").read_text(encoding="utf-8"))
    action = outcome["reproduction"]["actions"][0]
    message = outcome["reproduction"]["message_actions"][0]
    plan = _plan(
        original, candidate,
        [
            {"kind": "write", "original_offset": action["offset"], "candidate_offset": None,
             "size": action["size"], "before_hex": action["before_hex"],
             "after_hex": action["after_hex"], "site_va": action["site_va"],
             "reason": "reviewed_site", "authorization_ref": None},
            {"kind": "write", "original_offset": message["offset"],
             "candidate_offset": None, "size": message["size"],
             "before_hex": message["before_hex"], "after_hex": message["after_hex"],
             "site_va": None, "reason": "rodata_message",
             "authorization_ref": "phase8b:capacity-message-align"},
        ],
        scope_policy="target_scoped_associated",
        target_scope={"policy": "target_scoped_associated", "name": "capacity_site",
                      "va": 4202713, "end": 4202729},
    )
    return original, candidate, plan


def test_b1_heap_artifact_replays_and_scopes() -> None:
    from app.services.containers import detect_container

    original, candidate, plan = _b1_heap_plan()
    container = detect_container(original)
    view = {
        "format": container.format, "arch": container.arch, "bits": container.bits,
        "endian": container.endian,
        "sections": [{"name": s.name, "va": s.va, "size": s.size, "offset": s.offset,
                      "executable": s.executable} for s in container.sections],
        "symbols": [{"va": va, "name": name} for va, name in sorted(container.symbols.items())],
    }
    replay = semantics.replay_plan(original, candidate, plan, view)
    assert replay["ok"] is True, replay["problems"]
    assert replay["associated_changes"][0]["section"] == ".rodata"
    scope = semantics.validate_scope(plan, replay, view)
    assert scope["status"] == "passed", scope["problems"]
