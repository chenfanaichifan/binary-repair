# Acceptance: two AI binary repair paths (2026-11-13)

Branch: `feature/ai-binary-repair` (post-v5).  Product requirement: two AI
paths, one via an **assembly round-trip**, one **directly on binary bytes**,
both producing a patched binary and both bounded by the deterministic gate.

## 1. The two paths

| Path | Input → intermediate | AI output | Binary write | Gate |
|---|---|---|---|---|
| `asm_roundtrip` | binary → **assembly text** | replacement function assembly | clang assembles to a block; inject + function-entry redirect | same deterministic gate |
| `binary_direct` | binary → no assembly text | raw machine-code bytes or same-length byte edits | existing writer inject/redirect or in-place patch | same deterministic gate |

Path 1 supports ELF i386/x86_64/arm64.  Path 2 covers ELF/PE/Mach-O
x86_64/arm64 and ELF32/PE32 i386.  Neither path decompiles to C and recompiles;
path 1 does use assembly by design, path 2 does not.

## 2. Scripted acceptance evidence

Command: `python scripts/capture_ai_binary_repair.py --out artifacts/ai-direct-binary-2026-11-13`

The model in this bundle is a deterministic **scripted stand-in**; no network or
provider is used.  It proves protocol/assembler/validator/direct-writeback/gate
integration, not real-LLM repair quality.

| fixture | format/arch | path | result |
|---|---|---|---|
| `fixtures/pe/vuln-strcpy-x64.exe` | PE x86-64 guard | `binary_direct` | `verified_patch` |
| `fixtures/pe/vuln-strcpy-arm64.exe` | PE arm64 guard | `binary_direct` | `verified_patch` |
| `fixtures/elf/vuln-strcpy-x86.elf` | ELF i386 guard | `asm_roundtrip` + `binary_direct` | both `verified_patch` |
| `fixtures/elf/vuln-strcpy-x86_64.elf` | ELF x86-64 guard | `asm_roundtrip` + `binary_direct` | both `verified_patch` |
| `fixtures/elf/vuln-strcpy-arm64.elf` | ELF arm64 guard | `asm_roundtrip` + `binary_direct` | both `verified_patch` |
| `fixtures/elf/vuln-memcpy-x86.elf` | ELF i386 memcpy immediate | `binary_direct` | `verified_patch` |
| `fixtures/macho/vuln-strcpy-x86_64` | Mach-O x86-64 guard | `binary_direct` | `verified_patch` via **native** gate (macOS) |
| `fixtures/macho/vuln-strcpy-arm64` | Mach-O arm64 guard | `binary_direct` | `verified_patch` via **native** gate (macOS) |

Negative control: structurally valid but semantically empty injected guard
(`c3` = `ret`) → deterministic gate rejects it (`verified=false`,
`disposition=rejected`).  Scripted evidence contains 11 positive records on
macOS (9 on Linux, where Mach-O native cases are skipped by platform).

**No AI increment is measured.**  Direct-path scripted candidates coincide with
the v5 deterministic baseline; assembly-path candidates differ in representation
but do not prove extra vulnerability coverage.  Real-provider quality and a
gate-blind/PoC increment experiment remain future work.

## 3. Tests

| Environment | Result |
|---|---|
| macOS 13.5 arm64 / Python 3.11.8 | **1133 tests, 0 failed, 0 errors, 4 skipped** (335.4 s) |
| Linux VM Ubuntu 24.04 arm64 / Python 3.12.3 | **1133 tests, 0 failed, 0 errors, 7 skipped** (345.0 s) |

Targeted coverage includes:

- assembly path: i386/x86_64/arm64 scripted assembly → `verified_patch`;
  forbidden instructions (call/syscall), bad assembly, missing provider and
  non-ELF input fail closed; API returns 200/422/503 accordingly;
- direct path: guard injection and in-place edit verified; invalid code,
  before mismatch, unrelated edit, no-op guard fail closed;
- API/CLI/UI: two-path contract, provider absent 503, invalid 422, verified 200,
  CLI by-path success/failure, two UI cards and download gating;
- fixtures/provenance: `scripts/build_binary_fixtures.py --check`; content
  SHA-256 verifier `scripts/verify_evidence.py`.

## 4. CI

- Workflow: `Ubuntu verification` (`ubuntu-24.04`, Python 3.11, clang installed
  for the assembly path).
- Run: [43435227438](https://github.com/chenfanaichifan/binary-repair/actions/runs/43435227438)
  on `60362a9` (`workbench-v3`) — **success** (PoC differential gate,
  blind-spot/provider experiment tests).
- Previous two-path run: [43426508766](https://github.com/chenfanaichifan/binary-repair/actions/runs/43426508766)
  on `61287fd` — success.
- `feature/ai-binary-repair` and `workbench-v3` are both pushed at this commit;
  `main` and `handoff-v4-local` are untouched.
- This acceptance record is a docs-only follow-up; the workflow re-runs the same
  suite for it.

## 5. PoC differential gate and gate blind spots

When the original function's runtime is available, the deterministic gate now
includes a required **PoC-style differential**: the same capacity/input probe
must fail on the original bytes and pass on the candidate.  This is a
function-level runtime differential, not a guest/kernel PoC replay.  Reports
include `verification.packet.poc` and checks `poc.original_fails` /
`poc.candidate_passes`.

`scripts/gate_blind_spot_experiment.py` (scripted, no network) constructs
structurally valid but semantically deviant candidates:

| case | result |
|---|---|
| assembly no-op `ret` | caught |
| assembly wrong destination | caught |
| assembly missing NUL terminator | caught after explicit destination-fill hardening |
| direct extra unrelated executable edit | caught after restricting direct edits to the selected length immediate |
| assembly correct copy but no original `puts` side effect | **residual blind spot** (I/O side effects outside the runtime contract) |

Summary: 4/5 caught, one residual blind spot recorded honestly in
`artifacts/gate-blind-spots-2026-11-13/`.

## 6. Real-provider experiment

`scripts/run_ai_provider_experiment.py` was run once with the operator's
configured provider (no key/raw prompt/response stored):

| metric | result |
|---|---|
| tasks | 3 assembly + 3 direct |
| AI verified | 3/6 |
| deterministic baseline verified | 6/6 |
| coverage increment | 0 |

Failures were honest and typed: assembly x86-64 candidate failed the runtime
gate; direct PE x86-64 emitted forbidden `call`; direct PE arm64 emitted a
fall-through block (validator rejected).  All benchmark fixtures are also
repairable deterministically, so this set cannot show coverage increment; a
gate-blind/PoC benchmark on deterministic failures is still required.

## 7. Boundaries

- Assembly path: ELF i386/x86_64/arm64 only; requires host `clang`; no
  PE/Mach-O assembly path.
- Direct path: existing matrix only; Mach-O native evidence is macOS-only and
  skipped on Linux.
- One sink/target function per AI candidate.
- AI output is untrusted: structural validation only; semantics are decided by
  the deterministic runtime gate, not the model.
- No real-LLM quality/increment claim; PoC-failure is not yet a gate predicate.
