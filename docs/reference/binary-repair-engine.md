# Direct binary repair engine

## What it does

`app/services/binary_repair_engine.py` repairs an ELF **without converting it
to assembly text and reassembling it**:

```text
ELF bytes
  -> capstone decodes instructions for analysis only
  -> locate immediate read/write lengths and nearest sub rsp, N
  -> patch the imm32 in the original file bytes
  -> re-decode and verify the patched instruction
  -> emit patched ELF + JSON report
```

The original `.text` bytes are not regenerated.  No instruction is assembled
from text.

## CLI

```bash
.venv/bin/python scripts/repair_binary.py \
  artifacts/vuln-elf/vuln.elf \
  /tmp/vuln-patched.elf \
  --report /tmp/vuln-patched.json
```

For the known fixture it returns the reviewed **strict** binary.  For a modified
ELF with the same immediate pattern it returns a **bounds-only** patch.

Scan without writing:

```bash
.venv/bin/python scripts/repair_binary.py artifacts/vuln-elf/vuln.elf --scan-only
```

## API / GUI

### Structured review path

`POST /api/binary/repair-review` accepts a binary plus optional `ai_review=1`
and returns a verified packet even for unsupported inputs:

```json
{
  "ok": true,
  "candidate_available": true,
  "download_allowed": true,
  "filename": "vuln-fixed.elf",
  "patched_base64": "... only when the gate succeeded ...",
  "report": { "schema_version": 2, "mode": "strict", "capacity": 16, "...": "..." },
  "verification": {
    "schema_version": 1,
    "scope": { "format": "elf64-little", "arch": "x86_64", "mode": "strict", "...": "..." },
    "checks": [{"id": "runtime.no_overflow", "status": "passed", "...": "..."}],
    "missing": [],
    "report_sha256": "...",
    "gate": { "success": true, "outcome": "success_within_scope", "...": "..." }
  },
  "review": {
    "requested": true,
    "called": true,
    "status": "review_ok",
    "recommendation": "accept",
    "summary": "...",
    "concerns": [],
    "missing_evidence": [],
    "further_checks": [],
    "contribution": {"changed": false, "effect": "concurred"}
  },
  "decision": {
    "success": true,
    "outcome": "success_within_scope",
    "authority": "deterministic_gate",
    "gate_outcome": "success_within_scope"
  }
}
```

The gate is derived from the engine report and the Unicorn runtime evidence
using `app.domain.acceptance.decide_attempt_outcome()`. Missing runtime evidence
is `inconclusive`; a failed check is `rejected`; an unsupported format/pattern is
`unsupported`. `patched_base64` is absent unless the gate succeeded.

`POST /api/binary/quick-repair` remains as the legacy one-click API. It now
fails closed (422) when the structured gate does not pass, so it cannot return a
candidate with missing evidence. `GET /api/binary/review-contract` describes the
review-only boundary.

### AI review

`ai_review=1` sends only the structured packet above to the configured provider;
it never sends the binary bytes or source. The model may recommend `accept`,
`hold` or `needs_more_checks`. A hold can veto a passing gate; an accept cannot
promote a failed gate. The full decision table is in
[`docs/architecture/ai-adjudication.md`](../architecture/ai-adjudication.md).

## Supported

- little-endian **ELF64 x86-64**;
- `.text` section;
- `sub rsp, N` followed by a syscall whose `edx` is an **immediate** larger than
  `N` (read/write);
- `call memcpy` with an immediate `edx` and a stack destination derived from
  `rdi = rsp` / `lea rdi, [rsp+off]`;
- ELF64 x86-64 format detection; PE/Mach-O are reported as unsupported rather
  than patched.

It patches the immediate in place.  That is a genuine binary-level fix for the
buffer length; it does **not** rewrite the whole control flow.

## Strict fixture

For the generated `vuln.elf` digest, the engine returns a separately reviewed
strict template:

```text
read loop up to EOF / 17
cmp total, 16
ja reject
write only total
exit 1 on >16
```

This closes the short-read disclosure and truncation semantics.

## Fail-closed

The engine returns `unsupported` and no output when:

- input is not ELF64 x86-64;
- `.text` cannot be parsed;
- read/write length is not an immediate;
- no `sub rsp` capacity is found;
- a patch would need a new segment, relocation, or code cave.

No arbitrary machine code is guessed.

## Why "any binary" is not one algorithm

Arbitrary binary repair needs:

- relocation/GOT/PLT rewriting;
- PIE and shared-library awareness;
- data/code separation and function boundaries;
- calling-convention and stack-frame recovery;
- code caves or new loadable segments;
- PE/Mach-O support;
- isolated runtime regression.

This engine covers a deliberately safe subset and keeps expanding by adding
verified patterns.  It does not claim universal automatic repair.

## Runtime verification

`app/services/x86_runtime.py` uses Unicorn to execute the ELF's own x86-64
instructions with modeled `read`/`write`/`exit` syscalls.  It checks:

- valid/boundary input echo;
- over-limit rejection;
- exit status;
- stack sentinel beyond the buffer;
- partial reads.

It is a test oracle, not a host sandbox.  Final acceptance still belongs in a
disposable x86-64 Linux guest.

## Unified pipeline v4 (container-neutral, 2026-11-13)

`app/services/binary_pipeline.py` is the format-detecting entry point:

```python
from app.services.binary_pipeline import scan_binary, repair_binary

scan = scan_binary(data)                 # ELF / PE / Mach-O analysis
patched, report = repair_binary(data)    # fail-closed candidate + report v3
```

The v4 pipeline is built from four container-neutral layers:

```text
app/services/containers.py        format/arch detection, sections, imports
app/services/repair/analyzer.py   frame capacity + copy sinks
app/services/repair/guards.py     bounded-copy guards for 3 ABIs
app/services/repair/writer.py     immediate clamp, cave injection, call redirect
app/services/runtime/*            native Mach-O / Unicorn runtime evidence
app/services/unified_verification.py  deterministic gate
```

Routing:

```text
ELF64 x86-64   -> legacy strict-template / immediate / cave engine + old gate
ELF64 arm64    -> analyzer -> guard cave -> Unicorn gate
PE32+ x86-64   -> analyzer (IAT + thunk) -> guard cave -> Unicorn gate
PE32+ arm64    -> analyzer (IAT + adrp/ldr/br thunk) -> guard cave -> Unicorn gate
Mach-O 64      -> analyzer (stubs/bindings) -> guard cave -> native gate
other          -> unsupported, no candidate
```

Supported sinks:

1. `strcpy`/`strcat`/`stpcpy`/`memcpy`/`memmove` calls whose target resolves to
   a PLT entry, an IAT/thunk, or a Mach-O stub;
2. stack destination recovered from `lea rdi/rcx, [rsp/rbp ± K]`,
   `mov reg, rsp` or `add x0, sp, #K`;
3. capacity `frame_top - destination` with `frame_top` from `sub rsp, N`,
   `rbp`, or `sub sp, sp, #N`;
4. immediate lengths (`mov edx/r8d, imm`, `mov x2, #imm`, `mov w2, #imm`) for
   `memcpy`/`memmove` and raw `syscall` read/write;
5. checked-copy calls (`__memcpy_chk`, `__strcpy_chk`, `__strcat_chk`) use the
   explicit destination-size argument.

Repair actions:

- **immediate clamp**: rewrite the imm32 (x86-64) or MOVZ immediate (arm64);
- **guard cave**: append a new executable PE section / Mach-O `__brfix` section /
  ELF `PT_LOAD` containing a capacity-bounded copy guard, then redirect the call
  with `E8 rel32` (x86-64) or `BL` (arm64).

The gate in `app/services/unified_verification.py` requires: same container and
architecture after reparse, matching hashes, at least one action, and runtime
evidence whose tier is `native_run` or `emulated_run` with every case inside the
capacity. `static_only` is `not_verified` and never a success.

## Why "any binary" still has a boundary

The v4 pipeline removes the container limitation: ELF, PE and Mach-O, x86-64
and arm64, imported and direct calls. It does not remove the **information**
limitation:

- a capacity is only recoverable when the frame geometry or an explicit
  `_chk` size carries it;
- 32-bit, big-endian, fat Mach-O rewriting and heap/global buffers are
  detected but fail closed;
- `sprintf` format expansion is not repaired;
- frame geometry is not DWARF object size (see the acceptance record).

Everything outside the matrix returns `unsupported` with a reason. That is the
intended behavior, not a missing success.
