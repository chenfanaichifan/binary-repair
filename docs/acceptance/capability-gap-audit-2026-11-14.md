# Capability-gap audit and coverage closure (2026-11-14)

This milestone generalises the lesson from the `marcx` capacity-check failure into
a systematic, reproducible audit of the product, and closes the feasible gaps it
found. The audit is code, not prose: `app/services/coverage_audit.py` (driven by
`scripts/audit_capability_coverage.py`) imports the real repair matrix, pipeline,
analyzers, runtime selectors, gate builders and fixtures, then probes the real
pipeline within a bounded budget. Its output is
`artifacts/capability-gap-audit-2026-11-14/coverage-matrix.json` plus
`gap-report.md`; every status is re-measured on every run.

## 1. Two diseases, not one bug

The original failure was diagnosed as "the engine cannot patch this class".
The audit shows two distinct failure modes that must be fixed together:

1. **Repair-capability gaps** — the engine cannot express the defect class
   (capacity-check divergence, heap-destination copies, dynamic-ELF injection,
   dynamic import resolution, ...).
2. **Acceptance-model mismatches** — the gate's evidence model does not match
   what the repair can prove: stack/Unicorn oracle applied to heap destinations,
   empty regression for no-input/UAF cases, unavailable runner mislabeled as a
   rejected repair, matrix runtime-tier/cell declarations not enforced, a
   legacy gate that cannot consume PoC evidence at all, and a rewrite that the
   gate never re-derived from the produced bytes.

A capability with the wrong acceptance model is as unusable as a missing
capability: `marcx` had both (no engine, and no gate profile to express the PoC
differential).

## 2. Measured result

Latest full audit run (see `artifacts/capability-gap-audit-2026-11-14/gap-report.md`):

| metric | value |
|---|---|
| gaps measured | 66 |
| closed | 51 |
| mitigated (honest limitation, routed) | 1 |
| open (actionable) | 3 |
| non-goal (honest research/platform limits) | 11 |
| high-severity open | 0 |
| matrix cells / sink classes / strategies / profiles / evidence sources / gate checks | 8 / 5 / 18 / 4 / 24 / 34 |

The three remaining open records are documented, not hidden; they are listed in
§5. The audit is deterministic and exits 0; the run also writes SHA-256 sums.

## 3. What was closed and how it is proven

### 3.1 Reviewed capacity-check repair re-integrated (was: engine gap)

The isolated commit `86587da` is back in the product as `app/services/repair/capacity.py`,
selected explicitly via `strategy="capacity"` or as the automatic fail-closed
fallback when the legacy immediate engine finds nothing. Its acceptance model is
the declared `native_poc_rewrite` profile: the gate re-derives every rewrite
action from the original/candidate bytes (`patch.capacity`, `patch.rewrite`) and
takes the supplied PoC/regression differential as the only runtime evidence.

Evidence: `marcx` (`fixtures/elf/vuln-capacity-confusion-x86_64.elf`) repairs to
`93e27f2f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2`; the review
API with the real manifest in the Lima guest returns `verified_patch`, 21/21
required checks passed, `profile=native_poc_rewrite`. Without a manifest the
outcome is inconclusive with no download. The synthetic sibling-check fixture
repairs to `5b6501b0...`.

### 3.2 Heap-destination capacity repair (was: engine gap + oracle mismatch)

`Sink.destination_kind` (`stack|heap|global`, default `stack`) and same-function
recovery of immediate `malloc`/`calloc` capacities let the writer wrap a heap
`strcpy` guard through the existing code-cave machinery. Non-stack destinations
are never judged by the stack/Unicorn oracle; they are routed to the
`native_poc` profile and need a real external differential.

Two blockers found by the audit were fixed on the way:

- `code_cave.add_rx_segment` grew the program-header table over `PT_INTERP` on
  dynamic ELF, producing unrunnable candidates. It now repurposes one
  non-essential `PT_NOTE` phdr in place when no safe slot exists, preserving
  `e_phnum`, `PT_INTERP` and all existing phdrs, and verifies the result.
- The Lima guest could serve a stale virtiofs view of a just-rewritten staged
  candidate (same path), making qemu die with an internal SIGBUS on the new
  segment. `guest_runner` now waits (bounded, fail-closed) until the guest sees
  the host file size before executing.

Evidence: heap fixture `0f65a2d2...` repairs to
`ea22260535efca37dca19404c700ce29e6da1f45b3af24d3903c8d27fdf6fb73`; real Lima
differential `status=pass`, 19/19 gate checks, `profile=native_poc`; the original
crashes with `malloc(): corrupted top size`, the candidate truncates at
capacity-1 and keeps benign regressions byte-identical.

### 3.3 Acceptance-model harmonisation (was: gate mismatches)

- Declared evidence profiles (`strict_template`, `emulated_instruction`,
  `native_poc`, `native_poc_rewrite`) live in `app/services/repair_matrix.py`.
  `unified_verification.build` enforces `profile.declared`, `profile.evidence`
  (supplied evidence sources must match the profile) and
  `profile.required_checks`; a new engine cannot silently reuse the wrong oracle.
- `patch.rewrite`/`patch.capacity` re-derive in-place rewrites from bytes; a
  tampered action fails. `container.cell` checks the exact matrix cell
  (container/arch/bits/endian) and `runtime.cell_tier` rejects a tier the cell
  does not declare.
- External PoC evidence can serve as runtime evidence (`runtime.evidence`,
  `runtime.tier`, `runtime.contract`) only for profiles that declare it.
  An unavailable runner leaves every `poc.native.*` check `not_run`, so the
  outcome is inconclusive rather than "rejected".
- No-input/UAF: a manifest-level `no_input: true` makes an empty regression list
  an explicit `not_applicable_no_input` pass; an undeclared empty list still
  fails. `fixtures/poc/cwe416.json` now declares its no-input model.
- Quick repair no longer silently ignores/rejects evidence: manifest-bearing
  requests are routed through the unified pipeline for every container, and
  manifest-less ELF x86-64 surfaces reviewed deterministic candidates as
  inconclusive (what evidence is missing) instead of hiding them behind the
  legacy "unsupported" verdict. The legacy gate keeps its exact check ids and
  now also declares/enforces its evidence profile.
- The GUI quick-repair panel and `/api/binary/repair-review` accept the optional
  `poc_manifest` again; the candidate is only offered when the deterministic
  gate succeeds.

### 3.4 Engine capability gaps found by the audit

- x86-64 `.plt.sec`/CET stubs are now decoded (all in-stub `FF 25` positions),
  so dynamic ELF built with default toolchains resolve `strcpy`/`malloc`/...
  imports; previously the analyzer saw zero sinks for such binaries.
- The dynamic-ELF injection and guest-visibility fixes above are general
  capability fixes, not capacity-specific workarounds.
- Matrix truth was tightened: dead sink-class declarations removed, per-cell
  sink classes match what each analyzer can emit, the runtime-tier vocabulary
  includes `unavailable`, and requested strategies that do not match the
  produced action are rejected instead of being silently accepted.

## 4. Self-reflection: what this audit says about the earlier work

- **Isolating a working capability is not the same as shipping it.** The
  capacity engine was "done" in an isolated branch while the product still
  failed the same class; the gap only closed when engine, matrix, profile and
  UI/API landed together.
- **Implicit evidence models are the root cause of gate/engine drift.** Writing
  checks as ad-hoc clauses made it possible to verify a heap candidate with a
  stack oracle, or to reject an unavailable runner as a failed repair. Profiles
  make the model declare itself and fail when the evidence does not match.
- **The docs/claims were ahead of or behind the code.** `claims.json` said heap
  repair was unimplemented after heap recovery existed, and the no-input model
  was documented while the gate rejected it. Claims are now regenerated from
  measured state; the audit treats prose/claim drift as a first-class gap.
- **Bounded fixtures hid a general engine defect.** The `PT_INTERP` clobbering
  and stale-virtiofs issues only appeared once a real dynamic-ELF guard
  candidate was executed; "tests pass" on synthetic/static fixtures was not
  acceptance. The new fixtures exercise dynamic ELF, appended segments and real
  guest PoC/regression.
- **Concurrency hazard (operational):** an external operator reset the shared
  worktree mid-milestone. Work was recovered from git objects/safety stash and
  is now committed/pushed on `coverage-audit-2026-11-14`; uncommitted work must
  not be the only copy in a shared checkout.

## 5. Residual open gaps and honest non-goals

Open (measured; see gap-report for exact evidence strings):

1. `EG-target-scope` / `OG-wrong-function-candidate` — no caller-declared target
   selector: the deterministic engine patches the first patchable sink and the
   gate proves behaviour, not target identity. The hard-case benchmark is
   AI/non-goal evidence; do not claim deterministic target repair from it.
   Mitigation in this milestone: the audit reports the out-of-target patch sites
   explicitly, matrix payload marks unexercised capabilities, and no benchmark
   claim is derived from whole-image patches.
2. `RG-external-poc::macho/x86_64` — native Mach-O scheduler and external-PoC
   runner disagree on an arm64 host for x86_64 slices; external PoC is declared
   unavailable rather than faked.
3. The `GM-legacy-gate-poc-manifest` record is now `mitigated`: the legacy
   stack/emulated gate still cannot consume a PoC manifest, but the pipeline
   states that explicitly and routes manifest-bearing repairs to the unified
   evidence-profile path.

Closed since the first audit run include: no-input/UAF evidence model,
unavailable-runner semantics (inconclusive, never "rejected"), declared
profiles/profile checks, cell/tier validation, rewrite re-derivation, matrix
per-cell sink truth, dead-class removal, requested-vs-produced strategy honesty,
claims/limitations drift, and `checked_copy` (kept declared, explicitly marked
as no-shipped-fixture coverage instead of silently claimed).

Honest non-goals (unchanged or newly documented): sprintf/format-expansion,
UAF/lifetime, integer/loop deterministic templates, arm32/riscv/mips/ppc/
big-endian, fat/32-bit Mach-O rewrite, full global/struct-member capacity
inference (allocation-size over-estimation is caught by the runtime oracle, not
solved statically), one-function-per-candidate policy, whole-program proof,
non-loop AI verified success (0/6), and multi-provider model statistics.

## 6. Reproduction

```bash
# deterministic engine/gate checks
.venv/bin/python -m pytest -q tests/test_capacity_repair.py tests/test_binary_pipeline_capacity.py \
  tests/test_repair_heap.py tests/test_code_cave.py tests/test_gate_profiles.py tests/test_repair_matrix.py
# real guest acceptance (Lima VM `binaryrepair`)
.venv/bin/python scripts/repair_binary.py fixtures/elf/vuln-capacity-confusion-x86_64.elf /tmp/marcx.fixed \
  --poc fixtures/poc/marcx-capacity.json --json
.venv/bin/python scripts/repair_binary.py fixtures/hard-cases/vuln-heap-malloc-x86_64.elf /tmp/heap.fixed \
  --poc fixtures/poc/heap-malloc.json --json
# self-discovery audit (bounded, no network)
.venv/bin/python scripts/audit_capability_coverage.py --out artifacts/capability-gap-audit-2026-11-14
```

Contracts preserved: the deterministic gate remains the only acceptance
authority; AI review can only tighten; missing evidence stays `not_run`; no
candidate download unless `decision.success` is true.
