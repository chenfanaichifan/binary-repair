# Two AI binary repair paths

Status: implemented on `feature/ai-binary-repair` (post-v5).  Acceptance:
[`docs/acceptance/ai-binary-repair-2026-11-13.md`](../acceptance/ai-binary-repair-2026-11-13.md).

These are the two product paths requested for fixing a binary such as an ELF:

| # | Path ID | What happens |
|---|---|---|
| 1 | `asm_roundtrip` | binary → disassemble the target function to **assembly text** → AI repairs the assembly → host assembler turns it back into machine code → inject into a new executable block → redirect the original function entry → patched binary |
| 2 | `binary_direct` | binary → AI emits **raw bytes** (machine-code guard bytes or same-length in-place edits) → validator → existing writer injects/patches directly → patched binary; **no assembly text and no decompiled-C round-trip** |

Both end in the same deterministic reparse/runtime/gate.  The AI never owns the
acceptance decision: it cannot promote a failed, incomplete or missing gate.
Path 1 deliberately uses assembly text; path 2 deliberately does not.

## Path 1 — `asm_roundtrip`

```text
original ELF
  -> deterministic container/import/stack analysis
  -> Capstone disassembly of the target function (read-only)
  -> bounded packet: disassembly, sink (kind/callee/capacity/dest_rel), ABI
  -> model returns {schema_version:1, assembly:"<replacement function>"}
  -> fail-closed text validation (no calls/syscalls/privileged/indirect jumps)
  -> clang integrated assembler (target triple) -> machine-code bytes
  -> Capstone validation of the assembled block (complete decode, allowlist,
     internal branch targets, terminating instruction)
  -> existing ELF injection primitive allocates a new R-X block
  -> x86/i386: E9 rel32 at the original function entry; arm64: B imm26
  -> reparse + runtime + deterministic gate
```

- Supported inputs: ELF i386, x86_64, arm64.  PE/Mach-O return `unsupported` for
  this path (path 2 covers them).
- The model **writes assembly**, not bytes/C.  The assembler is the host `clang`
  (cross-target `i386-linux-gnu`, `x86_64-linux-gnu`, `aarch64-linux-gnu`); when
  clang is absent the path fails closed.
- The replacement function is injected as a block and the original function
  entry is redirected to it.  The original body is not preserved; this is
  reported as a limitation/action (`assembly-function`).
- The gate executes the patched function entry (jump → assembled block) and
  checks canary/return-slot/buffer semantics exactly like the deterministic path.

## Path 2 — `binary_direct`

```text
original binary
  -> bounded analysis packet (metadata + executable ranges + sink offsets)
  -> model returns raw patch
       guard sink:    {schema_version:1, sink_index, inject:{code_hex}}
       immediate sink:{schema_version:1, sink_index, edits:[{offset,before_hex,after_hex}]}
  -> fail-closed validator: Capstone decode, instruction allowlist, no
     calls/syscalls/privileged/indirect jumps, internal branches, injection/
     redirect ranges, same-length executable edits, container reparse
  -> existing writer injects/call-redirects or rewrites bytes
  -> reparse + runtime + deterministic gate
```

Supported by the existing repair matrix: ELF/PE/Mach-O x86_64/arm64 and
ELF32/PE32 i386.  On macOS, Mach-O candidates are checked by the native runtime
gate; on Linux they are reported as not verified (native Mach-O execution is a
macOS-only capability).

## Shared properties

- **No C decompilation and no C recompilation** on either path.
- **No model-owned verdict**: the deterministic gate is the only authority.
- `static_only` remains explicit opt-in, unverified and never success.
- Invalid AI output (parse error, forbidden assembly/bytes, bad offsets, bad
  injection) returns no candidate with a typed `ai.status`.
- The runtime `buffer_match` check rejects a structurally valid but semantically
  empty injected guard (e.g. a lone `ret`).

## Surfaces

| Surface | Value |
|---|---|
| API | `GET /api/binary/ai-paths`, `POST /api/binary/ai-repair` (`path=asm_roundtrip|binary_direct`) |
| CLI | `scripts/repair_binary.py ... --ai-path asm_roundtrip|binary_direct` |
| UI | `/binary` AI section: path 1 assembly round-trip card, path 2 direct binary card |
| Evidence | `scripts/capture_ai_binary_repair.py` → `artifacts/ai-direct-binary-2026-11-13/` |
| Provider | existing `client_from_env` client; tests/scripted evidence inject a fake client and do no network I/O |

## Boundaries

- Assembly path is ELF i386/x86_64/arm64 only; no PE/Mach-O assembly round-trip.
- Assembly path needs host `clang`; CI Ubuntu installs it and macOS has it.
- One sink/target function per AI candidate; multi-function selection remains
  future work.
- Scripted evidence proves protocol/assembler/validator/writeback/gate
  integration, not real-LLM repair quality; **no AI increment is measured on
  the current fixtures**.  PoC-failure is not yet a gate predicate.
- Mach-O direct-path positive evidence is native and macOS-only; on Linux those
  tests skip by platform design.

## Previous protocol names

The earlier prototype exposed internal names `ai_plan` and `ai_bytes`.  They are
retained only for internal unit tests/helpers and are not in `AI_PATHS`, the API
contract or the UI.  The product paths are exactly `asm_roundtrip` and
`binary_direct`.
