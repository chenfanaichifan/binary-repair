"""Pure verification semantics for layout-aware repair candidates.

Phase-8B B2: the independent verifier needs to reason about a repair that is
more than a same-size byte rewrite - an insertion/cave candidate (resized) and
declared *associated* changes outside the target function (e.g. a ``.rodata``
message alignment or a program-header update).

This module is deliberately pure: no AI, no network, no subprocess, no clock and
no global state.  It consumes the raw original/candidate bytes, a patch plan
(the ``contracts/patch-plan.schema.json`` shape) and a parsed container view and
returns deterministic dictionaries.

Hard rules (fail closed):

* a plan must replay from the original bytes to the candidate bytes exactly;
  any undeclared raw difference, mismatched before/after slice, overlap,
  out-of-bounds operation or no-op operation fails;
* an insertion/guard-cave plan needs an executable cave and a reviewed target
  site inside the declared target scope whose control flow redirects into the
  cave; the target site must exist in the target function;
* associated changes (``rodata_message``/``header_update``/``relocation``) are
  only allowed for ``target_scoped_associated`` plans, need an
  ``authorization_ref`` and are bounds/content checked; a ``rodata_message``
  change must live in a real, non-executable section;
* ``whole_image`` can never be treated as verified in Phase-8B and
  ``analysis_only`` is not verifiable;
* ABI blocks are derived from declared ``abi_blocks``, the resolved function or
  the target-scope range; an unmappable block yields ``not_run`` (explicit), not
  a fabricated pass.

The verifier stays authoritative: this module only derives facts.
"""

from __future__ import annotations

import hashlib
import json
import struct
from typing import Any, Iterable

PLAN_SCHEMA_VERSION = 1
OPERATION_KINDS = ("write", "insert", "replace")
OPERATION_REASONS = (
    "reviewed_site",
    "guard_cave",
    "rodata_message",
    "header_update",
    "relocation",
)
ASSOCIATED_REASONS = ("rodata_message", "header_update", "relocation")
SCOPE_POLICIES = (
    "target_scoped",
    "target_scoped_associated",
    "whole_image",
    "analysis_only",
)
ABI_ARCHES = ("x86_64", "i386", "arm64")
ORACLE_TIERS = ("native_run", "emulated_run", "static_only", "unavailable")
ORACLE_STATUSES = ("executed", "not_run", "unavailable")
REPLAY_KINDS = ("write", "insert", "replace", "associated")
HEX_DIGITS = set("0123456789abcdef")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_plan_sha256(plan: dict[str, Any]) -> str:
    """Stable sha256 of the plan (used as ``patch_plan_sha256``)."""
    return sha256_bytes(canonical_json(plan).encode("ascii"))


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _hex_bytes(value: Any) -> bytes | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if len(text) % 2 or any(char not in HEX_DIGITS for char in text):
        return None
    return bytes.fromhex(text)


def _section_at(container: dict[str, Any] | None, offset: int) -> dict[str, Any] | None:
    if not isinstance(container, dict):
        return None
    for section in container.get("sections") or []:
        try:
            start = int(section.get("offset", 0))
            size = int(section.get("size", 0))
        except (TypeError, ValueError):
            continue
        if start <= offset < start + max(size, 1):
            return section
    return None


def offset_to_va(container: dict[str, Any] | None, offset: int) -> int | None:
    section = _section_at(container, offset)
    if section is None:
        return None
    try:
        return int(section.get("va", 0)) + (offset - int(section.get("offset", 0)))
    except (TypeError, ValueError):
        return None


def va_to_offset(container: dict[str, Any] | None, va: int) -> int | None:
    if not isinstance(container, dict):
        return None
    for section in container.get("sections") or []:
        try:
            start_va = int(section.get("va", 0))
            size = int(section.get("size", 0))
            start_off = int(section.get("offset", 0))
        except (TypeError, ValueError):
            continue
        if start_va <= va < start_va + max(size, 1):
            return start_off + (va - start_va)
    return None


def _section_name_at(container: dict[str, Any] | None, offset: int,
                     *, fallback: str = "elf_header") -> str:
    section = _section_at(container, offset)
    if section is None:
        return fallback
    return str(section.get("name") or fallback)


def _first_section_offset(container: dict[str, Any] | None) -> int:
    if not isinstance(container, dict):
        return 0
    offsets = []
    for section in container.get("sections") or []:
        try:
            offsets.append(int(section.get("offset", 0)))
        except (TypeError, ValueError):
            continue
    return min(offsets) if offsets else 0


def _normalize_plan(plan: Any) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    if not isinstance(plan, dict):
        return {}, ["patch plan must be a JSON object"]
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        problems.append("patch plan schema_version must be 1")
    for field in ("candidate_id", "target_sha256", "candidate_sha256", "strategy",
                  "scope_policy", "target_scope", "operations", "cave",
                  "relocations", "abi_blocks", "oracle", "limitations"):
        if field not in plan:
            problems.append(f"patch plan is missing required field {field!r}")
    candidate_id = plan.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id.startswith("cand-"):
        problems.append("patch plan candidate_id must match 'cand-...'")
    if plan.get("scope_policy") not in SCOPE_POLICIES:
        problems.append("patch plan scope_policy is invalid")
    target_scope = plan.get("target_scope")
    if not isinstance(target_scope, dict) or target_scope.get("policy") not in SCOPE_POLICIES:
        problems.append("patch plan target_scope.policy is invalid")
    if not isinstance(plan.get("strategy"), str) or not plan.get("strategy"):
        problems.append("patch plan strategy must be a non-empty string")
    if not isinstance(plan.get("limitations"), list):
        problems.append("patch plan limitations must be a list")
    cave = plan.get("cave")
    if cave is not None:
        if not isinstance(cave, dict):
            problems.append("patch plan cave must be an object or null")
        else:
            if not _is_int(cave.get("va")) or int(cave["va"]) < 0:
                problems.append("patch plan cave.va must be a non-negative integer")
            if not _is_int(cave.get("size")) or int(cave["size"]) < 1:
                problems.append("patch plan cave.size must be a positive integer")
            if not isinstance(cave.get("executable"), bool):
                problems.append("patch plan cave.executable must be a boolean")
            if not isinstance(cave.get("method"), str) or not cave.get("method"):
                problems.append("patch plan cave.method must be a non-empty string")
    oracle = plan.get("oracle")
    if oracle is not None:
        if not isinstance(oracle, dict):
            problems.append("patch plan oracle must be an object or null")
        else:
            if not isinstance(oracle.get("manifest_sha256"), str):
                problems.append("patch plan oracle.manifest_sha256 is required")
            if not isinstance(oracle.get("runner"), str) or not oracle.get("runner"):
                problems.append("patch plan oracle.runner is required")
            if oracle.get("tier") not in ORACLE_TIERS:
                problems.append("patch plan oracle.tier is invalid")
            if "status" in oracle and oracle["status"] not in ORACLE_STATUSES:
                problems.append("patch plan oracle.status is invalid")
    operations = plan.get("operations")
    if not isinstance(operations, list) or not operations:
        problems.append("patch plan operations must be a non-empty array")
        operations = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            problems.append(f"operation[{index}] is not an object")
            continue
        if operation.get("kind") not in OPERATION_KINDS:
            problems.append(f"operation[{index}].kind is invalid")
        if operation.get("reason") not in OPERATION_REASONS:
            problems.append(f"operation[{index}].reason is invalid")
        if not _is_int(operation.get("original_offset")) or int(operation["original_offset"]) < 0:
            problems.append(f"operation[{index}].original_offset is invalid")
        if not _is_int(operation.get("size")) or int(operation["size"]) < 1:
            problems.append(f"operation[{index}].size is invalid")
        if _hex_bytes(operation.get("before_hex")) is None:
            problems.append(f"operation[{index}].before_hex is invalid hex")
        if _hex_bytes(operation.get("after_hex")) is None:
            problems.append(f"operation[{index}].after_hex is invalid hex")
        if operation.get("kind") == "insert":
            before = _hex_bytes(operation.get("before_hex"))
            if before:
                problems.append(f"operation[{index}] insert must have empty before_hex")
        if operation.get("reason") in ASSOCIATED_REASONS:
            auth = operation.get("authorization_ref")
            if not isinstance(auth, str) or not auth.strip():
                problems.append(
                    f"operation[{index}] associated reason {operation.get('reason')!r} "
                    "requires a non-empty authorization_ref"
                )
    relocations = plan.get("relocations")
    if not isinstance(relocations, list):
        problems.append("patch plan relocations must be an array")
        relocations = []
    for index, relocation in enumerate(relocations):
        if not isinstance(relocation, dict):
            problems.append(f"relocation[{index}] is not an object")
            continue
        if not _is_int(relocation.get("offset")) or int(relocation["offset"]) < 0:
            problems.append(f"relocation[{index}].offset is invalid")
        if not _is_int(relocation.get("size")) or int(relocation["size"]) < 1:
            problems.append(f"relocation[{index}].size is invalid")
        if not isinstance(relocation.get("kind"), str) or not relocation.get("kind"):
            problems.append(f"relocation[{index}].kind is required")
    abi_blocks = plan.get("abi_blocks")
    if not isinstance(abi_blocks, list):
        problems.append("patch plan abi_blocks must be an array")
        abi_blocks = []
    for index, block in enumerate(abi_blocks):
        if not isinstance(block, dict):
            problems.append(f"abi_blocks[{index}] is not an object")
            continue
        if not _is_int(block.get("va")) or int(block["va"]) < 0:
            problems.append(f"abi_blocks[{index}].va is invalid")
        if not _is_int(block.get("size")) or int(block["size"]) < 1:
            problems.append(f"abi_blocks[{index}].size is invalid")
        if block.get("arch") not in ABI_ARCHES:
            problems.append(f"abi_blocks[{index}].arch is invalid")
    return plan, problems


def replay_plan(
    original: bytes,
    candidate: bytes,
    plan: dict[str, Any],
    container: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay a patch plan from the original bytes and require candidate equality."""
    plan, problems = _normalize_plan(plan)
    if not isinstance(plan, dict) or not plan:
        return {
            "ok": False, "problems": problems, "plan_sha256": canonical_plan_sha256(plan or {}),
            "changed_ranges": [], "cave": None, "associated_changes": [],
            "relocations": [], "abi_blocks": [], "oracle": None,
            "operations": 0, "limitations": [],
        }
    original_sha = sha256_bytes(original)
    candidate_sha = sha256_bytes(candidate)
    for field, expected in (("target_sha256", original_sha), ("candidate_sha256", candidate_sha)):
        declared = plan.get(field)
        if isinstance(declared, str) and declared.lower() != expected:
            problems.append(f"plan {field} does not match the raw bytes")
    if isinstance(plan.get("original_sha256"), str) and plan["original_sha256"].lower() != original_sha:
        problems.append("plan original_sha256 does not match the raw original bytes")

    operations = plan.get("operations") or []
    ordered: list[tuple[int, int, dict[str, Any]]] = []
    for index, operation in enumerate(operations):
        if isinstance(operation, dict):
            try:
                ordered.append((int(operation.get("original_offset", 0)), index, operation))
            except (TypeError, ValueError):
                problems.append(f"operation[{index}] has an invalid original_offset")
    ordered.sort(key=lambda item: (item[0], item[1]))

    cave = plan.get("cave") if isinstance(plan.get("cave"), dict) else None
    output = bytearray()
    cursor = 0
    changed_ranges: list[dict[str, Any]] = []
    associated_changes: list[dict[str, Any]] = []
    consumed_until = 0
    seen_reasons: set[str] = set()
    header_boundary = max(4096, _first_section_offset(container))
    for position, (original_offset, index, operation) in enumerate(ordered):
        kind = str(operation.get("kind") or "")
        reason = str(operation.get("reason") or "")
        seen_reasons.add(reason)
        size = int(operation.get("size") or 0)
        before = _hex_bytes(operation.get("before_hex")) or b""
        after = _hex_bytes(operation.get("after_hex")) or b""
        if original_offset < cursor:
            problems.append(
                f"operation[{index}] original_offset 0x{original_offset:x} overlaps a "
                "previously consumed range"
            )
            continue
        if kind != "insert" and original_offset < consumed_until:
            problems.append(f"operation[{index}] overlaps a previously consumed range")
            continue
        output.extend(original[cursor:original_offset])
        cursor = original_offset
        if kind in {"write", "replace"}:
            if original_offset + size > len(original):
                problems.append(f"operation[{index}] is outside the original bytes")
                continue
            if original[original_offset:original_offset + size] != before:
                problems.append(
                    f"operation[{index}] before_hex does not match the original bytes at "
                    f"0x{original_offset:x}"
                )
                continue
            if len(before) != size:
                problems.append(f"operation[{index}] before_hex length does not match size")
                continue
            if kind == "write" and len(after) != size:
                problems.append(f"operation[{index}] write after_hex length must equal size")
                continue
            candidate_offset = operation.get("candidate_offset")
            if candidate_offset is not None:
                if not _is_int(candidate_offset) or int(candidate_offset) != len(output):
                    problems.append(
                        f"operation[{index}] candidate_offset does not match the replayed "
                        f"position 0x{len(output):x}"
                    )
                    continue
            if before == after:
                problems.append(f"operation[{index}] is a no-op write/replace")
                continue
            applied_offset = len(output)
            output.extend(after)
            cursor = original_offset + size
            consumed_until = max(consumed_until, cursor)
            range_kind = "associated" if reason in ASSOCIATED_REASONS else kind
            changed_ranges.append({
                "original_offset": original_offset,
                "candidate_offset": applied_offset,
                "size": size,
                "kind": range_kind,
            })
            if reason in ASSOCIATED_REASONS:
                section_name = _section_name_at(container, original_offset)
                associated_changes.append({
                    "kind": reason,
                    "offset": original_offset,
                    "size": size,
                    "section": section_name,
                    "authorization_ref": str(operation.get("authorization_ref") or ""),
                })
                if reason == "rodata_message":
                    section = _section_at(container, original_offset)
                    if section is None:
                        problems.append(
                            f"operation[{index}] rodata_message offset 0x{original_offset:x} "
                            "is not inside a known section"
                        )
                    else:
                        if bool(section.get("executable")):
                            problems.append(
                                f"operation[{index}] rodata_message is inside executable "
                                f"section {section.get('name')!r}"
                            )
                        try:
                            section_start = int(section.get("offset", 0))
                            section_size = int(section.get("size", 0))
                        except (TypeError, ValueError):
                            section_start, section_size = 0, 0
                        if (original_offset < section_start
                                or original_offset + size > section_start + section_size):
                            problems.append(
                                f"operation[{index}] rodata_message escapes section "
                                f"{section.get('name')!r}"
                            )
                elif reason == "header_update":
                    if original_offset >= header_boundary:
                        problems.append(
                            f"operation[{index}] header_update offset 0x{original_offset:x} "
                            "is outside the header region"
                        )
                    section = _section_at(container, original_offset)
                    if section is not None and bool(section.get("executable")):
                        problems.append(
                            f"operation[{index}] header_update is inside an executable section"
                        )
        elif kind == "insert":
            if len(after) != size:
                problems.append(f"operation[{index}] insert after_hex length must equal size")
                continue
            if not after:
                problems.append(f"operation[{index}] insert must insert bytes")
                continue
            candidate_offset = operation.get("candidate_offset")
            if candidate_offset is not None:
                if not _is_int(candidate_offset) or int(candidate_offset) != len(output):
                    problems.append(
                        f"operation[{index}] candidate_offset does not match the replayed "
                        f"position 0x{len(output):x}"
                    )
                    continue
            applied_offset = len(output)
            output.extend(after)
            changed_ranges.append({
                "original_offset": original_offset,
                "candidate_offset": applied_offset,
                "size": size,
                "kind": "insert",
            })
            if reason == "guard_cave":
                if cave is None:
                    problems.append(f"operation[{index}] guard_cave requires a plan cave")
                elif not bool(cave.get("executable")):
                    problems.append(f"operation[{index}] guard_cave cave is not executable")
    output.extend(original[cursor:])
    if bytes(output) != candidate:
        first = next(
            (index for index in range(min(len(output), len(candidate)))
             if output[index] != candidate[index]),
            min(len(output), len(candidate)),
        )
        problems.append(
            "replayed output does not equal the candidate bytes "
            f"(first mismatch at 0x{first:x}; replay={len(output)} candidate={len(candidate)})"
        )
    if not changed_ranges and bytes(output) == candidate:
        problems.append("patch plan declares no changed range")
    if not any(range_item["kind"] in {"write", "insert", "replace"} for range_item in changed_ranges):
        problems.append("patch plan declares no in-scope write/insert/replace operation")
    if "reviewed_site" not in seen_reasons:
        problems.append("patch plan has no reviewed_site operation")
    if cave is not None and not any(
        operation.get("reason") == "guard_cave" or operation.get("kind") == "insert"
        for operation in operations if isinstance(operation, dict)
    ):
        problems.append("plan declares a cave without any insertion/guard_cave operation")

    # Relocations must be covered by a relocation operation; sections must agree.
    relocation_ops = [
        operation for operation in operations
        if isinstance(operation, dict) and operation.get("reason") == "relocation"
    ]
    for index, relocation in enumerate(plan.get("relocations") or []):
        if not isinstance(relocation, dict):
            continue
        try:
            offset = int(relocation.get("offset"))
            size = int(relocation.get("size"))
        except (TypeError, ValueError):
            continue
        covered = any(
            int(operation.get("original_offset", 0)) <= offset
            and offset + size <= int(operation.get("original_offset", 0)) + int(operation.get("size", 0))
            for operation in relocation_ops
        )
        if not covered:
            problems.append(f"relocation[{index}] is not covered by a relocation operation")
        declared_section = relocation.get("section")
        if isinstance(declared_section, str) and declared_section:
            actual = _section_name_at(container, offset, fallback="")
            if actual and actual != declared_section:
                problems.append(
                    f"relocation[{index}] section {declared_section!r} does not contain "
                    f"offset 0x{offset:x}"
                )

    # ABI blocks: structural checks only; mapping/derivation is the verifier's job.
    for index, block in enumerate(plan.get("abi_blocks") or []):
        if not isinstance(block, dict):
            continue
        evidence_sha = block.get("evidence_sha256")
        if isinstance(evidence_sha, str):
            file_offset = va_to_offset(container, int(block.get("va") or 0))
            size = int(block.get("size") or 0)
            if file_offset is not None:
                chunk = candidate[file_offset:file_offset + size]
                if len(chunk) == size and sha256_bytes(chunk) != evidence_sha.lower():
                    problems.append(f"abi_blocks[{index}] evidence_sha256 does not match the candidate block")

    return {
        "ok": not problems,
        "problems": problems,
        "plan_sha256": canonical_plan_sha256(plan),
        "operations": len(operations),
        "changed_ranges": changed_ranges,
        "cave": cave,
        "associated_changes": associated_changes,
        "relocations": list(plan.get("relocations") or []),
        "abi_blocks": list(plan.get("abi_blocks") or []),
        "oracle": plan.get("oracle"),
        "original_sha256": original_sha,
        "candidate_sha256": candidate_sha,
        "limitations": list(plan.get("limitations") or []),
    }


def _branch_targets(code: bytes, site_va: int) -> set[int]:
    targets: set[int] = set()
    for index in range(0, max(0, len(code) - 4)):
        opcode = code[index]
        if opcode in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", code, index + 1)[0]
            targets.add(site_va + index + 5 + rel)
    return targets


def _scope_symbol_end(container: dict[str, Any] | None, name: str) -> tuple[int, int] | None:
    symbols = []
    for symbol in (container or {}).get("symbols") or []:
        try:
            symbols.append((int(symbol.get("va", 0)), str(symbol.get("name") or "")))
        except (TypeError, ValueError):
            continue
    symbols.sort()
    for index, (va, symbol_name) in enumerate(symbols):
        if symbol_name == name:
            end = symbols[index + 1][0] if index + 1 < len(symbols) else va
            return va, end
    return None


def validate_scope(
    plan: dict[str, Any],
    replay: dict[str, Any],
    container: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate the declared scope and the cave/associated-change rules."""
    problems: list[str] = []
    policy = str(plan.get("scope_policy") or "")
    target_scope = plan.get("target_scope") if isinstance(plan.get("target_scope"), dict) else {}
    policy_value = str(target_scope.get("policy") or policy)
    if policy_value != policy:
        problems.append("scope_policy and target_scope.policy disagree")
    if policy_value == "whole_image":
        problems.append(
            "whole_image scope cannot be independently verified in Phase-8B; "
            "a whole-image claim is never verified"
        )
        return {
            "ok": False, "status": "failed", "policy": policy_value,
            "problems": problems, "target_scope": target_scope,
            "detail": "; ".join(problems),
        }
    if policy_value == "analysis_only":
        return {
            "ok": False, "status": "not_run", "policy": policy_value,
            "problems": ["analysis_only plan has no verifiable candidate scope"],
            "target_scope": target_scope,
            "detail": "analysis_only plan: no candidate verification is claimed",
        }
    scope_va = target_scope.get("va")
    scope_end = target_scope.get("end")
    if not (_is_int(scope_va) and _is_int(scope_end) and int(scope_end) > int(scope_va)):
        name = str(target_scope.get("name") or "")
        resolved = _scope_symbol_end(container, name) if name else None
        if resolved is None:
            detail = (
                "target scope has no resolved va/end and the symbol cannot be resolved; "
                "an unresolved target scope is not verifiable"
            )
            return {
                "ok": False, "status": "not_run", "policy": policy_value,
                "problems": [detail], "target_scope": target_scope, "detail": detail,
            }
        scope_va, scope_end = resolved
    scope_start = int(scope_va)
    scope_end = int(scope_end)

    operations = [operation for operation in (plan.get("operations") or [])
                  if isinstance(operation, dict)]
    reviewed_sites = [operation for operation in operations
                      if operation.get("reason") == "reviewed_site"]
    if not reviewed_sites:
        problems.append("target_scoped plan requires at least one reviewed_site operation")
    for index, operation in enumerate(reviewed_sites):
        site_va = operation.get("site_va")
        if not _is_int(site_va):
            mapped = offset_to_va(container, int(operation.get("original_offset") or 0))
            if mapped is None:
                problems.append(
                    f"reviewed_site operation[{index}] has no site_va and its offset is not mappable"
                )
                continue
            site_va = mapped
        if not (scope_start <= int(site_va) < scope_end):
            problems.append(
                f"reviewed_site operation[{index}] site {int(site_va):#x} is outside "
                f"[{scope_start:#x}, {scope_end:#x})"
            )
    for index, operation in enumerate(operations):
        reason = operation.get("reason")
        if reason in ASSOCIATED_REASONS:
            if policy_value != "target_scoped_associated":
                problems.append(
                    f"operation[{index}] associated reason {reason!r} requires "
                    "target_scoped_associated scope"
                )
            if not str(operation.get("authorization_ref") or "").strip():
                problems.append(
                    f"operation[{index}] associated reason {reason!r} lacks authorization_ref"
                )
            continue
        if reason == "guard_cave":
            continue
        site_va = operation.get("site_va")
        if not _is_int(site_va):
            mapped = offset_to_va(container, int(operation.get("original_offset") or 0))
            site_va = mapped
        if site_va is None:
            problems.append(
                f"operation[{index}] modification offset is outside the mapped target scope"
            )
            continue
        if not (scope_start <= int(site_va) < scope_end):
            problems.append(
                f"operation[{index}] site {int(site_va):#x} escapes "
                f"[{scope_start:#x}, {scope_end:#x})"
            )

    cave = plan.get("cave") if isinstance(plan.get("cave"), dict) else (
        replay.get("cave") if isinstance(replay.get("cave"), dict) else None
    )
    guard_ops = [operation for operation in operations
                 if operation.get("reason") == "guard_cave" or operation.get("kind") == "insert"]
    if guard_ops:
        if cave is None:
            problems.append("guard cave insertion requires a declared cave")
        else:
            if not bool(cave.get("executable")):
                problems.append("guard cave is declared non-executable")
            cave_va = int(cave.get("va") or 0)
            cave_size = int(cave.get("size") or 0)
            redirect_found = False
            for operation in reviewed_sites:
                site_va = operation.get("site_va")
                if not _is_int(site_va):
                    mapped = offset_to_va(container, int(operation.get("original_offset") or 0))
                    site_va = mapped if mapped is not None else 0
                after = _hex_bytes(operation.get("after_hex")) or b""
                for target in _branch_targets(after, int(site_va)):
                    if cave_size > 0 and cave_va <= target < cave_va + cave_size:
                        redirect_found = True
            if not redirect_found:
                problems.append(
                    "guard cave is not reachable by a direct branch from a reviewed_site "
                    "operation (expected redirect into the declared cave)"
                )
    detail = (
        f"policy={policy_value} scope=[{scope_start:#x}, {scope_end:#x}) "
        f"ops={len(operations)} reviewed_sites={len(reviewed_sites)}"
    )
    if problems:
        detail += "; " + "; ".join(problems[:4])
    return {
        "ok": not problems,
        "status": "passed" if not problems else "failed",
        "policy": policy_value,
        "target_scope": {"policy": policy_value, **{
            key: target_scope[key] for key in ("name", "va", "end") if key in target_scope
        }},
        "problems": problems,
        "detail": detail,
    }


def _function_containing_symbol(
    container: dict[str, Any] | None,
    va: int,
    fallback_end: int | None = None,
) -> tuple[str, int, int] | None:
    """Return (name, start_va, end_va) of the symbol containing ``va``; else None."""
    symbols = []
    for symbol in (container or {}).get("symbols") or []:
        try:
            symbols.append((int(symbol.get("va", 0)), str(symbol.get("name") or "")))
        except (TypeError, ValueError):
            continue
    symbols.sort()
    for index, (symbol_va, name) in enumerate(symbols):
        if symbol_va > va:
            continue
        end = symbols[index + 1][0] if index + 1 < len(symbols) else None
        if end is None or end <= symbol_va:
            if fallback_end is not None and fallback_end > symbol_va:
                end = fallback_end
            else:
                continue
        if symbol_va <= va < end:
            return name, symbol_va, end
    return None


def derive_abi_blocks(
    plan: dict[str, Any],
    original: bytes,
    candidate: bytes,
    container: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive ABI evidence blocks; return ``not_run`` when none can be derived.

    Priority: declared plan blocks, exchanged metadata blocks/function range, a
    real symbol-backed function containing the target scope, then guard-cave
    bytes.  A bare site-sized target-scope range is not guessed as a function
    block (the Phase-8B B1 audit showed that produces false ABI failures); if no
    real function/block or cave exists the result is ``not_run``.
    """
    metadata = metadata or {}
    blocks: list[dict[str, Any]] = []
    problems: list[str] = []
    limitations: list[str] = []

    def add_block(source: str, function: str, va: int, size: int,
                  file_offset: int | None, arch: str,
                  block_hex: str | None = None) -> None:
        if block_hex is not None:
            chunk = bytes.fromhex(block_hex)
            blocks.append({
                "source": source, "function": function, "va": va,
                "size": len(chunk), "arch": arch, "file_offset": None,
                "block_sha256": sha256_bytes(chunk), "block_hex": chunk.hex(),
            })
            return
        if file_offset is None:
            limitations.append(f"{source} block at va {va:#x} is not mappable to a file offset")
            return
        if file_offset < 0 or size <= 0 or file_offset + size > len(candidate):
            problems.append(f"{source} block at va {va:#x} size {size} is outside the candidate")
            return
        chunk = candidate[file_offset:file_offset + size]
        blocks.append({
            "source": source,
            "function": function,
            "va": va,
            "size": size,
            "arch": arch,
            "file_offset": file_offset,
            "block_sha256": sha256_bytes(chunk),
        })

    arch = str(metadata.get("arch") or (container or {}).get("arch") or "")
    for entry in plan.get("abi_blocks") or []:
        if not isinstance(entry, dict):
            continue
        va = int(entry.get("va") or 0)
        size = int(entry.get("size") or 0)
        offset = va_to_offset(container, va)
        add_block("plan.abi_blocks", str(entry.get("function") or ""), va, size, offset,
                  str(entry.get("arch") or arch))
        declared_sha = entry.get("evidence_sha256")
        if (blocks and isinstance(declared_sha, str)
                and blocks[-1]["block_sha256"] != declared_sha.lower()):
            problems.append("plan abi block evidence_sha256 does not match the candidate block")
    for entry in metadata.get("abi_blocks") or []:
        if not isinstance(entry, dict):
            continue
        if "offset" in entry or "file_offset" in entry:
            offset = int(entry.get("offset", entry.get("file_offset")) or 0)
            size = int(entry.get("size") or 0)
            add_block("metadata.abi_blocks", str(entry.get("function") or ""),
                      int(entry.get("va") or 0), size, offset, str(entry.get("arch") or arch))
        else:
            va = int(entry.get("va") or 0)
            size = int(entry.get("size") or 0)
            add_block("metadata.abi_blocks", str(entry.get("function") or ""), va, size,
                      va_to_offset(container, va), str(entry.get("arch") or arch))
    old_block = metadata.get("abi_block")
    if not blocks and isinstance(old_block, dict):
        offset = old_block.get("offset", old_block.get("file_offset"))
        size = old_block.get("size", old_block.get("byte_size"))
        if _is_int(offset) and _is_int(size):
            add_block("metadata.abi_block", "", int(offset), int(size), int(offset), arch)
    abi_function = metadata.get("abi_function")
    if not blocks and isinstance(abi_function, dict):
        size = abi_function.get("size")
        if not _is_int(size) and _is_int(abi_function.get("end")) and _is_int(abi_function.get("va")):
            size = int(abi_function["end"]) - int(abi_function["va"])
        if _is_int(abi_function.get("va")) and _is_int(size):
            va = int(abi_function["va"])
            add_block("metadata.abi_function", str(abi_function.get("function") or ""),
                      va, int(size), va_to_offset(container, va),
                      str(abi_function.get("arch") or arch))
    scope = plan.get("target_scope") if isinstance(plan.get("target_scope"), dict) else {}
    if not blocks:
        scope_va = scope.get("va")
        if _is_int(scope_va):
            scope_end_fallback = scope.get("end")
            containing = _function_containing_symbol(
                container, int(scope_va),
                int(scope_end_fallback) if _is_int(scope_end_fallback) else None,
            )
            if containing is not None:
                name, start_va, end_va = containing
                add_block("symbol_function", name, start_va, end_va - start_va,
                          va_to_offset(container, start_va), arch)
    cave = plan.get("cave") if isinstance(plan.get("cave"), dict) else None
    if not blocks and cave is not None:
        cave_va = int(cave.get("va") or 0)
        cave_size = int(cave.get("size") or 0)
        offset = va_to_offset(container, cave_va)
        if offset is not None and cave_size > 0:
            add_block("cave", "guard_cave", cave_va, cave_size, offset, arch)
        else:
            inserted = b""
            for operation in plan.get("operations") or []:
                if (isinstance(operation, dict)
                        and (operation.get("reason") == "guard_cave"
                             or operation.get("kind") == "insert")):
                    inserted += _hex_bytes(operation.get("after_hex")) or b""
            if inserted and cave_size > 0:
                chunk = inserted[-cave_size:] if cave_size <= len(inserted) else inserted
                add_block("cave.inserted", "guard_cave", cave_va, len(chunk), None, arch,
                          block_hex=chunk.hex())
                limitations.append("guard cave block derived from inserted bytes")
    if problems:
        status = "failed"
    elif not blocks:
        status = "not_run"
        limitations.append(
            "no ABI block can be derived from the plan, exchanged metadata, a real "
            "symbol-backed function or the guard cave; ABI is unverifiable (not_run)"
        )
    else:
        status = "ok"
    return {
        "status": status,
        "blocks": blocks,
        "problems": problems,
        "limitations": limitations,
    }


def plan_limitations(plan: dict[str, Any]) -> list[str]:
    return list(plan.get("limitations") or [])


__all__ = [
    "PLAN_SCHEMA_VERSION",
    "OPERATION_KINDS",
    "OPERATION_REASONS",
    "ASSOCIATED_REASONS",
    "SCOPE_POLICIES",
    "ABI_ARCHES",
    "ORACLE_TIERS",
    "ORACLE_STATUSES",
    "canonical_plan_sha256",
    "offset_to_va",
    "va_to_offset",
    "replay_plan",
    "validate_scope",
    "derive_abi_blocks",
    "plan_limitations",
]
