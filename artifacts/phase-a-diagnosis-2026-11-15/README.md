# Phase A: cave relocation root cause (2026-11-15)

`hard-multicall` candidate crashed on the valid `hi` input too.  Telemetry
showed the executed cave had `call 0x2a`/`call 0x33` (zero-displacement `e8 00
00 00 00`), while the candidate file also contained correctly relocated bytes at
an unrelated file offset.

Root cause: the injected cave VA (`0x10cf000`) falls inside the virtual range of
`.tbss` (SHT_NOBITS).  `_patch_binary_call_relocations` tried section mapping
first, got the `.tbss` file offset, and patched those bytes; the executable
PT_LOAD segment kept the zero call displacements.  Fix: always map the cave VA
through PT_LOAD program headers before falling back to section mapping.

After the fix:

- valid inputs pass;
- `hard-multicall` still had no bounds guard (model semantics) until the
  RepairSpec planner was introduced;
- `hard-nonconst` immediately became AI verified;
- ABI checker now uses CFG-aware stack tracking, so equivalent branch epilogues
  are not false fatal, and the fixed cave reports `ok=true`.
