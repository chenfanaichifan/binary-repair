"""Reviewed in-place repair for duplicated destination-range checks that use
the wrong capacity variable.

The defect class
----------------
A compiler inlines a bounds check such as ``range_ok(dst_off, len, cap)`` into
three near-identical blocks (for example one per operation kind).  Two blocks
compare against the capacity of the buffer that is written; one block compares
against the *input size* variable instead.  The block is self-consistent
(``cap - dst`` plays the role of ``cap - dst`` for whichever variable was
picked), so the wrong variable is only visible by comparing the sibling blocks.
This is CWE-131 / CWE-697 leading to CWE-787 (out-of-bounds write).

Detection is deliberately bounded and fail-closed.  A block is only a
candidate when

  * it is an inlined unsigned range check of the shape
    ``cmp Ra, Rb; jb FAIL; mov T, Ra; sub T, Rb; cmp T, Rl; jcc``;
  * ``Rb`` is loaded from ``[BASE+dst_disp]`` and ``Rl`` is loaded from memory
    (the copied length is a runtime value);
  * at least three blocks in the same function guard the *same*
    ``[BASE+dst_disp]`` field;
  * exactly one of them uses a capacity register that differs from the
    majority, and that register is also used as the capacity of a different
    field of the same structure (the input-size variable) elsewhere in the
    function.

The minority block is rewritten in place, keeping the same byte length::

    mov T, GOOD_CAP      ; the sibling-consistent capacity register
    sub T, dst           ; sets CF exactly like the dropped ``cmp GOOD_CAP, dst``
    jb  FAIL             ; unsigned dst > GOOD_CAP
    cmp T, len
    jae COPY             ; (or ``jb FAIL`` when the original was fail/fail)
    nop ...

The rewrite is re-decoded and every byte outside the recorded actions is
checked to be unchanged.  When the error message of the patched block still
names the wrong buffer (``... outside the payload pool``) while its agreeing
siblings say ``... outside the output``, the ``.rodata`` string is aligned to
the sibling wording as a separate, recorded action.

This is a pattern engine for one reviewed defect class, not a universal
binary rewriter.
"""
from __future__ import annotations

import bisect
import hashlib
import io
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from capstone import CS_ARCH_X86, CS_MODE_64, Cs
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG
from elftools.elf.elffile import ELFFile

_MD = Cs(CS_ARCH_X86, CS_MODE_64)
_MD.detail = True
_MD.skipdata = True

_REG32 = {
    name: index
    for index, name in enumerate(
        ("eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi")
    )
}
_REG32.update({f"r{i}d": i for i in range(8, 16)})
_REG32_NAME = {value: name for name, value in _REG32.items()}

# The first branch must be the unsigned ``below`` failure branch; the second is
# either the same failure branch (``jb`` to the same target) or the success
# branch (``jae`` to the copy).  Signed or inclusive predicates are rejected.
_FAIL_JCC = frozenset({"jb"})
_SUCCESS_JCC = frozenset({"jae"})

_MESSAGE_RE = re.compile(
    r"^(?P<prefix>(?:op\[%u\]: )?(?P<branch>\S+) destination outside the )"
    r"(?P<noun>[ -~]+)$"
)

_MAX_BLOCK_INSTRUCTIONS = 10
_MAX_LOOKBACK = 24

#: Detection decodes the whole executable region; very large images are outside
#: this reviewed engine and are rejected explicitly instead of paying an
#: unbounded decode cost.  (marcx: 521 KB, synthetic fixture: 518 KB.)
MAX_CODE_BYTES = 2 * 1024 * 1024


class CapacityError(RuntimeError):
    """Raised when a candidate patch cannot be applied safely."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class CapacitySite:
    """One divergent block selected for an in-place rewrite."""

    site_va: int
    file_offset: int
    block_size: int
    dst_disp: int
    base_reg: str
    bad_capacity: str
    good_capacity: str
    sibling_vas: tuple[int, ...]
    source_disp: int | None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "sibling_vas": [int(item) for item in self.sibling_vas]}


@dataclass(frozen=True)
class CapacityAction:
    """Byte-level record of one reviewed change (re-derived by the gate)."""

    kind: str
    offset: int
    size: int
    before_hex: str
    after_hex: str
    site_va: int = 0
    bad_capacity: str = ""
    good_capacity: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapacityReport:
    original_sha256: str
    patched_sha256: str
    format: str
    arch: str
    mode: str
    strategy: str
    supported: bool
    status: str
    sites: list[CapacitySite] = field(default_factory=list)
    actions: list[CapacityAction] = field(default_factory=list)
    message_actions: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "sites": [item.to_dict() for item in self.sites],
            "actions": [item.to_dict() for item in self.actions],
            "message_actions": [dict(item) for item in self.message_actions],
        }


# ---------------------------------------------------------------------------
# ELF layout helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Region:
    data: bytes
    vaddr: int
    file_offset: int

    def contains(self, addr: int, size: int = 1) -> bool:
        return self.vaddr <= addr and addr + size <= self.vaddr + len(self.data)

    def read(self, addr: int, size: int) -> bytes:
        start = addr - self.vaddr
        return self.data[start:start + size]

    def offset_of(self, addr: int) -> int:
        return self.file_offset + (addr - self.vaddr)


def _elf(data: bytes) -> ELFFile:
    if len(data) < 64 or data[:4] != b"\x7fELF":
        raise CapacityError("not an ELF file")
    if data[4] != 2 or data[5] != 1:
        raise CapacityError("only little-endian ELF64 is supported")
    try:
        elf = ELFFile(io.BytesIO(data))
    except Exception as exc:  # noqa: BLE001
        raise CapacityError(f"ELF header parse failed: {type(exc).__name__}") from exc
    machine = elf.header["e_machine"]
    if isinstance(machine, str):
        machine = {"EM_X86_64": 62}.get(machine)
    if machine != 62:  # EM_X86_64
        raise CapacityError("only x86-64 ELF is supported")
    return elf


_NOBITS = frozenset({"SHT_NOBITS", 8})


def _section_type(section: Any) -> Any:
    """``sh_type`` as an int when possible, else the enum name."""
    value = section["sh_type"]
    if isinstance(value, str):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _sections(elf: ELFFile) -> dict[str, _Region]:
    out: dict[str, _Region] = {}
    try:
        sections = list(elf.iter_sections())
    except Exception:  # noqa: BLE001
        return {}
    for section in sections:
        try:
            if not int(section["sh_flags"]) & 0x2:  # SHF_ALLOC
                continue
            if _section_type(section) in _NOBITS:
                continue
            size = int(section["sh_size"])
            if size <= 0:
                continue
            out[str(section.name)] = _Region(
                section.data(), int(section["sh_addr"]), int(section["sh_offset"])
            )
        except Exception:  # noqa: BLE001
            continue
    return out


def _load_regions(elf: ELFFile) -> list[_Region]:
    regions: list[_Region] = []
    for segment in elf.iter_segments():
        if segment["p_type"] != "PT_LOAD":
            continue
        size = int(segment["p_filesz"])
        if size <= 0:
            continue
        regions.append(
            _Region(segment.data(), int(segment["p_vaddr"]), int(segment["p_offset"]))
        )
    return regions


def _code_region(elf: ELFFile, sections: dict[str, _Region]) -> _Region:
    text = sections.get(".text")
    if text is not None and text.data:
        return text
    for name, region in sections.items():
        if name.startswith(".text") and region.data:
            return region
    for segment in elf.iter_segments():
        if segment["p_type"] != "PT_LOAD" or not int(segment["p_flags"]) & 0x1:
            continue
        size = int(segment["p_filesz"])
        if size > 0:
            return _Region(
                segment.data(), int(segment["p_vaddr"]), int(segment["p_offset"])
            )
    raise CapacityError("ELF has no readable executable code")


def _read_cstring(regions: list[_Region], addr: int, limit: int = 160) -> str | None:
    for region in regions:
        if not region.contains(addr):
            continue
        available = min(limit, len(region.data) - (addr - region.vaddr))
        raw = region.read(addr, available)
        end = raw.find(b"\x00")
        if end <= 0:
            return None
        try:
            return raw[:end].decode("ascii")
        except UnicodeDecodeError:
            return None
    return None


# ---------------------------------------------------------------------------
# Instruction helpers
# ---------------------------------------------------------------------------


def _reg32(ins: Any, operand: Any) -> int | None:
    if operand.type != X86_OP_REG:
        return None
    try:
        return _REG32.get(ins.reg_name(operand.reg) or "")
    except Exception:  # noqa: BLE001
        return None


def _name32(index: int | None) -> str:
    return "?" if index is None else _REG32_NAME.get(index, "?")


def _writes_reg(ins: Any, reg: int) -> bool:
    if not getattr(ins, 'operands', None) or ins.mnemonic in {"cmp", "test", "nop", "push", "jmp", "call"}:
        return False
    return _reg32(ins, ins.operands[0]) == reg


def _mem_field(ins: Any, operand: Any) -> tuple[str, int] | None:
    """Return ``(base register name, displacement)`` for ``[base + disp]``."""
    if operand.type != X86_OP_MEM:
        return None
    if operand.mem.index != 0 or operand.mem.segment != 0 or operand.mem.base == 0:
        return None
    try:
        base = ins.reg_name(operand.mem.base)
    except Exception:  # noqa: BLE001
        return None
    if not base:
        return None
    return base, int(operand.mem.disp)


def _jcc_target(ins: Any) -> int | None:
    for operand in getattr(ins, 'operands', None) or []:
        if operand.type == X86_OP_IMM:
            return int(operand.imm) & 0xFFFFFFFF
    return None


@dataclass(frozen=True)
class _Block:
    va: int
    end_va: int
    func_start: int
    base_reg: str
    dst_disp: int
    dst_reg: int
    len_reg: int
    temp_reg: int
    capacity_reg: int
    fail_target: int
    success_target: int | None
    orientation: str  # "fail" | "success"
    index: int
    len_field: tuple[str, int] | None = None

    @property
    def size(self) -> int:
        return self.end_va - self.va

    @property
    def capacity_name(self) -> str:
        return _name32(self.capacity_reg)


def _function_starts(code: _Region, instructions: list[Any]) -> list[int]:
    starts: set[int] = {code.vaddr}
    for ins in instructions:
        if ins.mnemonic != "call":
            continue
        target = _jcc_target(ins)
        if target is not None and code.contains(target):
            starts.add(target)
    return sorted(starts)


def _function_of(starts: list[int], addr: int) -> int | None:
    position = bisect.bisect_right(starts, addr) - 1
    return starts[position] if position >= 0 else None


def _match_block(instructions: list[Any], index: int, limit: int) -> _Block | None:
    """Match one inlined unsigned range check starting at ``instructions[index]``."""
    if index + 5 >= limit:
        return None
    cmp1 = instructions[index]
    if cmp1.mnemonic != "cmp" or len(cmp1.operands) != 2:
        return None
    cap = _reg32(cmp1, cmp1.operands[0])
    dst = _reg32(cmp1, cmp1.operands[1])
    if cap is None or dst is None or cap == dst:
        return None

    branch1 = instructions[index + 1]
    if branch1.mnemonic not in _FAIL_JCC:
        return None
    fail_target = _jcc_target(branch1)
    if fail_target is None:
        return None

    # ``mov T, CAP`` -- optionally preceded by runtime memory loads.
    cursor = index + 2
    temp: int | None = None
    block_limit = min(index + _MAX_BLOCK_INSTRUCTIONS, limit)
    while cursor < block_limit:
        ins = instructions[cursor]
        if ins.mnemonic == "mov" and len(ins.operands) == 2:
            dest = _reg32(ins, ins.operands[0])
            src = _reg32(ins, ins.operands[1])
            if src == cap and dest is not None and dest != cap:
                temp = dest
                cursor += 1
                break
            if _mem_field(ins, ins.operands[1]) is not None and dest is not None:
                cursor += 1
                continue
        return None
    if temp is None:
        return None

    # Up to two runtime memory loads may sit before ``sub T, dst``.
    inline_len: tuple[int, tuple[str, int]] | None = None
    while cursor < block_limit:
        ins = instructions[cursor]
        if ins.mnemonic == "mov" and len(ins.operands) == 2:
            dest = _reg32(ins, ins.operands[0])
            field = _mem_field(ins, ins.operands[1])
            if field is not None and dest is not None and dest not in {temp, cap, dst}:
                inline_len = (dest, field)
                cursor += 1
                continue
        break
    if cursor >= block_limit:
        return None
    sub_ins = instructions[cursor]
    if (
        sub_ins.mnemonic != "sub"
        or len(sub_ins.operands) != 2
        or _reg32(sub_ins, sub_ins.operands[0]) != temp
        or _reg32(sub_ins, sub_ins.operands[1]) != dst
    ):
        return None

    cursor += 1
    if cursor >= block_limit:
        return None
    cmp2 = instructions[cursor]
    if (
        cmp2.mnemonic != "cmp"
        or len(cmp2.operands) != 2
        or _reg32(cmp2, cmp2.operands[0]) != temp
    ):
        return None
    length = _reg32(cmp2, cmp2.operands[1])
    if length is None or length in {temp, cap, dst}:
        return None

    cursor += 1
    if cursor >= block_limit:
        return None
    branch2 = instructions[cursor]
    target2 = _jcc_target(branch2)
    if target2 is None:
        return None
    if branch2.mnemonic in _FAIL_JCC and target2 == fail_target:
        orientation = "fail"
        success_target = None
    elif branch2.mnemonic in _SUCCESS_JCC and target2 != fail_target:
        orientation = "success"
        success_target = target2
    else:
        return None

    end_va = int(branch2.address) + int(branch2.size)
    if end_va <= int(cmp1.address):
        return None
    return _Block(
        va=int(cmp1.address),
        end_va=end_va,
        func_start=-1,
        base_reg="",
        dst_disp=0,
        dst_reg=dst,
        len_reg=length,
        temp_reg=temp,
        capacity_reg=cap,
        fail_target=fail_target,
        success_target=success_target,
        orientation=orientation,
        index=index,
        len_field=inline_len[1] if inline_len is not None and inline_len[0] == length else None,
    )


def _reaching_mem_load(
    instructions: list[Any], index: int, reg: int
) -> tuple[str, int] | None:
    """Nearest definition of ``reg`` must be ``mov reg, [base+disp]``."""
    for cursor in range(index - 1, max(index - _MAX_LOOKBACK, -1), -1):
        ins = instructions[cursor]
        if not _writes_reg(ins, reg):
            continue
        if ins.mnemonic != "mov" or len(ins.operands) != 2:
            return None
        return _mem_field(ins, ins.operands[1])
    return None


def _attach_fields(instructions: list[Any], block: _Block) -> _Block | None:
    dst_field = _reaching_mem_load(instructions, block.index, block.dst_reg)
    if dst_field is None:
        return None
    if block.len_field is None:
        if _reaching_mem_load(instructions, block.index, block.len_reg) is None:
            return None
    return replace(block, base_reg=dst_field[0], dst_disp=dst_field[1])


def _collect_blocks(
    instructions: list[Any], starts: list[int]
) -> list[_Block]:
    blocks: list[_Block] = []
    limit = len(instructions)
    for index, ins in enumerate(instructions):
        if ins.mnemonic != "cmp":
            continue
        matched = _match_block(instructions, index, limit)
        if matched is None:
            continue
        matched = _attach_fields(instructions, matched)
        if matched is None:
            continue
        func_start = _function_of(starts, matched.va)
        if func_start is None:
            continue
        blocks.append(replace(matched, func_start=func_start))
    return blocks


# ---------------------------------------------------------------------------
# x86-64 encoders (32-bit registers only)
# ---------------------------------------------------------------------------


def _modrm(mod: int, reg: int, rm: int) -> int:
    return ((mod & 3) << 6) | ((reg & 7) << 3) | (rm & 7)


def _rex(r: int = 0, b: int = 0) -> int:
    value = 0x40
    if r >= 8:
        value |= 0x4
    if b >= 8:
        value |= 0x1
    return value


def _op_rr(opcode: int, rm: int, reg: int) -> bytes:
    """``op r/m32, r32`` (``89`` mov, ``29`` sub, ``39`` cmp)."""
    body = bytes([opcode, _modrm(3, reg, rm)])
    prefix = _rex(r=reg, b=rm)
    return body if prefix == 0x40 else bytes([prefix]) + body


def _rel8_ok(rel: int) -> bool:
    return -128 <= rel <= 127


def _branch(mnemonic: str, va: int, target: int) -> bytes:
    """Encode ``jb``/``jae`` to ``target`` from instruction address ``va``."""
    short_op = 0x72 if mnemonic == "jb" else 0x73
    near_op = 0x82 if mnemonic == "jb" else 0x83
    rel8 = target - (va + 2)
    if _rel8_ok(rel8):
        return bytes([short_op, rel8 & 0xFF])
    rel32 = target - (va + 6)
    return bytes([0x0F, near_op]) + int(rel32).to_bytes(4, "little", signed=True)


def _encode_rewrite(block: _Block, good_capacity: int) -> bytes:
    """Encode the corrected block, kept within the original byte length."""
    parts: list[bytes] = []
    parts.append(_op_rr(0x89, block.temp_reg, good_capacity))  # mov T, GOOD
    parts.append(_op_rr(0x29, block.temp_reg, block.dst_reg))  # sub T, dst
    parts.append(_branch("jb", block.va + sum(len(p) for p in parts), block.fail_target))
    parts.append(_op_rr(0x39, block.temp_reg, block.len_reg))  # cmp T, len
    branch_va = block.va + sum(len(p) for p in parts)
    if block.orientation == "fail":
        parts.append(_branch("jb", branch_va, block.fail_target))
    else:
        parts.append(_branch("jae", branch_va, int(block.success_target)))

    encoded = b"".join(parts)
    if len(encoded) > block.size:
        raise CapacityError(
            f"rewrite needs {len(encoded)} bytes but only {block.size} are available "
            f"at {hex(block.va)}"
        )
    return encoded + b"\x90" * (block.size - len(encoded))


def _verify_rewrite(
    patched: bytes, code: _Region, block: _Block, good_capacity: int, encoded: bytes
) -> None:
    start = code.offset_of(block.va)
    raw = patched[start:start + block.size]
    if raw != encoded:
        raise CapacityError("patched bytes do not match the encoded rewrite")
    decoded = list(_MD.disasm(raw, block.va))
    expected = [
        ("mov", lambda ins: _reg32(ins, ins.operands[0]) == block.temp_reg
         and _reg32(ins, ins.operands[1]) == good_capacity),
        ("sub", lambda ins: _reg32(ins, ins.operands[0]) == block.temp_reg
         and _reg32(ins, ins.operands[1]) == block.dst_reg),
        ("jb", lambda ins: _jcc_target(ins) == block.fail_target),
        ("cmp", lambda ins: _reg32(ins, ins.operands[0]) == block.temp_reg
         and _reg32(ins, ins.operands[1]) == block.len_reg),
    ]
    if block.orientation == "fail":
        expected.append(("jb", lambda ins: _jcc_target(ins) == block.fail_target))
    else:
        expected.append(("jae", lambda ins: _jcc_target(ins) == block.success_target))
    for position, (mnemonic, predicate) in enumerate(expected):
        if position >= len(decoded):
            raise CapacityError("rewrite does not decode to the expected block")
        ins = decoded[position]
        if ins.mnemonic != mnemonic or not ins.operands or not predicate(ins):
            raise CapacityError(
                f"rewrite instruction {position} decoded as {ins.mnemonic} {ins.op_str}"
            )
    for ins in decoded[len(expected):]:
        if ins.mnemonic != "nop":
            raise CapacityError(
                f"trailing padding decoded as {ins.mnemonic} {ins.op_str}, not nop"
            )


# ---------------------------------------------------------------------------
# Error message alignment (.rodata)
# ---------------------------------------------------------------------------


def _error_string_from(by_address: dict[int, Any], start: int) -> int | None:
    for cursor in range(start, start + 32):
        ins = by_address.get(cursor)
        if ins is None:
            continue
        if ins.mnemonic not in {"mov", "lea"} or len(ins.operands) != 2:
            continue
        if _reg32(ins, ins.operands[0]) != 7:  # edi
            continue
        src = ins.operands[1]
        if src.type != X86_OP_IMM:
            continue
        return int(src.imm) & 0xFFFFFFFF
    return None


def _message_action(
    data: bytes,
    regions: list[_Region],
    code: _Region,
    instructions: list[Any],
    by_address: dict[int, Any],
    block: _Block,
    siblings: list[_Block],
) -> tuple[dict[str, Any], bytes] | None:
    bad_va = _error_string_from(by_address, block.fail_target)
    if bad_va is None:
        return None
    bad_text = _read_cstring(regions, bad_va)
    if bad_text is None:
        return None
    bad_match = _MESSAGE_RE.match(bad_text)
    if bad_match is None:
        return None
    nouns: set[str] = set()
    for sibling in siblings:
        sibling_va = _error_string_from(by_address, sibling.fail_target)
        if sibling_va is None:
            return None
        sibling_text = _read_cstring(regions, sibling_va)
        if sibling_text is None:
            return None
        match = _MESSAGE_RE.match(sibling_text)
        if match is None:
            return None
        if match.group("prefix") == bad_match.group("prefix"):
            return None  # same branch wording: not a sibling destination error
        nouns.add(match.group("noun"))
    if len(nouns) != 1:
        return None
    good_noun = next(iter(nouns))
    if good_noun == bad_match.group("noun"):
        return None
    new_text = bad_match.group("prefix") + good_noun
    if len(new_text) >= len(bad_text):
        return None
    raw_old = bad_text.encode("ascii")
    raw_new = new_text.encode("ascii") + b"\x00" * (len(raw_old) - len(new_text))
    # The immediate must be referenced exactly once in code so no other caller
    # keeps the old, now-contradictory wording.
    needle = int(bad_va).to_bytes(4, "little")
    if code.data.count(needle) != 1:
        return None
    for region in regions:
        if not region.contains(bad_va, len(raw_old)):
            continue
        offset = region.offset_of(bad_va)
        if data[offset:offset + len(raw_old)] != raw_old:
            return None
        return (
            {
                "kind": "rodata_message_align",
                "offset": offset,
                "size": len(raw_old),
                "before_hex": raw_old.hex(),
                "after_hex": raw_new.hex(),
                "string_va": bad_va,
                "old_text": bad_text,
                "new_text": new_text,
            },
            raw_new,
        )
    return None


# ---------------------------------------------------------------------------
# Detection / repair
# ---------------------------------------------------------------------------


@dataclass
class _Analysis:
    report: CapacityReport
    blocks: list[_Block]
    code: _Region | None
    instructions: list[Any]
    regions: list[_Region]


def _analyse(data: bytes) -> _Analysis:
    report = CapacityReport(
        original_sha256=_sha(data),
        patched_sha256=_sha(data),
        format="unknown",
        arch="unknown",
        mode="unsupported",
        strategy="capacity",
        supported=False,
        status="unsupported",
    )
    try:
        elf = _elf(data)
    except CapacityError as exc:
        report.limitations.append(str(exc))
        return _Analysis(report, [], None, [], [])
    sections = _sections(elf)
    regions = list(sections.values()) + _load_regions(elf)
    try:
        code = _code_region(elf, sections)
    except CapacityError as exc:
        report.limitations.append(str(exc))
        return _Analysis(report, [], None, [], regions)
    report.format = "elf64-little"
    report.arch = "x86_64"
    if len(code.data) > MAX_CODE_BYTES:
        report.limitations.append(
            f"executable region is {len(code.data)} bytes, above the reviewed "
            f"capacity-check limit of {MAX_CODE_BYTES} bytes"
        )
        return _Analysis(report, [], code, [], regions)
    instructions = list(_MD.disasm(code.data, code.vaddr))
    if not instructions:
        report.limitations.append("capstone decoded no instructions in the code region")
        return _Analysis(report, [], code, [], regions)
    starts = _function_starts(code, instructions)
    blocks = _collect_blocks(instructions, starts)
    report.limitations.append(
        f"scanned {len(blocks)} inlined range-check block(s) in the code region"
    )
    return _Analysis(report, blocks, code, instructions, regions)


def _select_sites(
    blocks: list[_Block], code: _Region
) -> tuple[list[CapacitySite], list[str]]:
    limitations: list[str] = []
    groups: dict[tuple[int, str, int], list[_Block]] = {}
    for block in blocks:
        groups.setdefault(
            (block.func_start, block.base_reg, block.dst_disp), []
        ).append(block)
    sites: list[CapacitySite] = []
    for key, group in sorted(groups.items()):
        if len(group) < 3:
            continue
        counts: dict[int, list[_Block]] = {}
        for block in group:
            counts.setdefault(block.capacity_reg, []).append(block)
        if len(counts) != 2:
            continue
        minority = [reg for reg, items in counts.items() if len(items) == 1]
        majority = [reg for reg, items in counts.items() if len(items) >= 2]
        if len(minority) != 1 or len(majority) != 1:
            continue
        bad = counts[minority[0]][0]
        good_reg = majority[0]
        good_blocks = counts[good_reg]
        func_start, base_reg, dst_disp = key
        source_disp: int | None = None
        for block in blocks:
            if block.func_start != func_start or block.base_reg != base_reg:
                continue
            if block.dst_disp == dst_disp:
                continue
            if block.capacity_reg == bad.capacity_reg:
                source_disp = block.dst_disp
                break
        if source_disp is None:
            limitations.append(
                f"divergent capacity register {bad.capacity_name} at {hex(bad.va)} "
                "is not used as an input-size bound elsewhere in the function"
            )
            continue
        sites.append(
            CapacitySite(
                site_va=bad.va,
                file_offset=code.offset_of(bad.va),
                block_size=bad.size,
                dst_disp=dst_disp,
                base_reg=base_reg,
                bad_capacity=bad.capacity_name,
                good_capacity=_name32(good_reg),
                sibling_vas=tuple(sorted(block.va for block in good_blocks)),
                source_disp=source_disp,
                detail=(
                    f"destination check on [{base_reg}+{dst_disp}] compares against "
                    f"{bad.capacity_name} (input size, used for source checks at "
                    f"[{base_reg}+{source_disp}]) instead of the sibling capacity "
                    f"{_name32(good_reg)}"
                ),
            )
        )
    if len(sites) > 1:
        return [], limitations + [
            f"{len(sites)} independent divergent check groups found; this engine "
            "repairs exactly one reviewed group per candidate (fail-closed)"
        ]
    return sites, limitations


def detect_capacity_confusion(data: bytes) -> tuple[list[CapacitySite], list[str]]:
    """Return the divergent destination checks and human-readable limitations."""
    analysis = _analyse(data)
    if analysis.code is None or not analysis.blocks:
        return [], list(analysis.report.limitations)
    sites, limitations = _select_sites(analysis.blocks, analysis.code)
    return sites, limitations + list(analysis.report.limitations)


def repair_capacity_confusion(data: bytes) -> tuple[bytes | None, CapacityReport]:
    """Return patched bytes and a report, or ``(None, report)`` when unsupported."""
    analysis = _analyse(data)
    report = analysis.report
    if analysis.code is None or not analysis.blocks:
        return None, report
    sites, limitations = _select_sites(analysis.blocks, analysis.code)
    report.limitations.extend(limitations)
    if not sites:
        if not report.limitations:
            report.limitations.append("no divergent destination capacity check found")
        return None, report
    site = sites[0]
    block = next((item for item in analysis.blocks if item.va == site.site_va), None)
    if block is None:
        report.limitations.append("internal error: selected block disappeared")
        return None, report
    siblings = [
        item
        for item in analysis.blocks
        if item.func_start == block.func_start
        and item.base_reg == block.base_reg
        and item.dst_disp == block.dst_disp
        and item.capacity_reg != block.capacity_reg
    ]
    good_reg = _REG32[site.good_capacity]
    try:
        encoded = _encode_rewrite(block, good_reg)
    except CapacityError as exc:
        report.limitations.append(str(exc))
        return None, report

    patched = bytearray(data)
    offset = site.file_offset
    patched[offset:offset + block.size] = encoded
    try:
        _verify_rewrite(bytes(patched), analysis.code, block, good_reg, encoded)
    except CapacityError as exc:
        report.limitations.append(str(exc))
        return None, report

    actions = [
        CapacityAction(
            kind="capacity_check_rewrite",
            offset=offset,
            size=block.size,
            before_hex=data[offset:offset + block.size].hex(),
            after_hex=encoded.hex(),
            site_va=block.va,
            bad_capacity=site.bad_capacity,
            good_capacity=site.good_capacity,
        )
    ]
    by_address = {int(ins.address): ins for ins in analysis.instructions}
    message_actions: list[dict[str, Any]] = []
    message = _message_action(
        bytes(patched), analysis.regions, analysis.code, analysis.instructions,
        by_address, block, siblings,
    )
    if message is not None:
        action, new_bytes = message
        message_offset = int(action["offset"])
        patched[message_offset:message_offset + len(new_bytes)] = new_bytes
        message_actions.append(action)

    # Whitelist check: nothing outside the recorded actions may change.
    allowed = [(int(item.offset), int(item.size)) for item in actions] + [
        (int(item["offset"]), int(item["size"])) for item in message_actions
    ]
    for index in range(len(data)):
        if data[index] == patched[index]:
            continue
        if not any(start <= index < start + size for start, size in allowed):
            report.limitations.append(
                f"unrecorded byte change at file offset {index}; no patch written"
            )
            return None, report

    report.mode = "capacity-check"
    report.supported = True
    report.status = "patched"
    report.sites = sites
    report.actions = actions
    report.message_actions = message_actions
    report.patched_sha256 = _sha(bytes(patched))
    report.limitations.extend([
        "In-place rewrite of one reviewed inlined range-check block; no code cave, "
        "no segment or program-header change.",
        "Semantic equivalence of the rewritten predicate is established by the "
        "duplicated check shape and verified end-to-end by the supplied "
        "PoC/regression cases; this is not a whole-program proof.",
    ])
    return bytes(patched), report


__all__ = [
    "CapacityAction",
    "CapacityError",
    "CapacityReport",
    "CapacitySite",
    "detect_capacity_confusion",
    "repair_capacity_confusion",
]
