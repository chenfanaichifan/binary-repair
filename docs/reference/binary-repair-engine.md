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

## Unified pipeline v5 (universal repair entry, 2026-11-13)

v5 keeps the v4 container-neutral layers and adds an explicit, matrix-driven
"any input" entry. The single source of truth is
`app/services/repair_matrix.py`; pipeline, verification, API and CLI all read
it, so a cell cannot silently enter verified coverage.

### Repair matrix

| container | bits | arch | strategies | runtime tier |
|---|---|---|---|---|
| ELF | 32 | i386 | immediate, guard | `emulated_run` (Unicorn x86-32) |
| ELF | 64 | x86_64 | strict-template, immediate, guard | `emulated_run` |
| ELF | 64 | arm64 | immediate, guard | `emulated_run` |
| PE | 32 | i386 | immediate, guard | `emulated_run` (Unicorn x86-32) |
| PE | 32+ | x86_64 | immediate, guard | `emulated_run` |
| PE | 32+ | arm64 | immediate, guard | `emulated_run` |
| Mach-O | 64 | x86_64 | immediate, guard | `native_run` (macOS only) |
| Mach-O | 64 | arm64 | immediate, guard | `native_run` (macOS only) |

Supported sink classes: `unbounded_copy` (strcpy/strcat/stpcpy, guard) and
`immediate_length` / `memcpy_length` / `syscall_length` / `checked_copy`
(immediate clamp). Sinks must have a recoverable capacity: frame geometry
(`frame_top - destination`) or an explicit `_chk` size.

Outside the matrix (detected, analysed, **never rewritten**): 32-bit Mach-O,
fat Mach-O, arm32, riscv, mips, powerpc, big-endian containers, and copy sinks
whose capacity cannot be recovered. Heap/global buffers, `sprintf` format
expansion, UAF/integer/loop defects and obfuscated code are not repaired.

### Dispositions

`repair_any(data)` (and `/api/binary/repair`, `scripts/repair_binary.py`)
returns exactly one disposition:

| disposition | candidate | verified | meaning |
|---|---|---|---|
| `verified_patch` | yes | yes | in-matrix repair action + native/emulated gate passed |
| `static_only_patch` | yes | no | action exists, no runtime evidence; **explicit opt-in only** |
| `not_verified` | no | no | action exists but static-only delivery was not requested |
| `analysis_only` | no | no | recognised container, no patchable sink |
| `unsupported` | no | no | recognised container outside the matrix |
| `rejected` | no | no | deterministic gate rejected the candidate |
| `invalid` | no | no | empty, oversized, malformed or unrecognised input |

`static_only` is never success, never used for an accept decision, and must be
requested with `allow_static_only=1` (API) / `--allow-static-only` (CLI) /
the page checkbox. A gate failure always drops the candidate.

### Python / HTTP / CLI / UI

```python
from app.services.binary_pipeline import repair_any, scan_binary
from app.services.repair_matrix import matrix_payload

scan = scan_binary(data)                 # schema v4 analysis, never executes
outcome = repair_any(data)               # verified candidate or explicit refusal
outcome.candidate, outcome.verified, outcome.download_allowed, outcome.report
matrix = matrix_payload()                # English ASCII matrix/coverage contract
```

- `POST /api/binary/scan` — multipart `binary` + `csrf`; schema v4 scan.
- `POST /api/binary/repair` — multipart `binary` + `csrf`, optional
  `allow_static_only`, `backend`, `strategy`; 200 with `verified`, `disposition`,
  `delivery`, `patched_base64`, `report`; 422 with report when no candidate.
- `GET /api/binary/matrix` — matrix/dispositions/non-goals (English ASCII).
- `GET /binary` — 「任意二进制修复」page: upload → scan → repair → disposition
  badge → download only when `delivery.download_allowed` is true.
- `scripts/repair_binary.py` — single/batch, `--allow-static-only`, `--scan-only`;
  batch summary counts `verified`/`static_only`/`analysis_only`/`unsupported`/
  `rejected`/`invalid`/`error` plus legacy `ok`.

Report `schema_version` is 4. New additive fields: `disposition`, `matrix`
(cell/repairable/strategies/runtime_tiers/sink_classes), `delivery`
(download_allowed/verified/tier), `coverage` (sink classes/non-goals), `slices`
(fat Mach-O metadata) and `warnings`. Existing v3 fields and statuses remain.

### i386 specifics (32-bit x86)

- analyzer: Capstone `CS_MODE_32`; cdecl frame model (`push ebp; mov ebp,esp`,
  `sub esp,N`), destination from `lea reg,[ebp-K]` / `[esp+K]`; call resolution
  for `E8 rel32` (PLT or symbol, including static-musl symtab `strcpy`) and
  `call [IAT]` (`FF15`); only **push-materialised** cdecl arguments are modelled
  in v1, so `mov [esp+k],reg`-style argument setup is fail-closed (documented
  limitation, keeps the `i386-control` fixture a negative control).
- writer: imm32 clamp; `E8 rel32` redirect (NOP-padded from 6-byte `FF15`);
  guard blob injected as a new ELF32 `PT_LOAD` (32-bit program header) or a new
  PE32 `.brfix` R-X section; reparse must still identify the same container/arch.
- runtime: Unicorn `UC_ARCH_X86` + `UC_MODE_32`, 4-byte sentinel/canary, cdecl
  stack argument, call-site/import hook; `tier=emulated_run`,
  `engine=unicorn-i386`; the emulated run is instruction-level evidence, not a
  native Linux/Windows run.

### Fail-closed behavior

- `repair_binary(..., verify=False)` still returns bytes for compatibility, but
  the report is `not_verified` / `static_only_patch` with `verified=false`.
- A failed gate (`rejected`) clears `candidate_available` and returns no bytes;
  the historical ELF x86-64 fail-open path is removed.
- Malformed/unknown/oversized input is `invalid`; matrix-outside input is
  `unsupported`; in-matrix without a patchable sink is `analysis_only`.

See [`docs/acceptance/binary-universal-v5-2026-11-13.md`](../acceptance/binary-universal-v5-2026-11-13.md)
for the v5 acceptance matrix and evidence.

### v5.1 advanced i386 coverage

- dynamic ELF32: `PT_INTERP` + `.plt` images resolve imports through the
  i386 `FF25 abs32` PLT stub decoder (glibc `x86-linux-gnu` fixture);
- PE32 direct IAT: `call dword ptr [__imp_x]` (`FF 15 abs32`) is resolved and
  rewritten to `E8 rel32` + one NOP (6-byte call site; fixture
  `vuln-strcpy-x86-iat.exe`);
- immediate-length i386: `memcpy(dst, src, 64)` with a `push imm32` length is
  clamped in place to the recovered stack capacity; the Unicorn runtime is
  length-aware for memcpy/memmove (reads the length argument per ABI) so the
  patched candidate can pass the deterministic gate as `verified_patch`;
- fat Mach-O is detected, each slice is reported with per-slice architecture
  support (`slices[].supported`) but the container is `analysis_only`
  (`container_rewrite=false`); fat rewriting remains outside v5;
- a candidate repairs **one function**: the guard sink (or earliest call site)
  chooses the function, and only sinks in that function are patched. Other
  function sinks are reported as a limitation, keeping every shipped action
  inside the runtime-verified function.
