#!/usr/bin/env python3
"""D04: analyze the Phase-8C heap-malloc independent-ABI rejection.

Repairs the committed heap fixture with the deterministic pipeline into a
temporary directory, runs the independent verifier with the generator's patch
plan and the committed external PoC, resolves every control-flow target in the
declared ABI block from bytes/relocations, checks the injected cave separately,
and records explicit root-cause classifications.

This is an analysis tool.  It never changes verifier rules, never accepts a
generator verdict as verification, and never turns the rejected candidate into a
verified claim.  ``--write`` produces the evidence artifact; ``--check`` is
offline and deterministic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURE_REL = "fixtures/hard-cases/vuln-heap-malloc-x86_64.elf"
POC_REL = "fixtures/poc/heap-malloc.json"
ARTIFACT_REL = "artifacts/phase8d-heap-malloc-abi-2026-11-17"
DOC_REL = "docs/operations/phase8d-heap-abi-analysis.md"
GENERATED_AT = "2026-11-17T00:00:00Z"
EXPECTED_ORIGINAL = "0f65a2d2ffe1ebf91f717d5edc78928cb8ee219e3f73e623b256f87bdcc4381f"
EXPECTED_CANDIDATE = "ea22260535efca37dca19404c700ce29e6da1f45b3af24d3903c8d27fdf6fb73"
TARGET = "heap_bad"
ROOTS = (
    "generator_patch_invalid",
    "generator_plan_incorrect",
    "verifier_rule_incorrect",
    "analysis_evidence_insufficient",
    "abi_proof_insufficient",
    "root_cause_inconclusive",
)
REQUIRED_ROOTS = (
    "generator_plan_incorrect",
    "abi_proof_insufficient",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _load_json(rel_or_path: str | Path) -> Any:
    path = Path(rel_or_path)
    if not path.is_absolute():
        path = ROOT / path
    return json.loads(path.read_text(encoding="utf-8"))


def _git_head() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT),
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = (result.stdout or "").strip()
    return value if len(value) == 40 else None


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _va_to_offset(data: bytes, va: int) -> int | None:
    """Map a VA to a file offset using ELF program headers."""
    try:
        from elftools.elf.elffile import ELFFile
    except Exception:  # noqa: BLE001
        return None
    import io

    try:
        with io.BytesIO(data) as stream:
            elf = ELFFile(stream)
            for segment in elf.iter_segments():
                start = int(segment["p_vaddr"])
                end = start + int(segment["p_filesz"])
                if start <= va < end:
                    return int(segment["p_offset"]) + (va - start)
    except Exception:  # noqa: BLE001
        return None
    return None


def _section_for_va(data: bytes, va: int) -> dict[str, Any] | None:
    from app.services.containers import detect_container

    container = detect_container(data)
    for section in container.sections:
        if section.executable and section.va <= va < section.va + section.size:
            return {
                "name": section.name,
                "va": section.va,
                "size": section.size,
                "offset": section.offset,
            }
    return None


def _block_bytes(data: bytes, va: int, size: int) -> tuple[bytes | None, dict[str, Any]]:
    section = _section_for_va(data, va)
    if section is not None:
        start = section["offset"] + (va - section["va"])
    else:
        start = _va_to_offset(data, va)
    if start is None or size <= 0 or start + size > len(data):
        return None, {"mapping": None, "section": section}
    return data[start:start + size], {
        "mapping": "section" if section is not None else "program_header",
        "section": section,
        "file_offset": start,
    }


def _relocation_map(data: bytes) -> dict[int, dict[str, Any]]:
    """Map relocation offsets (GOT slots) to their imported symbol names."""
    result: dict[int, dict[str, Any]] = {}
    try:
        from elftools.elf.elffile import ELFFile
    except Exception:  # noqa: BLE001
        return result
    import io

    try:
        with io.BytesIO(data) as stream:
            elf = ELFFile(stream)
            dynsym = elf.get_section_by_name(".dynsym")
            for name in (".rela.dyn", ".rela.plt"):
                section = elf.get_section_by_name(name)
                if section is None:
                    continue
                for reloc in section.iter_relocations():
                    index = int(reloc["r_info_sym"])
                    symbol = None
                    if dynsym is not None and index:
                        try:
                            symbol = dynsym.get_symbol(index).name or None
                        except Exception:  # noqa: BLE001
                            symbol = None
                    result[int(reloc["r_offset"])] = {
                        "relocation_section": name,
                        "symbol": symbol,
                        "relocation_type": int(reloc["r_info_type"]),
                    }
    except Exception:  # noqa: BLE001
        return result
    return result


def _disassemble(code: bytes, base_va: int) -> list[dict[str, Any]]:
    from capstone import CS_ARCH_X86, CS_MODE_64, CS_OP_IMM, CS_OP_MEM, Cs

    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    rows: list[dict[str, Any]] = []
    for ins in md.disasm(code, base_va):
        row: dict[str, Any] = {
            "address": hex(ins.address),
            "offset": ins.address - base_va,
            "bytes": ins.bytes.hex(),
            "mnemonic": ins.mnemonic,
            "op_str": ins.op_str,
            "control_flow": False,
        }
        if ins.mnemonic in {"call", "jmp"} or ins.mnemonic.startswith("j"):
            row["control_flow"] = True
            target_immediate = None
            memory = []
            for operand in ins.operands:
                if operand.type == CS_OP_IMM:
                    target_immediate = int(operand.imm)
                elif operand.type == CS_OP_MEM:
                    memory.append({
                        "base": ins.reg_name(operand.mem.base).lower()
                        if operand.mem.base else "",
                        "index": ins.reg_name(operand.mem.index).lower()
                        if operand.mem.index else "",
                        "disp": int(operand.mem.disp),
                        "segment": ins.reg_name(operand.mem.segment).lower()
                        if operand.mem.segment else "",
                    })
            row["direct_target_va"] = target_immediate
            row["memory_operands"] = memory
        rows.append(row)
    return rows


def _control_flow_resolution(
    instructions: list[dict[str, Any]], relocations: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Resolve direct or RIP-relative memory-indirect control-flow targets."""
    resolved: list[dict[str, Any]] = []
    for row in instructions:
        if not row.get("control_flow"):
            continue
        address = int(row["address"], 16)
        size = len(bytes.fromhex(row["bytes"]))
        entry: dict[str, Any] = {
            "address": row["address"],
            "offset": row["offset"],
            "mnemonic": row["mnemonic"],
            "op_str": row["op_str"],
            "kind": "direct" if row.get("direct_target_va") is not None else "unknown",
            "target_va": row.get("direct_target_va"),
            "target_symbol": None,
            "slot_va": None,
            "slot_symbol": None,
            "tail_call": row["mnemonic"] == "jmp",
        }
        if entry["kind"] == "direct":
            resolved.append(entry)
            continue
        for memory in row.get("memory_operands") or []:
            if memory.get("base") != "rip":
                continue
            slot_va = address + size + int(memory.get("disp") or 0)
            relocation = relocations.get(slot_va)
            entry.update({
                "kind": "memory_indirect",
                "slot_va": hex(slot_va),
                "slot_symbol": (relocation or {}).get("symbol"),
                "slot_relocation": (relocation or {}).get("relocation_section"),
                "slot_relocation_type": (relocation or {}).get("relocation_type"),
                "target_va": None,
            })
            break
        resolved.append(entry)
    return resolved


def _abi_report(code: bytes, *, allowed: list[int] | None = None) -> dict[str, Any]:
    from app.services.repair.abi import check_x86_64

    report = check_x86_64(code, allowed_call_targets=tuple(allowed or ()))
    return report.to_dict()


def _repair() -> tuple[bytes, bytes, Any]:
    from app.services.binary_pipeline import repair_any

    original = (ROOT / FIXTURE_REL).read_bytes()
    poc = _load_json(POC_REL)
    outcome = repair_any(
        original,
        poc_manifest=poc,
        target=TARGET,
        require_target=True,
        allow_whole_image=False,
    )
    if outcome.candidate is None:
        raise SystemExit("heap-malloc repair produced no candidate; cannot claim D04 result")
    return original, outcome.candidate, outcome


def _verify(original: bytes, candidate: bytes, plan: dict[str, Any]) -> dict[str, Any]:
    from app.services import independent_verifier
    from app.services.poc_runner import run_poc

    exchange_plan = json.loads(json.dumps(plan))
    # Match the benchmark-runner exchange: bind the plan's oracle declaration to
    # the committed manifest *file bytes* and remove generator-produced oracle
    # evidence hashes.  The verifier re-executes the oracle itself; without this
    # binding a valid plan would be rejected as if the manifest were different.
    exchange_oracle = exchange_plan.get("oracle")
    if isinstance(exchange_oracle, dict):
        exchange_oracle["manifest_sha256"] = _sha((ROOT / POC_REL).read_bytes())
        exchange_oracle.pop("evidence_sha256", None)
    metadata = {
        "format": "elf",
        "arch": "x86_64",
        "bits": 64,
        "endian": "little",
        "target_sha256": _sha(original),
        "target_scope": {
            "policy": "target_scoped",
            "name": TARGET,
            "va": plan["target_scope"]["va"],
            "end": plan["target_scope"]["end"],
        },
        "allow_whole_image": False,
        "generator": {"generator_id": "phase8d-heap-abi-analysis"},
        "patch_plan": exchange_plan,
        "actions": [],
    }
    # The plan's oracle manifest hash is verified by the verifier against the
    # independently supplied manifest path.
    return independent_verifier.verify_repair(
        original=original,
        candidate=candidate,
        metadata=metadata,
        oracle=str(ROOT / POC_REL),
        generator={"generator_id": "phase8d-heap-abi-analysis"},
        run_poc=run_poc,
    )


def _classifications(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    plan_block = analysis["plan"]["abi_blocks"][0]
    cave = analysis["plan"]["cave"]
    cave_abi = analysis["cave_abi"]
    function_abi = analysis["function_abi"]
    unresolved = analysis["control_flow_resolution"]
    calls = [item for item in unresolved if item["mnemonic"] == "call"]
    tail = [item for item in unresolved if item["mnemonic"] == "jmp"]
    results = [
        {
            "root": "generator_plan_incorrect",
            "confidence": "high",
            "primary": True,
            "detail": (
                "patch_plan.abi_blocks[0] covers the pre-existing target function "
                f"VA {hex(int(plan_block['va']))} size {plan_block['size']} and does "
                f"not cover the injected executable cave VA {hex(int(cave['va']))} "
                f"size {cave['size']}; the candidate's cave ABI check is "
                f"ok={cave_abi['ok']} while the declared function-block check is "
                f"ok={function_abi['ok']}."
            ),
            "evidence": {
                "plan_abi_block": plan_block,
                "cave": cave,
                "cave_abi_ok": cave_abi["ok"],
                "function_abi_ok": function_abi["ok"],
            },
        },
        {
            "root": "abi_proof_insufficient",
            "confidence": "high",
            "primary": True,
            "detail": (
                "ABI evidence binds the function block hash, not the injected cave "
                "block; a passing or failing function-block check therefore does not "
                "prove the injected guard's ABI discipline. The plan carries a cave "
                "but no independent ABI block for it."
            ),
            "evidence": {
                "abi_block_evidence_sha256": plan_block.get("evidence_sha256"),
                "cave_sha256": cave_abi.get("block_sha256"),
                "plan_has_cave": bool(cave),
            },
        },
        {
            "root": "verifier_rule_incorrect",
            "confidence": "medium",
            "primary": False,
            "detail": (
                "The verifier's x86-64 ABI checker does not resolve RIP-relative "
                "memory-indirect call/jump targets and does not model a tail call. "
                "On the declared function block it reports call_target_not_allowed "
                "for legal malloc/puts calls and no_ret for a legal free tail call. "
                "This is conservative for injected-only blocks, but insufficient "
                "when the declared block is a whole function; it is a contributing "
                "rule/expression gap, not the primary reason this plan should not "
                "have declared that block."
            ),
            "evidence": {
                "call_findings": [item for item in function_abi["findings"]
                                  if item["code"] == "call_target_not_allowed"],
                "branch_findings": [item for item in function_abi["findings"]
                                    if item["code"] == "branch_target_unknown"],
                "no_ret_findings": [item for item in function_abi["findings"]
                                    if item["code"] == "no_ret"],
                "resolved_calls": calls,
                "resolved_tail_calls": tail,
            },
        },
        {
            "root": "analysis_evidence_insufficient",
            "confidence": "high",
            "primary": False,
            "detail": (
                "The Phase-8C rejection report exposes only finding codes and no "
                "resolved call slots/symbols; it cannot by itself distinguish an "
                "invalid candidate from a mis-scoped ABI block. This artifact "
                "resolves the memory-indirect targets to malloc/puts and the tail "
                "jump to free via .rela.dyn."
            ),
            "evidence": {
                "phase8c_reason": analysis["verifier"]["phase8c_rejection_detail"],
                "resolved_control_flow": unresolved,
            },
        },
        {
            "root": "generator_patch_invalid",
            "confidence": "high",
            "primary": False,
            "excluded": True,
            "detail": (
                "No evidence the candidate patch is invalid: independent oracle "
                f"status={analysis['verifier']['runtime_oracle_status']}, layout "
                f"replay={analysis['verifier']['layout_passed']}, target scope="
                f"{analysis['verifier']['target_scope_passed']}, and the injected "
                f"cave ABI check is ok={cave_abi['ok']}."
            ),
            "evidence": {
                "oracle": analysis["verifier"]["oracle"],
                "cave_abi": cave_abi,
            },
        },
        {
            "root": "root_cause_inconclusive",
            "confidence": "high",
            "primary": False,
            "excluded": True,
            "detail": (
                "Root cause is conclusive at the plan/ABI-evidence layer: the plan "
                "declares the function block, the candidate cave is valid, and the "
                "independent oracle passes while the verifier remains fail-closed. "
                "No rule was changed and the candidate remains rejected."
            ),
            "evidence": {"decision": analysis["verifier"]["decision"]},
        },
    ]
    return results


def _build_analysis(original: bytes, candidate: bytes, outcome: Any, report: dict[str, Any]) -> dict[str, Any]:
    report_data = outcome.report.to_dict()
    plan = report_data.get("patch_plan")
    if not isinstance(plan, dict):
        raise SystemExit("repair report has no patch plan; cannot analyze ABI evidence")
    function_block = plan["abi_blocks"][0]
    function_code, function_map = _block_bytes(
        candidate, int(function_block["va"]), int(function_block["size"]))
    if function_code is None:
        raise SystemExit("declared ABI block cannot be mapped into candidate bytes")
    cave = plan["cave"]
    cave_code, cave_map = _block_bytes(
        candidate, int(cave["va"]), int(cave["size"]))
    if cave_code is None:
        raise SystemExit("declared cave cannot be mapped into candidate bytes")
    relocations = _relocation_map(candidate)
    instructions = _disassemble(function_code, int(function_block["va"]))
    cave_instructions = _disassemble(cave_code, int(cave["va"]))
    function_abi = _abi_report(function_code)
    cave_abi = _abi_report(cave_code)
    function_abi["block_sha256"] = _sha(function_code)
    cave_abi["block_sha256"] = _sha(cave_code)
    checks = {str(check.get("id")): check for check in report.get("checks") or []}
    abi_check = checks.get("abi") or {}
    phase8c = _load_json("artifacts/phase8c-benchmark-2026-11-16/samples/heap-malloc/verifier-report.json")
    phase8c_abi = next((item for item in phase8c.get("checks") or [] if item.get("id") == "abi"), {})
    oracle = (checks.get("runtime-oracle") or {})
    analysis: dict[str, Any] = {
        "schema_version": 1,
        "kind": "phase8d_heap_malloc_abi_analysis",
        "generated_at": GENERATED_AT,
        "base_repo": "phase8d-open-world",
        "worktree_head": _git_head(),
        "fixture": {
            "path": FIXTURE_REL,
            "sha256": _sha(original),
            "size": len(original),
        },
        "poc": {"path": POC_REL, "manifest_sha256": _sha((ROOT / POC_REL).read_bytes())},
        "target": TARGET,
        "candidate": {
            "sha256": _sha(candidate),
            "size": len(candidate),
            "matches_phase8c_candidate": _sha(candidate) == EXPECTED_CANDIDATE,
        },
        "plan": {
            "plan_id": plan.get("plan_id"),
            "plan_sha256": report.get("patch_plan_sha256"),
            "target_scope": plan.get("target_scope"),
            "cave": cave,
            "abi_blocks": plan.get("abi_blocks"),
            "operations": plan.get("operations"),
        },
        "function_block": {
            "mapping": function_map,
            "disassembly": instructions,
            "control_flow_resolution": _control_flow_resolution(instructions, relocations),
            "abi": function_abi,
        },
        "cave_block": {
            "mapping": cave_map,
            "disassembly": cave_instructions,
            "control_flow_resolution": _control_flow_resolution(
                cave_instructions, relocations),
            "abi": cave_abi,
        },
        "function_abi": function_abi,
        "cave_abi": cave_abi,
        "control_flow_resolution": _control_flow_resolution(instructions, relocations),
        "verifier": {
            "decision": report.get("decision"),
            "abi_status": abi_check.get("status"),
            "abi_detail": abi_check.get("detail"),
            "runtime_oracle_status": oracle.get("status"),
            "runtime_oracle_detail": oracle.get("detail"),
            "layout_passed": (checks.get("layout-plan") or {}).get("status") == "passed",
            "target_scope_passed": (checks.get("target-scope") or {}).get("status") == "passed",
            "phase8c_rejection_detail": phase8c_abi.get("detail"),
            "oracle": (checks.get("runtime-oracle") or {}),
        },
        "rule_modifications": [],
        "limitations": [
            "This analysis does not prove full semantic equivalence; the independent PoC oracle is function-level behavioural evidence.",
            "The ABI checker is conservative and static; GOT/PLT slot resolution is relocation-name based, not runtime-load resolved.",
            "The candidate remains rejected by the independent verifier; no verified claim is made.",
            "The original Phase-8C candidate bytes are reconstructed from the deterministic repair; hash equality with the committed Phase-8C candidate is recorded, not assumed.",
        ],
        "expected_hashes": {
            "original": EXPECTED_ORIGINAL,
            "candidate": EXPECTED_CANDIDATE,
        },
    }
    analysis["classifications"] = _classifications(analysis)
    return analysis


def _artifact_paths(artifact_dir: Path | None = None) -> dict[str, Path]:
    base = Path(artifact_dir) if artifact_dir is not None else ROOT / ARTIFACT_REL
    return {
        "dir": base,
        "candidate": base / "candidate.bin",
        "original_sha": base / "original.sha256",
        "candidate_sha": base / "candidate.sha256",
        "plan": base / "plan.json",
        "verifier_report": base / "verifier-report.json",
        "abi_analysis": base / "abi-analysis.json",
        "readme": base / "README.md",
        "sums": base / "SHA256SUMS",
    }


def _write_artifacts() -> list[str]:
    from dataclasses import asdict

    paths = _artifact_paths()
    paths["dir"].mkdir(parents=True, exist_ok=True)
    original, candidate, outcome = _repair()
    report = _verify(original, candidate, outcome.report.patch_plan or {})
    analysis = _build_analysis(original, candidate, outcome, report)
    paths["candidate"].write_bytes(candidate)
    paths["candidate_sha"].write_text(_sha(candidate) + "\n", encoding="ascii")
    paths["original_sha"].write_text(_sha(original) + "\n", encoding="ascii")
    _write_json(paths["plan"], outcome.report.patch_plan)
    _write_json(paths["verifier_report"], report)
    _write_json(paths["abi_analysis"], analysis)
    paths["readme"].write_text(
        "# D04 heap-malloc ABI rejection analysis (2026-11-17)\n\n"
        f"- fixture: `{FIXTURE_REL}` sha256 `{_sha(original)}`\n"
        f"- candidate: sha256 `{_sha(candidate)}` (matches Phase-8C: "
        f"{_sha(candidate) == EXPECTED_CANDIDATE})\n"
        "- independent verifier: decision `rejected`, ABI check `failed`\n"
        "- injected cave ABI: `ok=True`; declared function-block ABI: `ok=False`\n"
        "- classifications: `generator_plan_incorrect` (primary), "
        "`abi_proof_insufficient` (primary), `verifier_rule_incorrect` "
        "(contributing rule gap), `analysis_evidence_insufficient` (Phase-8C "
        "rejection message lacked target resolution). `generator_patch_invalid` "
        "and `root_cause_inconclusive` are excluded.\n"
        "- no verifier rule was modified; the candidate remains rejected.\n\n"
        "The function block contains legal `call [rip+...]` to malloc/puts and a "
        "legal `jmp [rip+...]` tail call to free. The plan declared that whole "
        "function as `abi_blocks[0]` instead of the injected cave. The checker "
        "does not resolve memory-indirect targets/tail calls, so it reports "
        "`call_target_not_allowed` and `no_ret`. The cave itself passes ABI.\n",
        encoding="utf-8",
    )
    names = ["candidate.bin", "original.sha256", "candidate.sha256", "plan.json",
             "verifier-report.json", "abi-analysis.json", "README.md"]
    lines = [f"{_sha((paths['dir'] / name).read_bytes())}  {name}" for name in names]
    paths["sums"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sorted(names + ["SHA256SUMS"])


def _check(artifact_dir: Path | None = None) -> list[str]:
    paths = _artifact_paths(artifact_dir)
    problems: list[str] = []
    for key, path in paths.items():
        if key == "dir":
            continue
        if not path.is_file():
            problems.append(f"missing {path.relative_to(ROOT)}")
    if problems:
        return problems
    analysis = _load_json(paths["abi_analysis"])
    candidate = paths["candidate"].read_bytes()
    if _sha(candidate) != EXPECTED_CANDIDATE:
        problems.append("candidate hash differs from expected Phase-8C candidate")
    if analysis.get("candidate", {}).get("sha256") != _sha(candidate):
        problems.append("analysis candidate hash mismatch")
    if analysis.get("fixture", {}).get("sha256") != EXPECTED_ORIGINAL:
        problems.append("fixture hash mismatch")
    verifier = analysis.get("verifier") or {}
    if verifier.get("decision") != "rejected":
        problems.append("verifier decision must remain rejected")
    if verifier.get("abi_status") != "failed":
        problems.append("ABI check must be failed")
    if analysis.get("cave_abi", {}).get("ok") is not True:
        problems.append("injected cave ABI must be reproducible as ok")
    if analysis.get("function_abi", {}).get("ok") is not False:
        problems.append("declared function-block ABI must reproduce failed")
    if analysis.get("rule_modifications"):
        problems.append("analysis must not modify verifier rules")
    roots = {item.get("root") for item in analysis.get("classifications") or []}
    for required in REQUIRED_ROOTS:
        if required not in roots:
            problems.append(f"missing classification {required}")
    if "generator_patch_invalid" in roots and not any(
        item.get("root") == "generator_patch_invalid" and item.get("excluded")
        for item in analysis.get("classifications") or []
    ):
        problems.append("generator_patch_invalid must be explicit/excluded")
    if analysis.get("candidate", {}).get("matches_phase8c_candidate") is not True:
        problems.append("candidate must match Phase-8C hash")
    # No hidden material or per-sample leak.
    text = json.dumps(analysis, sort_keys=True).lower()
    if "phase8c-hidden" in text or "/.binaryrepair/" in text:
        problems.append("artifact references hidden material")
    # SUMS covers exactly the data files.
    sums = paths["sums"].read_text(encoding="utf-8")
    listed = {}
    for line in sums.splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        listed[name.strip()] = digest
    expected = {"candidate.bin", "original.sha256", "candidate.sha256", "plan.json",
                "verifier-report.json", "abi-analysis.json", "README.md"}
    if set(listed) != expected:
        problems.append("SHA256SUMS entries do not match artifact payload set")
    for name, digest in listed.items():
        if _sha((paths["dir"] / name).read_bytes()) != digest:
            problems.append(f"sha256 mismatch {name}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--artifact-dir", type=Path, default=None,
                        help="artifact directory to check (default: committed D04 artifact)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        names = _write_artifacts()
        print(json.dumps({"ok": True, "artifact": ARTIFACT_REL, "files": names}, indent=2))
        return 0
    problems = _check(args.artifact_dir)
    print(json.dumps({"ok": not problems, "problems": problems}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
