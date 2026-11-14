# Capacity-check repair (integrated profile)

> Status 2026-11-14: re-integrated into the main coverage branch (see
> `docs/operations/capacity-decision-2026-11-14.md`). The engine is unchanged;
> the acceptance model is now the declared `native_poc_rewrite` evidence
> profile: `patch.capacity` + `patch.rewrite` re-derive every rewrite action
> from the original/candidate bytes and the supplied PoC/regression manifest is
> the only runtime evidence. Without that evidence the result is
> not_verified/inconclusive, never verified_patch.

Status: implemented (2026-11-14) for **ELF64 little-endian x86-64 only**, as a
bounded reviewed repair class.  It is not a general vulnerability rewriter and it
is not a whole-program proof.

| Area | Location |
|---|---|
| Engine | `app/services/repair/capacity.py` (`detect_capacity_confusion`, `repair_capacity_confusion`) |
| Pipeline | `app/services/binary_pipeline.py` (`_attempt_capacity`, `_finish_capacity`, `repair_any`) |
| Gate | `app/services/unified_verification.py` (`patch.capacity`, PoC differential as runtime evidence) |
| API | `POST /api/binary/repair-review` (optional `poc_manifest` form field), `POST /api/binary/repair` |
| GUI | `/agent` quick-repair card: optional `PoC / 回归用例清单（可选，JSON）` picker, `data-testid="agent-poc-manifest"` |
| Fixtures | `fixtures/elf/vuln-capacity-confusion-x86_64.elf`, `fixtures/poc/marcx-capacity.json`, synthetic compiler-variant `fixtures/hard-cases/vuln-capacity-param-x86_64.elf` |

## 1. The defect class

A compiler inlines a copy-destination bounds check into several nearly identical
blocks, one per operation kind.  Every block computes the same predicate:

```c
/* range_ok(dst_off, len, capacity) */
dst_off + len <= capacity
```

and emits it as an unsigned two-branch check:

```asm
cmp  cap, dst          ; dst > cap ?
jb   fail
mov  t, cap
sub  t, dst            ; t = cap - dst
cmp  t, len
jae  copy              ; cap - dst >= len
```

Two or three of those inlined siblings agree on the capacity variable (the
destination buffer's size), but **one copy compares against a different variable
that happens to hold the input size**.  Because that copy also computes
`input_size - dst` before comparing with `len`, it is *self-consistent*: it looks
exactly like a correct range check in isolation.  It is only visibly wrong when
compared with the agreeing siblings that guard the same destination field, and
only exploitable when the two capacities differ (for example a sparse container
that permits `out_size < data_size`).

This is CWE-131 (incorrect calculation of buffer size), CWE-697 (incorrect
comparison) and CWE-787 (out-of-bounds write), in that order of contribution: the
comparison is wrong because the capacity is wrong, and the consequence is an
out-of-bounds write through a runtime-length `memcpy`/`memset`.

Why the existing engines miss it:

- the copy length is a **runtime value** loaded from input, not an immediate, so
  immediate-length clamping patterns cannot see it;
- the frame has no canary/stack-capacity signal, so stack-capacity analysis has
  nothing to anchor on;
- nothing is imported from a recognised copy helper in the usual sense: the
  vulnerable call is an inlined branch pair followed by an ordinary `memcpy`.

Trigger conditions for the marcx example (all required): sparse flag set,
`out_size < data_size`, at least one span operation, source range legal,
destination range legal **against the wrong (input) capacity**, destination range
illegal against the real output capacity, and a correct CRC when required.

## 2. Detection preconditions (fail-closed)

The engine is deliberately narrow and only emits a candidate when **all** of the
following hold; otherwise it returns no candidate (or `unsupported` for other
container/architectures) and the caller keeps its normal disposition:

1. Container is ELF64 little-endian x86-64; `.text` is readable via section
   headers (with a program-header fallback).  The executable region must be at
   most 2 MiB: detection decodes the whole region, so larger images are rejected
   explicitly (`unsupported`, no candidate) instead of paying an unbounded decode
   cost.
2. A *pattern block* matches, in order:
   `cmp Ra, Rb` (reg32/reg32, `Ra != Rb`) → conditional branch →
   `mov T, Ra` → `sub T, Rb` → `cmp T, Rl` → conditional branch.
   Only the **unsigned, strict** predicate forms are accepted:
   the first branch must be `jb` to the failure target, and the second branch is
   either another `jb` to the same failure target or `jae` to the copy
   continuation.  In the common orientation the capacity register is copied to a
   distinct temp register (`T != Ra`); the "reuse the capacity register as its
   own temp" shape is rejected because restoring its value for later siblings is
   not provable in place.
3. `Rb` (destination offset) is defined by `mov Rb, [BASE+disp]` shortly before
   the block.  `Rl` (length) may be defined the same way before the block or by a
   `mov Rl, [mem]` inside it; either way the load proves the copy length is a
   runtime value rather than an immediate.
4. Blocks are grouped by `(function start, BASE, dst_disp)`.  Function starts are
   recovered from direct `call` targets in the executable region (a bounded
   heuristic; unresolvable images are skipped).  The group must contain **at
   least three** blocks and the capacity identities must contain **exactly one
   minority value**.  A capacity identity is the register's reaching definition:
   a `mov reg, [BASE+disp]` field load, a chain of register moves, or an opaque
   argument register.
5. The minority capacity identity must also be used as the capacity in another
   check in the same function against a **different displacement** of the same
   `BASE`.  That is the evidence that it is the input-size variable, not a
   second legitimate capacity.
6. The minority block is rewritten **in place, same byte length** (NOP padding)
   into the sibling-consistent form:

   ```asm
   mov  T, GOOD_CAP
   sub  T, dst         ; CF set exactly like the dropped "cmp GOOD_CAP, dst"
   jb   FAIL
   cmp  T, len
   jae  COPY           ; or "jb FAIL" when the original was fail/fail
   nop ...
   ```

   The rewrite is re-decoded and every byte outside the recorded actions is
   checked to be unchanged before the candidate is returned.
7. Optional, only when safe: if the patched block's error message differs from
   its agreeing siblings only by the buffer noun (`... outside the payload pool`
   vs `... outside the output`), the `.rodata` string is aligned to the sibling
   wording.  These are recorded as `message_actions`, **not** as `.text`
   actions, and are cosmetic only.

No SHA-256 is special-cased anywhere in detection: the marcx fixture is found by
the structural preconditions above, and a separately built synthetic C fixture
with the same three-sibling structure is repaired by the same engine.

## 3. Worked example: `marcx`

Test fixture in the repository:
`fixtures/elf/vuln-capacity-confusion-x86_64.elf`
sha256 `72fb53cbac09f576e037f730b07a7850ce8e129fb8c9a72c2c707c121d54b0d5`
(713,160 bytes, static stripped ELF64 x86-64 `ET_EXEC`).

Detected site (exactly one, no SHA special-casing):

| Field | Value |
|---|---|
| `site_va` | `0x4020d9` |
| file offset | `0x20d9` (`.text` at vaddr `0x401180` / file `0x1180`) |
| `block_size` | 16 bytes |
| `base_reg` | `r15` (header structure pointer) |
| `dst_disp` | 4 (`dst_off` field of the operation) |
| `bad_capacity` | `ebx` (input `data_size`) |
| `good_capacity` | `r12d` (output `out_size`, used by the agreeing siblings) |
| sibling checks | `0x401f97` (literal branch), `0x40208a` (fill branch) |
| source_disp | 8 (`len` field; proves the length is a runtime value) |

Before (16 bytes at `0x4020d9`, hex `39f3720c89df29f739d70f83c4feffff`):

```asm
0x4020d9  39 f3                cmp  ebx, esi        ; ebx = data_size, esi = dst_off
0x4020db  72 0c                jb   0x4020e9        ; fail only if data_size < dst_off
0x4020dd  89 df                mov  edi, ebx
0x4020df  29 f7                sub  edi, esi        ; edi = data_size - dst_off
0x4020e1  39 d7                cmp  edi, edx        ; ... >= len ?
0x4020e3  0f 83 c4 fe ff ff    jae  0x401fad        ; -> memcpy(out + dst_off, ...)
```

After (same 16 bytes, hex `4489e729f7720939d70f83c5feffff90`):

```asm
0x4020d9  44 89 e7             mov  edi, r12d       ; r12d = out_size
0x4020dc  29 f7                sub  edi, esi        ; edi = out_size - dst_off, CF on dst > cap
0x4020de  72 09                jb   0x4020e9        ; fail if out_size < dst_off
0x4020e0  39 d7                cmp  edi, edx        ; ... >= len ?
0x4020e2  0f 83 c5 fe ff ff    jae  0x401fad        ; -> memcpy(out + dst_off, ...)
0x4020e8  90                   nop
```

Equivalence: the original error branch was `dst_off > data_size`; the rewrite
replaces it with `dst_off > out_size` via the carry flag of `sub` (the dropped
`cmp GOOD_CAP, dst`).  For the `dst_off == capacity` boundary, both forms fall
through the first branch and then fail the `cap - dst >= len` compare because the
copy length is non-zero, so the predicate is preserved for unsigned values.

Recorded actions and side effects:

- `.text` action: 16-byte in-place rewrite at file offset `0x20d9`; **no code
  cave, no segment or program-header change**.
- `.rodata` message action at vaddr `0x483800` (file offset `0x83800`):
  `op[%u]: span destination outside the payload pool` →
  `op[%u]: span destination outside the output`, zero-padded to the original
  length (49 bytes).  Cosmetic alignment with the sibling branches, recorded
  separately from the `.text` actions.
- Binary diff outside the recorded regions: none (27 differing bytes across the
  16-byte `.text` window and the 49-byte message window).
- Candidate sha256: `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2`.

A second, independently built compiler-variant fixture
(`fixtures/hard-cases/vuln-capacity-param-x86_64.elf`, sha256
`371b9edd51b72764f0a3e821f47c0ba8286ba7540b749fcb8a658aec3e6346a5`; C source
`fixtures/hard-cases/capacity_confusion.c`; CAP1 archive helper
`fixtures/hard-cases/gen_capacity_archives.py`) has the same three-sibling shape
with a different register allocation (`rbx` base, `ebp` bad capacity, `r12d`
good capacity) and a 12-byte rewrite block at `0x401eb3` (patched sha256
`5b6501b058f24591d9aa4cc954acf6cb6dbcb29bdf445fe9f70480645fdb4322`).  It is
repaired by the same engine, and its PoC differential is exercised when a guest
runner is available; it exists so the tests prove the engine is not keyed to the
marcx bytes.

## 4. Verification profile

A `capacity` candidate is only reported as `verified_patch` when the
deterministic gate passes **every required check**.  For this profile the
verification packet (`verification` in the API payload, `schema_version: 2`)
contains:

| Check | Source of truth |
|---|---|
| `format` | ELF/x86-64 is in the repair matrix |
| `candidate.present` | candidate bytes exist |
| `candidate.identity.original` / `.patched` | SHA-256 re-derived from the actual bytes |
| `container.reparse` | patched bytes re-parse as the same container |
| `repair.action` | at least one recorded repair action |
| `patch.capacity` | **re-derived from the bytes**: for every action the original slice equals `before_hex` and the candidate slice equals `after_hex`; detail lists action count, site vaddrs and the register substitution (`ebx->r12d`) |
| `runtime.evidence` | the supplied PoC/regression differential actually ran and passed (`runner=... tier=... source=poc_manifest`) |
| `runtime.tier` | tier is `native_run` or `emulated_run`, never static-only |
| `runtime.contract` | the differential passed |
| `poc.native.available` / `.original_failure` / `.candidate_pass` / `.regression` | per-case results from the manifest run |

Runtime evidence is a **real differential execution in a Linux guest**:

- `native_run` — a native Linux x86-64 host;
- `emulated_run` — qemu-user or a Lima/VM guest (aarch64 host running the
  x86-64 fixture through binfmt/qemu-user);

The supplied manifest is executed against the **original** and the **candidate**
binary with the same cases:

- `poc` cases must reproduce the defect on the original (crash or documented
  failure) and be rejected safely by the candidate;
- `regression` cases are valid inputs and must agree exactly between original
  and candidate (exit code, stdout, stderr).

Fail-closed behaviour (never weakened by this class):

- **No PoC/regression manifest** → no runtime evidence → `runtime.evidence`
  stays `not_run` → the gate cannot succeed → no `verified_patch` and no
  downloadable candidate (raw `static_only_patch` requires the explicit
  `allow_static_only` opt-in on the `/binary` path and is still unverified).
- **Manifest supplied but no runnable guest runner** → PoC status is
  `unavailable` (never fabricated), `runtime.evidence` stays `not_run`, and the
  gate cannot succeed.
- **Wrong fixture hash / malformed manifest / failing case** → the PoC
  differential fails; the candidate is not verified.
- **Unsupported input** (non-ELF, non-x86-64, non-ELF64-LE, no matching site) →
  `unsupported` or `analysis_only`, no capacity candidate.

## 5. Using it

### GUI quick repair

1. Open the console (`/agent/new`; in demo data mode `/agent/new?plan=fixture`).
2. Upload the sample (`marcx` binary).
3. Complete the guided questions and reach the **任务单复核 / 一键修复** card.
4. Optionally choose a JSON file in
   `PoC / 回归用例清单（可选，JSON）` (accepts `.json`, ≤ 64 KiB).  The file is
   appended to the same multipart request as `poc_manifest`; it is **not**
   required.
5. Click `一键修复（自动识别格式）`.  For a successful capacity repair the result
   card shows a `策略 capacity-check` chip and a `运行时 guest/emulated`
   (or `运行时 native`) chip plus the runner name, the full required-check
   table, and the download link for the patched ELF.

Without a manifest the request still runs, but the candidate is held (no
download) because runtime evidence is missing.

### API

`POST /api/binary/repair-review` (multipart, CSRF token required):

```bash
curl -sS -F "binary=@marcx" \
     -F "csrf=$CSRF" \
     -F "poc_manifest=@fixtures/poc/marcx-capacity.json" \
     http://127.0.0.1:8123/api/binary/repair-review
```

Relevant response fields: `decision.success`, `verification.checks[]`
(including `patch.capacity` and `runtime.evidence`), and `patched_base64`
(present only when the gate succeeded).

### CLI

```bash
.venv/bin/python scripts/repair_binary.py marcx marcx-fixed \
    --poc fixtures/poc/marcx-capacity.json --json
```

### Manifest schema (`schema_version: 1`)

Top level: `schema_version`, `fixture_sha256` (must equal the uploaded
original's SHA-256), `format`, `arch`, `target`, plus non-empty `poc` and
`regression` case lists.  Each case has:

- `id` — stable case name;
- `files` — optional list of `{"name": "...", "base64": "..."}`; each file is
  staged into an execution directory and may be referenced from `argv` as
  `{tmp}/name` (v1 manifests without `files` keep working);
- `argv` — argument vector (no shell);
- `original` / `candidate` — expected observations (`crashed`, `exit_code`,
  `stdout`, `stdout_contains`, `stdout_hex`, `stderr`, `stderr_contains`);
- `stdin_base64` — optional standard input.

The checked-in `fixtures/poc/marcx-capacity.json` is the marcx manifest: four
`poc` cases (sparse overflow with/without CRC, span-note variants) and ten
`regression` cases (benign, benign-sparse, benign-CRC, equal-size control,
non-sparse control, source-out-of-bounds control, literal-destination control,
bad CRC, `--help`, `--list` on the PoC archive).  The case archives are embedded
as base64 `files`, so the fixture is a single self-contained JSON file; for a
new binary, build the archives with the challenge generator, compute the
uploaded binary's SHA-256, and embed each archive as a `files` entry.

## 6. Tests

- `tests/test_capacity_repair.py` — fixture identity, exactly one detected
  site, candidate sha256, whitelist byte diff, rewrite disassembly, message
  alignment, idempotence, fail-closed behaviour on other inputs, synthetic
  fixture parity.
- `tests/test_binary_pipeline_capacity.py` — pipeline fallback, `patch.capacity`
  gate check, PoC differential as runtime evidence, no-manifest fail-closed,
  API `poc_manifest` contract.
- `tests/test_binary_ui.py` and `tests/e2e/test_agent_flow.py` — the optional
  manifest picker markup and quick-repair panel wiring.
- Python comments/docstrings added for this feature are ASCII
  (`scripts/check_language_policy.py` scope); user-facing Chinese labels live in
  the UI/JS layer only.

## 7. Limitations

- **x86-64 ELF only.**  ELF64 little-endian x86-64; no PE, Mach-O, arm64, i386,
  big-endian or 32-bit support for this class.
- **Needs the PoC/regression manifest and a runnable guest for `verified_patch`.**
  The differential is the runtime evidence; without it the class cannot produce
  a verified candidate.  A manifest alone is not proof and never bypasses the
  gate.
- **One reviewed inline shape.**  The detector only recognises the inlined
  duplicated unsigned range-check pattern described above; other compiler
  shapes, guard styles or capacity-confusion variants are missed by design
  (`analysis_only` / `unsupported`).  It is a pattern engine, not a general
  capacity-bug detector.  In particular the capacity must be a
  **register-allocated** size variable (a `T != Ra` temp copy); builds where the
  compiler reloads the capacity from a structure field for every check (for
  example the challenge's `-O1` debug build or the guard-page build) are outside
  this engine and fail closed.
- **2 MiB executable-region limit.**  Detection disassembles the complete
  executable region; larger images are rejected explicitly rather than partially
  analysed.
- **No whole-program proof.**  Verification is scoped to: container reparse, the
  re-derived patch bytes (every rewrite is byte-checked), and the PoC/regression
  cases listed in the manifest executed by the selected runtime.  Behaviour on
  inputs outside those cases is not proven, and the profile is not a proof of
  memory safety for the whole program.
- **Runtime tier depends on the host.**  A native Linux runner reports
  `native_run`; qemu-user or a Lima guest reports `emulated_run`.  A host with
  no runner (for example this macOS host without qemu/guest) reports
  `unavailable` and the gate stays fail-closed.
- **Message alignment is cosmetic and conditional.**  It is only applied when
  the sibling wording is unambiguous and the new text is not longer than the
  old one; it is recorded separately and does not affect the verdict.
- **Regression coverage is exactly the manifest's.**  Regression equality is
  checked on the listed valid inputs only; it is not a full behavioural
  equivalence proof.
