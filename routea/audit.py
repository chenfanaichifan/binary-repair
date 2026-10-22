"""Complete static Gate 3 audit for the Route A cave candidate.

Every check here is a *static* fact about the original and the candidate. Runtime
facts (cave mapping, six-case behaviour, isolation) are separate evidence and are
never inferred from this module (handoff 11 §3 items 3-5; handoff 13 §5).

The audit returns a single JSON-serialisable dict::

    {"checks": {"<name>": bool, ...},
     "details": {...},
     "pass": bool,
     "failed": ["<name>", ...]}

``pass`` means every *required* check is ``True``. A check that could not be
evaluated is recorded as ``False`` with a reason, never silently dropped.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from capstone import CS_ARCH_X86, CS_GRP_CALL, CS_GRP_JUMP, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_REG_RIP
from elftools.elf.elffile import ELFFile

from routea.byteaudit import audit_changed_bytes, intervals_as_dicts
from routea.facts import (
    elf_facts,
    header_fields,
    program_headers,
    sha256_bytes,
    sha256_file,
)

MD = Cs(CS_ARCH_X86, CS_MODE_64)
MD.detail = True

CALLEE_SAVED = frozenset({"rbx", "rbp", "r12", "r13", "r14", "r15"})
PAGE = 0x1000
SHF_ALLOC = 0x2
SHF_EXECINSTR = 0x4


class AuditError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Small helpers


def _diff_dicts(before: dict[str, Any], after: dict[str, Any], ignore: tuple[str, ...] = ()) -> list[dict]:
    out = []
    for key in sorted(set(before) | set(after)):
        if key in ignore:
            continue
        if before.get(key) != after.get(key):
            out.append({"field": key, "before": before.get(key), "after": after.get(key)})
    return out


def _segment_index(phdrs: list[dict], vaddr: int) -> int | None:
    for seg in phdrs:
        if seg["type"] != "PT_LOAD":
            continue
        if seg["vaddr"] <= vaddr < seg["vaddr"] + max(seg["filesz"], seg["memsz"]):
            return seg["index"]
    return None


def _loads(phdrs: list[dict]) -> list[dict]:
    return [seg for seg in phdrs if seg["type"] == "PT_LOAD"]


def _make_check(checks: dict[str, bool], details: dict[str, Any], name: str, value: bool, **extra) -> None:
    checks[name] = bool(value)
    if extra:
        details[name] = extra


# ---------------------------------------------------------------------------
# Header audit


def header_audit(original: Path, patched: Path, *, expected_vaddr: int, expected_new_size: int) -> dict:
    before_facts = elf_facts(original)
    after_facts = elf_facts(patched)
    before = before_facts["program_headers"]
    after = after_facts["program_headers"]
    before_loads = _loads(before)
    after_loads = _loads(after)
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}

    _make_check(checks, details, "phdr_same_count", len(before) == len(after),
                before=len(before), after=len(after))
    _make_check(checks, details, "load_same_count", len(before_loads) == len(after_loads),
                before=len(before_loads), after=len(after_loads))

    changed = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
    expected_index = _segment_index(after, expected_vaddr)
    _make_check(checks, details, "exactly_one_header_changed",
                len(changed) == 1 and changed[0] == expected_index,
                changed_indices=changed, expected_index=expected_index)
    details["header_changes"] = [
        {"index": idx, "fields": _diff_dicts(before[idx], after[idx])}
        for idx in changed
    ]

    if expected_index is None:
        _make_check(checks, details, "expected_segment_present", False, vaddr=hex(expected_vaddr))
        return {"checks": checks, "details": details, "pass": False, "failed": _failed(checks)}

    old = before[expected_index]
    new = after[expected_index]
    _make_check(checks, details, "expected_segment_is_rx_load",
                new["type"] == "PT_LOAD" and new["flags"] == 5,
                type=new["type"], flags=new["flags"])
    for field in ("offset", "vaddr", "paddr", "flags", "align"):
        _make_check(checks, details, f"header_{field}_unchanged",
                    old[field] == new[field], before=old[field], after=new[field])
    _make_check(checks, details, "rx_end_file_backed",
                new["filesz"] == expected_new_size and new["memsz"] == expected_new_size,
                filesz=hex(new["filesz"]), memsz=hex(new["memsz"]),
                expected=hex(expected_new_size))
    _make_check(checks, details, "memsz_ge_filesz", new["memsz"] >= new["filesz"])
    align = new["align"] or PAGE
    _make_check(checks, details, "page_congruent",
                new["offset"] % align == new["vaddr"] % align,
                offset=hex(new["offset"]), vaddr=hex(new["vaddr"]), align=hex(align))
    _make_check(checks, details, "filesz_within_file",
                new["offset"] + new["filesz"] <= after_facts["size"],
                end_file=hex(new["offset"] + new["filesz"]), file_size=hex(after_facts["size"]))
    _make_check(checks, details, "entry_unchanged",
                before_facts["header"]["e_entry"] == after_facts["header"]["e_entry"],
                before=hex(before_facts["header"]["e_entry"]),
                after=hex(after_facts["header"]["e_entry"]))
    header_changes = _diff_dicts(
        before_facts["header"], after_facts["header"],
    )
    _make_check(checks, details, "elf_header_unchanged", not header_changes,
                changed=header_changes)

    # no overlap with the next loadable segment (virtual and file views)
    next_load = None
    for seg in after_loads:
        if seg["vaddr"] > new["vaddr"]:
            next_load = seg if next_load is None or seg["vaddr"] < next_load["vaddr"] else next_load
    overlap_ok = True
    if next_load is not None:
        overlap_ok = (
            new["vaddr"] + new["memsz"] <= next_load["vaddr"]
            and new["offset"] + new["filesz"] <= next_load["offset"]
        )
    _make_check(checks, details, "no_overlap_with_next_load", overlap_ok,
                segment_vaddr_end=hex(new["vaddr"] + new["memsz"]),
                next_vaddr=hex(next_load["vaddr"]) if next_load else None,
                segment_file_end=hex(new["offset"] + new["filesz"]),
                next_offset=hex(next_load["offset"]) if next_load else None)
    return {"checks": checks, "details": details, "pass": all(checks.values()), "failed": _failed(checks)}


# ---------------------------------------------------------------------------
# Section / dynamic / protection audit


def section_and_dynamic_audit(original: Path, patched: Path, *, cave_addr: int, cave_size: int) -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    before = elf_facts(original)
    after = elf_facts(patched)

    _make_check(checks, details, "section_header_table_unchanged",
                before["section_header_table_sha256"] == after["section_header_table_sha256"])
    _make_check(checks, details, "sections_unchanged",
                before["section_headers"] == after["section_headers"])

    for name in (".dynamic", ".dynsym", ".dynstr", ".rela.dyn", ".rela.plt",
                 ".rel.dyn", ".rel.plt", ".got", ".got.plt", ".plt", ".plt.sec"):
        left = before["section_content_sha256"][name]
        right = after["section_content_sha256"][name]
        _make_check(checks, details, f"section_identical_{name.lstrip('.')}", left == right,
                    before=left, after=right)
    _make_check(checks, details, "dynamic_entries_unchanged",
                before["dynamic"] == after["dynamic"])
    _make_check(checks, details, "relocations_unchanged",
                before["relocations"] == after["relocations"],
                before_count=len(before["relocations"]), after_count=len(after["relocations"]))
    _make_check(checks, details, "symbols_unchanged_except_none",
                before["symbols"] == after["symbols"])

    # nothing may cover the cave range: no alloc section, no symbol, no relocation
    cave_end = cave_addr + cave_size
    sections_in_cave = [
        sec["name"] for sec in before["section_headers"]
        if sec["alloc"] and sec["addr"] and sec["addr"] < cave_end and sec["addr"] + sec["size"] > cave_addr
    ]
    _make_check(checks, details, "no_section_covers_cave", not sections_in_cave,
                sections=sections_in_cave)
    file_offset = _file_offset(original, cave_addr)
    sections_in_cave_file = [
        sec["name"] for sec in before["section_headers"]
        if sec["size"] and sec["offset"] < file_offset + cave_size
        and sec["offset"] + sec["size"] > file_offset
    ]
    _make_check(checks, details, "no_section_file_range_covers_cave",
                not sections_in_cave_file, sections=sections_in_cave_file,
                cave_file_offset=hex(file_offset))
    symbols_in_cave = [
        sym["name"] for sym in before["symbols"]
        if cave_addr <= sym["value"] < cave_end
        or (sym["value"] and sym["value"] + sym["size"] > cave_addr and sym["value"] < cave_end)
    ]
    _make_check(checks, details, "no_symbol_in_cave", not symbols_in_cave, symbols=symbols_in_cave)
    relocs_in_cave = [
        rel for rel in before["relocations"]
        if cave_addr <= rel["offset"] < cave_end
    ]
    _make_check(checks, details, "no_relocation_targets_cave", not relocs_in_cave,
                relocations=relocs_in_cave)

    # protections
    _make_check(checks, details, "no_wx_segment",
                all(not (seg["flags"] & 2 and seg["flags"] & 1) for seg in after["program_headers"]))
    gnu_stack_before = [s for s in before["program_headers"] if s["type"] == "GNU_STACK"]
    gnu_stack_after = [s for s in after["program_headers"] if s["type"] == "GNU_STACK"]
    _make_check(checks, details, "gnu_stack_unchanged_no_nx_loss",
                gnu_stack_before == gnu_stack_after
                and all(not (seg["flags"] & 1) for seg in gnu_stack_after))
    relro_before = [s for s in before["program_headers"] if s["type"] == "GNU_RELRO"]
    relro_after = [s for s in after["program_headers"] if s["type"] == "GNU_RELRO"]
    _make_check(checks, details, "gnu_relro_unchanged", relro_before == relro_after)
    bits_before = [entry["tag"] for entry in before["dynamic"]]
    bits_after = [entry["tag"] for entry in after["dynamic"]]
    _make_check(checks, details, "dynamic_tags_unchanged", bits_before == bits_after)
    _make_check(checks, details, "cet_note_unchanged",
                before["cet"] == after["cet"], before=before["cet"], after=after["cet"])
    return {"checks": checks, "details": details, "pass": all(checks.values()), "failed": _failed(checks)}


# ---------------------------------------------------------------------------
# Redirect / displaced bytes


def redirect_audit(original: Path, patched: Path, *, call_site: int, expected_redirect: bytes,
                   expected_original: bytes, cave_addr: int, strcpy_plt: int,
                   resume_at: int) -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    original_site = _bytes_at(original, call_site, 5)
    patched_site = _bytes_at(patched, call_site, 5)
    _make_check(checks, details, "original_call_is_strcpy_plt",
                original_site == expected_original
                and original_site[:1] == b"\xe8"
                and call_site + 5 + int.from_bytes(original_site[1:5], "little", signed=True) == strcpy_plt,
                original_hex=original_site.hex(), strcpy_plt=hex(strcpy_plt))
    _make_check(checks, details, "redirect_bytes_written",
                patched_site == expected_redirect,
                expected=expected_redirect.hex(), actual=patched_site.hex())
    _make_check(checks, details, "redirect_target_is_cave",
                patched_site[:1] == b"\xe8"
                and call_site + 5 + int.from_bytes(patched_site[1:5], "little", signed=True) == cave_addr,
                cave=hex(cave_addr))
    _make_check(checks, details, "resume_address_after_call",
                resume_at == call_site + 5, resume_at=hex(resume_at), call_site=hex(call_site))
    displacement = int.from_bytes(patched_site[1:5], "little", signed=True)
    _make_check(checks, details, "redirect_rel32_in_range", -(2**31) <= displacement < 2**31,
                displacement=hex(displacement & 0xFFFFFFFF))
    details["displaced"] = {
        "file_offset": hex(_file_offset(original, call_site)),
        "vaddr": hex(call_site),
        "size": 5,
        "original_hex": original_site.hex(),
        "new_hex": patched_site.hex(),
        "resume_at": hex(resume_at),
    }
    return {"checks": checks, "details": details, "pass": all(checks.values()), "failed": _failed(checks)}


# ---------------------------------------------------------------------------
# Cave unused proof (static)


def cave_unused_audit(original: Path, patched: Path, *, cave_addr: int, cave_size: int) -> dict:
    """Prove the cave is unused in the original and reachable in the candidate.

    Review finding B4: the cave starts exactly at the original RX ``p_memsz``
    end, so the containment check must use the **patched/extended** segment; the
    original segment is only used to prove the range was not file-backed before
    the authorized extension.
    """
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    cave_end = cave_addr + cave_size
    before = _loads(program_headers(original))
    after = _loads(program_headers(patched))

    def enclosing(loads: list[dict]) -> dict | None:
        return next((seg for seg in loads
                     if seg["vaddr"] <= cave_addr < seg["vaddr"] + seg["memsz"]), None)

    extended = enclosing(after)
    # The cave starts exactly at the original RX p_memsz end, so a strict
    # "inside memsz" lookup returns nothing for the original; use the closest
    # loadable segment at or below the address instead (same page).
    original_candidates = [seg for seg in before
                           if seg["vaddr"] <= cave_addr]
    original_seg = max(original_candidates, key=lambda seg: seg["vaddr"]) \
        if original_candidates else None
    _make_check(checks, details, "inside_extended_rx_load",
                extended is not None and (extended["flags"] & 4) and (extended["flags"] & 1),
                segment_flags=extended["flags"] if extended else None)
    if extended is None:
        return {"checks": checks, "details": details, "pass": False, "failed": _failed(checks)}

    _make_check(checks, details, "cave_within_extended_memsz",
                cave_end <= extended["vaddr"] + extended["memsz"],
                extended_memsz=hex(extended["memsz"]),
                cave_end=hex(cave_end))
    if original_seg is not None:
        original_file_backed_end = original_seg["vaddr"] + original_seg["filesz"]
        _make_check(checks, details, "cave_not_file_backed_before_extension",
                    cave_addr >= original_file_backed_end,
                    original_filesz=hex(original_seg["filesz"]),
                    original_file_backed_end=hex(original_file_backed_end))
    else:
        _make_check(checks, details, "cave_not_file_backed_before_extension", False,
                    reason="cave is outside every original PT_LOAD")
    page_start = cave_addr & ~0xFFF
    _make_check(checks, details, "cave_inside_one_page",
                cave_end <= page_start + 0x1000,
                page=hex(page_start), cave_end=hex(cave_end))

    cave_file_offset = extended["offset"] + (cave_addr - extended["vaddr"])
    filler = _bytes_at_file(original, cave_file_offset, cave_size)
    details["original_filler"] = {
        "file_offset": hex(cave_file_offset),
        "size": cave_size,
        "all_zero": filler == b"\x00" * cave_size,
        "sha256": sha256_bytes(filler),
    }
    _make_check(checks, details, "original_filler_zero",
                details["original_filler"]["all_zero"])

    # no branch or RIP-relative reference into the cave from any executable section
    incoming: list[dict[str, Any]] = []
    with original.open("rb") as fh:
        elf = ELFFile(fh)
        for sec in elf.iter_sections():
            flags = sec["sh_flags"]
            if not (flags & SHF_ALLOC and flags & SHF_EXECINSTR):
                continue
            for insn in MD.disasm(sec.data(), sec["sh_addr"]):
                targets: list[int] = []
                if insn.group(CS_GRP_JUMP) or insn.group(CS_GRP_CALL):
                    for op in insn.operands:
                        if op.type == X86_OP_IMM:
                            targets.append(op.imm)
                for op in insn.operands:
                    if op.type == X86_OP_MEM and op.mem.base == X86_REG_RIP:
                        targets.append(insn.address + insn.size + op.mem.disp)
                for target in targets:
                    if cave_addr <= target < cave_end:
                        incoming.append(
                            {"section": sec.name, "address": hex(insn.address),
                             "mnemonic": insn.mnemonic, "target": hex(target)}
                        )
    _make_check(checks, details, "no_incoming_reference", not incoming, references=incoming[:40])
    return {"checks": checks, "details": details, "pass": all(checks.values()), "failed": _failed(checks)}


# ---------------------------------------------------------------------------
# Added-code static safety (register / stack / control transfer)


def code_audit(code: bytes, code_vaddr: int, *, strcpy_plt: int,
               exit_group_number: int = 231) -> dict:
    """Static checks for the canonical cave code (write + exit_group syscalls)."""
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    insns = list(MD.disasm(code, code_vaddr))
    if not insns or insns[-1].address + insns[-1].size != code_vaddr + len(code):
        return {"checks": {"code_decodes_fully": False}, "details": {},
                "pass": False, "failed": ["code_decodes_fully"]}
    checks["code_decodes_fully"] = True

    writes: list[dict[str, Any]] = []
    forbidden: list[dict[str, Any]] = []
    indirect: list[dict[str, Any]] = []
    rets: list[dict[str, Any]] = []
    syscalls: list[dict[str, Any]] = []
    branch_targets: list[dict[str, Any]] = []
    for insn in insns:
        _read, written = insn.regs_access()
        for reg in written:
            name = insn.reg_name(reg)
            record = {"address": hex(insn.address), "instruction": f"{insn.mnemonic} {insn.op_str}",
                      "register": name, "mnemonic": insn.mnemonic}
            writes.append(record)
            if name in CALLEE_SAVED:
                forbidden.append(record)
        if insn.mnemonic == "ret":
            rets.append({"address": hex(insn.address)})
        if insn.mnemonic in ("syscall", "sysenter"):
            syscalls.append({"address": hex(insn.address), "mnemonic": insn.mnemonic})
        if (insn.group(CS_GRP_JUMP) or insn.group(CS_GRP_CALL)) and insn.operands:
            op = insn.operands[0]
            if op.type != X86_OP_IMM:
                indirect.append({"address": hex(insn.address),
                                 "instruction": f"{insn.mnemonic} {insn.op_str}"})
            else:
                branch_targets.append({"address": hex(insn.address), "target": hex(op.imm),
                                       "external": not (code_vaddr <= op.imm < code_vaddr + len(code))})

    _make_check(checks, details, "no_callee_saved_write", not forbidden, writes=forbidden)
    _make_check(checks, details, "no_return_instruction", not rets, instructions=rets)
    _make_check(checks, details, "no_indirect_transfer", not indirect, instructions=indirect)
    rsp_writes = [w for w in writes if w["register"] == "rsp"]
    _make_check(checks, details, "no_stack_write", not rsp_writes, writes=rsp_writes)
    details["writes"] = writes
    details["branch_targets"] = branch_targets

    text = [f"{insn.mnemonic} {insn.op_str}" for insn in insns]
    _make_check(checks, details, "two_syscalls", len(syscalls) == 2, syscalls=syscalls)
    _make_check(checks, details, "write_syscall_setup",
                any(t in ("mov eax, 1", "mov eax, 0x1") for t in text)
                and any(t in ("mov edi, 2", "mov edi, 0x2") for t in text)
                and any(t in ("mov edx, 0x2a", "mov edx, 42") for t in text),
                instructions=text)
    _make_check(checks, details, "exit_group_status_1_setup",
                any(t in ("mov eax, 0xe7", "mov eax, 231") or
                    t == f"mov eax, {exit_group_number}" for t in text)
                and any(t in ("mov edi, 1", "mov edi, 0x1") for t in text),
                instructions=text)
    _make_check(checks, details, "no_plt_call",
                not any(insn.mnemonic == "call" for insn in insns),
                note="canonical candidate writes via write(2), not fprintf@plt")
    _make_check(checks, details, "valid_path_reuses_strcpy",
                any(t["target"] == hex(strcpy_plt) for t in branch_targets),
                strcpy_plt=hex(strcpy_plt))
    return {"checks": checks, "details": details, "pass": all(checks.values()), "failed": _failed(checks)}


# ---------------------------------------------------------------------------
# Independent readelf view


def parse_readelf_program_headers(text: str) -> list[dict]:
    """Parse ``readelf -lW`` program-header rows into the elftools field names.

    The independent view exists so the audit cannot rely on a single parser
    (handoff 11 §3 item 3). Rows look like::

          LOAD           0x001000 0x...401000 0x...401000 0x001000 0x001000 R E 0x1000
    """
    out = []
    for line in text.splitlines():
        tokens = line.split()
        if len(tokens) < 8:
            continue
        kind = tokens[0]
        if not kind.isupper() or not tokens[1].startswith("0x"):
            continue
        try:
            offset = int(tokens[1], 16)
            vaddr = int(tokens[2], 16)
            paddr = int(tokens[3], 16)
            filesz = int(tokens[4], 16)
            memsz = int(tokens[5], 16)
            align = int(tokens[-1], 16)
        except ValueError:
            continue
        flags_text = "".join(tokens[6:-1])
        if not flags_text or any(ch not in "RWE" for ch in flags_text):
            continue
        numeric = (4 if "R" in flags_text else 0) | (2 if "W" in flags_text else 0) \
            | (1 if "E" in flags_text else 0)
        out.append(
            {
                "type": kind,
                "offset": offset,
                "vaddr": vaddr,
                "paddr": paddr,
                "filesz": filesz,
                "memsz": memsz,
                "flags": numeric,
                "align": align,
            }
        )
    return out


def independent_readelf_audit(patched: Path, readelf_text: str) -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    parsed = parse_readelf_program_headers(readelf_text)
    _make_check(checks, details, "readelf_parsed", bool(parsed), segments=len(parsed))
    if not parsed:
        return {"checks": checks, "details": details, "pass": False, "failed": _failed(checks)}
    facts = program_headers(patched)
    _make_check(checks, details, "readelf_matches_elftools_count", len(parsed) == len(facts),
                readelf=len(parsed), elftools=len(facts))
    mismatches = []
    for left, right in zip(parsed, facts):
        for field in ("offset", "vaddr", "paddr", "filesz", "memsz", "flags", "align"):
            if left[field] != right[field]:
                mismatches.append({"index": right["index"], "field": field,
                                   "readelf": left[field], "elftools": right[field]})
    _make_check(checks, details, "readelf_matches_elftools_values", not mismatches,
                mismatches=mismatches)
    return {"checks": checks, "details": details, "pass": all(checks.values()), "failed": _failed(checks)}


# ---------------------------------------------------------------------------
# Combined audit


def audit_cave_candidate(
    original: Path,
    patched: Path,
    *,
    call_site: int,
    redirect: bytes,
    displaced: bytes,
    cave_addr: int,
    cave_size: int,
    code: bytes,
    code_vaddr: int,
    message: bytes,
    message_vaddr: int,
    strcpy_plt: int,
    resume_at: int,
    expected_new_size: int,
    declared_intervals,
    readelf_text: str | None = None,
) -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, Any] = {}
    sections = [
        redirect_audit(original, patched, call_site=call_site, expected_redirect=redirect,
                       expected_original=displaced, cave_addr=cave_addr, strcpy_plt=strcpy_plt,
                       resume_at=resume_at),
        header_audit(original, patched, expected_vaddr=_rx_vaddr(original, cave_addr),
                     expected_new_size=expected_new_size),
        cave_unused_audit(original, patched, cave_addr=cave_addr, cave_size=cave_size),
        section_and_dynamic_audit(original, patched, cave_addr=cave_addr, cave_size=cave_size),
        code_audit(code, code_vaddr, strcpy_plt=strcpy_plt),
    ]
    if readelf_text is not None:
        sections.append(independent_readelf_audit(patched, readelf_text))

    for part in sections:
        for name, value in part["checks"].items():
            checks[name] = checks.get(name, True) and bool(value)
            if not value:
                details[name] = part["details"].get(name, {"value": value})

    # bytes: written locations and declared intervals must match exactly
    original_bytes = original.read_bytes()
    patched_bytes = patched.read_bytes()
    byte_result = audit_changed_bytes(original_bytes, patched_bytes, declared_intervals)
    checks["changed_bytes_inside_declared_intervals"] = byte_result["pass"]
    details["changed_bytes"] = byte_result
    if not byte_result["pass"]:
        details["changed_bytes_outside"] = byte_result["outside_declared"]

    # expected content at the declared locations
    _make_check(checks, details, "cave_code_at_address",
                _bytes_at(patched, cave_addr, len(code)) == code,
                cave=hex(cave_addr), size=len(code))
    _make_check(checks, details, "message_at_address",
                _bytes_at(patched, message_vaddr, len(message)) == message,
                message_vaddr=hex(message_vaddr), size=len(message))
    _make_check(checks, details, "original_hash_recorded",
                sha256_bytes(original_bytes) == sha256_file(original))
    _make_check(checks, details, "candidate_differs_from_original",
                original_bytes != patched_bytes and byte_result["changed_byte_count"] > 0,
                changed_byte_count=byte_result["changed_byte_count"],
                note="fixes review finding B5: an unpatched candidate must fail this check")
    return {
        "checks": checks,
        "details": details,
        "pass": all(checks.values()),
        "failed": _failed(checks),
    }


def _phdr_index(path: Path, vaddr: int) -> int:
    for seg in program_headers(path):
        if seg["type"] == "PT_LOAD" and seg["vaddr"] == vaddr:
            return int(seg["index"])
    raise AuditError(f"PT_LOAD at {vaddr:#x} not found")


def declared_intervals_for_plan(original: Path, plan) -> list[dict]:
    """Inclusive file intervals the canonical build is allowed to change."""
    call_offset = _file_offset(original, plan.call_site)
    cave_offset = _file_offset(original, plan.cave_addr)
    cave_len = len(plan.code) + len(plan.message)
    fields = header_fields(original)
    entry_offset = fields["e_phoff"] + _phdr_index(original, plan.rx_vaddr) * fields["e_phentsize"]
    return intervals_as_dicts(
        [
            (call_offset, call_offset + 4),
            (cave_offset, cave_offset + cave_len - 1),
            # ELF64 program header: p_filesz at +32, p_memsz at +40
            (entry_offset + 32, entry_offset + 47),
        ]
    )


def audit_canonical_candidate(original: Path, patched: Path, plan, *,
                              readelf_text: str | None = None) -> dict:
    """Audit a candidate built by the canonical ``routea.cave`` plan."""
    return audit_cave_candidate(
        original,
        patched,
        call_site=plan.call_site,
        redirect=plan.redirect,
        displaced=_bytes_at(original, plan.call_site, 5),
        cave_addr=plan.cave_addr,
        cave_size=plan.cave_size,
        code=plan.code,
        code_vaddr=plan.cave_addr,
        message=plan.message,
        message_vaddr=plan.message_addr,
        strcpy_plt=plan.strcpy_plt,
        resume_at=plan.call_site + 5,
        expected_new_size=plan.rx_new_size,
        declared_intervals=declared_intervals_for_plan(original, plan),
        readelf_text=readelf_text,
    )


def _failed(checks: dict[str, bool]) -> list[str]:
    return [name for name, value in checks.items() if not value]


# ---------------------------------------------------------------------------
# Low-level file helpers


def _file_offset(path: Path, vaddr: int) -> int:
    segments = program_headers(path)
    file_size = path.stat().st_size
    for seg in segments:
        if seg["type"] != "PT_LOAD":
            continue
        if seg["vaddr"] <= vaddr < seg["vaddr"] + seg["filesz"]:
            return seg["offset"] + vaddr - seg["vaddr"]
    # Addresses in the loader-zero tail or file padding are not inside p_filesz,
    # but their file byte position is still well defined when it is inside EOF.
    candidates = [seg for seg in segments
                  if seg["type"] == "PT_LOAD" and seg["vaddr"] <= vaddr]
    if candidates:
        segment = max(candidates, key=lambda seg: seg["vaddr"])
        offset = segment["offset"] + (vaddr - segment["vaddr"])
        if offset < file_size:
            return offset
    raise AuditError(f"address {vaddr:#x} has no file offset")


def _bytes_at(path: Path, vaddr: int, size: int) -> bytes:
    try:
        offset = _file_offset(path, vaddr)
    except AuditError:
        return b""
    raw = path.read_bytes()
    return raw[offset : offset + size]


def _bytes_at_file(path: Path, offset: int, size: int) -> bytes:
    return path.read_bytes()[offset : offset + size]


def _rx_vaddr(path: Path, cave_addr: int) -> int:
    for seg in program_headers(path):
        if seg["type"] == "PT_LOAD" and (seg["flags"] & 1) and seg["vaddr"] <= cave_addr:
            return seg["vaddr"]
    raise AuditError("RX segment not found")
