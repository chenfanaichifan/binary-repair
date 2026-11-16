# Phase-8D D04: heap-malloc ABI rejection root cause

Status: **analyzed; candidate remains rejected**. No verifier rule was changed.
No capability promotion or verified claim is made.

Worktree base: `f1bb1f41eba1e0be61be09cea56091e8a03a9896`.

## Question

Phase-8C's public benchmark had one deterministic claim withdrawn after the
independent verifier rejected `heap-malloc` with:

```text
ABI report not ok: plan.abi_blocks@4198704: fatal=3
findings=['branch_target_unknown', 'call_target_not_allowed', 'no_ret']
```

Was the candidate invalid, was the generator patch plan wrong, was the
verifier's ABI rule insufficient, or was the evidence unprovable?

## Reproduction

From the Phase-8D worktree (base `f1bb1f41eba1e0be61be09cea56091e8a03a9896`):

```bash
.venv/bin/python scripts/analyze_phase8d_heap_malloc_abi.py --write
.venv/bin/python scripts/analyze_phase8d_heap_malloc_abi.py --check
```

The deterministic repair in `app/services/binary_pipeline.py` (`repair_any`,
target `heap_bad`, PoC `fixtures/poc/heap-malloc.json`, `require_target=True`)
reconstructs:

- original: `0f65a2d2ffe1ebf91f717d5edc78928cb8ee219e3f73e623b256f87bdcc4381f`
- candidate: `ea22260535efca37dca19404c700ce29e6da1f45b3af24d3903c8d27fdf6fb73`
- candidate hash equals the committed Phase-8C candidate.

The candidate is not hidden evidence; it is the public benchmark candidate
reconstructed from the committed fixture and deterministic engine.

## What the candidate actually contains

- The original target function `heap_bad` is at `0x401130`, size 59 bytes.
- The repair redirects `strcpy` at `0x40114d` to injected cave `0x405000`,
  size 38 bytes, via a new executable `PT_LOAD` (file offset `0x4000`).
- The plan's `abi_blocks[0]` is:
  - function `reviewed-function`, VA `0x401130`, size 59,
    evidence sha `c15420fcf575024f6404b97d43bdf1522fa6cdd3a9376e666ba22431db008c9c`.
- The cave ABI check (38 bytes) is `ok=True`, fatal=0; findings=[].
- The declared function-block ABI check is `ok=False`, fatal=3:
  - `call_target_not_allowed` at offset `0xe`
  - `call_target_not_allowed` at offset `0x26`
  - `no_ret` at block end
  - plus `branch_target_unknown` warning at offset `0x35`

## Resolved control flow from raw bytes and relocations

The function block is a normal compiled `heap_bad` with three legal
memory-indirect control transfers:

| VA | instruction | GOT slot | imported symbol |
|---|---|---|---|
| `0x40113e` | `call qword ptr [rip + 0x2e9c]` | `0x403fe0` | `malloc` |
| `0x40114d` | `call 0x405000` | direct | injected cave |
| `0x401156` | `call qword ptr [rip + 0x2e74]` | `0x403fd0` | `puts` |
| `0x401165` | `jmp qword ptr [rip + 0x2e4d]` | `0x403fb8` | `free` (tail call) |

GOT slots were resolved from `.rela.dyn` to `malloc`, `puts`, `free`.
The original source (`fixtures/hard-cases/heap_capacity.c`) is:

```c
void heap_bad(char *src)
{
    char *dst = (char *)malloc(16);
    strcpy(dst, src);
    puts(dst);
    free(dst);
}
```

The compiled `free(dst)` is a licensed tail call, so the function block
legitimately ends in `jmp [free@GOT]` and has no `ret`. The `malloc` and `puts`
calls are normal PLT/GOT calls. None of these is a candidate defect.

## Root-cause classification

Primary:

- **`generator_plan_incorrect`** (high confidence): the plan declares the
  pre-existing function range as `abi_blocks[0]` rather than the injected cave
  `0x405000`/38 bytes. The cave is carried separately as `plan.cave`. The ABI
  evidence therefore validates the wrong region, and the verifier rejects on
  unrelated original-function control flow.
- **`abi_proof_insufficient`** (high confidence): the ABI evidence hash binds
  the function block (`c15420...`), not the injected cave (`d6851587...`).
  Even a passing function-block check would not prove the injected guard's
  stack/return discipline.

Contributing, not primary:

- **`verifier_rule_incorrect`** (medium confidence): the x86-64 ABI checker
  does not resolve RIP-relative memory-indirect calls/jumps to imported symbols
  and does not model tail calls. On a declared whole-function block it
  classifies legal `call [malloc@GOT]`, `call [puts@GOT]` and
  `jmp [free@GOT]` as fatal/unknown. This is conservative for an intended
  injected-only block; it is an insufficient expression for function-context
  ABI evidence. It is not the primary reason the plan should not have declared
  that block.
- **`analysis_evidence_insufficient`** (high confidence): the Phase-8C rejection
  message exposed only finding codes, without resolved GOT slots/symbols or
  tail-call context, so the original rejection text alone could not distinguish
  a bad candidate from a mis-scoped ABI block. This artifact supplies the
  missing resolution.

Excluded:

- **`generator_patch_invalid`**: no evidence the candidate is invalid. The
  independent runtime oracle passed (`limactl`, `emulated_run`, 4 cases), plan
  replay passed, target scope passed, and the injected cave ABI is valid.
- **`root_cause_inconclusive`**: the rejection is explainable and reproducible
  at the plan/ABI-evidence layer; the candidate remains rejected fail-closed.

## Verifier decision

The independent verifier still returns `decision="rejected"` with:
- layout-plan: passed
- action-replay: passed
- target-scope: passed
- runtime-oracle: passed
- abi: failed
- decision: rejected (fail-closed)

No verifier rule or allowlist was modified by this analysis. The rejection is
preserved; D04 does not turn it into a pass.

## Evidence artifact

`artifacts/phase8d-heap-malloc-abi-2026-11-17/` contains:

- `original.sha256`
- `candidate.bin`, `candidate.sha256`
- `plan.json` (generator's plan)
- `verifier-report.json` (independent report)
- `abi-analysis.json` (disassembly, control-flow resolution, ABI reports,
  classifications and evidence hashes)
- `README.md`, `SHA256SUMS`

`python scripts/analyze_phase8d_heap_malloc_abi.py --check` validates artifact
contents and SHA256SUMS offline.

## Follow-up implications for Phase-8D

1. The generator plan builder should derive `abi_blocks` from the **injected
   cave** (and, if needed, a separate function-context block with resolved
   targets), not from the pre-existing function range.
2. The independent verifier's ABI report should expose resolved GOT/PLT slots
   and tail-call context when it rejects, so another agent can distinguish
   candidate defect from block-scope defect.
3. No rule should be relaxed simply to make `heap-malloc` verified. A fix must
   preserve the separate cave/function proof and the fail-closed decision.

## Limitations

- ABI checking is static and conservative; GOT/PLT names are relocation-derived,
  not runtime-load-resolved.
- The independent PoC is function-level behavioural evidence, not a full
  semantic-equivalence proof.
- The injected cave ABI pass covers stack/return/callee-saved discipline only.
- The candidate remains rejected; D04 is a root-cause analysis, not a repair
  claim.
