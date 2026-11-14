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
| gaps measured (frozen release tree) | 68 |
| closed | 55 |
| mitigated (honest platform declaration) | 1 |
| open (actionable) | 0 |
| non-goal (honest research/platform limits) | 12 |
| high-severity open | 0 |
| dynamic_unverified (full/local run) | 0 |
| dynamic_unverified (static/PR mode) | 6 |
| capability universe cells (unknown) | 240 (0) |
| matrix cells / sink classes / strategies / profiles / evidence sources / gate checks | 8 / 5 / 18 / 4 / 24 / 34 |

Phase-2 closure (same day): the three open records and the one mitigated record
were closed with measured evidence. Phase-3 (same day) added the
safe-by-default whole-image policy, `dynamic_unverified` static-mode semantics,
an explicit capability universe (unknown=0), a meta-audit of the audit itself
(injected-defect recall/precision 1.0), an acceptance-invariant engine, real
12-case provider-matrix evidence with target-strict measurement, productized
non-goals (owner/review date/productization criteria/fallback), and staged
PR/nightly/release gates. `scripts/verify_coverage_gate.py --static-only` and
`--local` are the regression authorities; CI runs the static mode and the
release gate requires `--local` plus invariants/meta-audit/real acceptance.

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

### 3.4 Safe-by-default policy and platform capability contract (phase 3)

- **Safe default**: `repair_any` without an explicit target and without
  `allow_whole_image=True` returns `analysis_only` — no candidate, no download,
  no success-readable packet, explicit reason, `target_policy="analysis_only"`.
  Whole-image repair is an explicit opt-in (`allow_whole_image=True` /
  `--allow-whole-image` / GUI checkbox default OFF) and its packets record
  `target_policy="whole_image"`; target-scoped repair keeps the required
  `patch.target_scope` ownership check. A PoC manifest cannot silently opt in.
- **Capability contract**: `runtime/capabilities.contract()` is the single source
  of truth for declared vs measured tier, emulated availability, external-PoC
  availability and reason. `matrix_payload` exposes `contract_capabilities`;
  `poc_runner` and the native Mach-O scheduler read the same contract.
  Declared-but-unavailable capabilities (Mach-O x86_64 external PoC on arm64,
  PE external PoC, 32-bit Mach-O) are reported `unavailable`/`not_run` with
  reasons — never fabricated and never `rejected`/verified.
- **Dynamic vs static audit**: `--static-only` reports probe-dependent records as
  `dynamic_unverified` (6 rows) instead of closed/mitigated; `--local` requires
  `dynamic_unverified == 0`. A static green light cannot be used for release
  claims.
- **Audit about the audit**: `scripts/meta_audit.py` injects known defects
  (dead sink class, removed gate check, unexercised strategy, manifest-route
  signature-token false positive, fabricated open gap/unmapped non-goal) and
  measures detector recall/precision (1.0/1.0, 9 scenarios). The acceptance
  invariant engine (`app/services/acceptance_invariants.py`) fail-closes
  inconsistent packets (verified/rejected/not_run/target/rewrite/manifest-legacy/
  download/policy rules).
- **Real provider matrix**: 12 hard cases, deepseek endpoint, 1 repeat,
  253.7 s / 13 of 40 calls, served model `deepseek-flash` while
  `deepseek-chat` was requested (identity mismatch recorded, not hidden),
  cost/seed unavailable honestly. Deterministic target-strict expectation
  matches 12/12 with 0 verified (these are AI/non-goal classes); AI target mode
  verified 6/12 (in-scope 9/12); reference `.S` fixes 6/6 verified, `.c`
  references source-only 6. Evidence:
  `artifacts/provider-matrix-2026-11-14/`.

## 3.5 Release freeze and P0/P1/P2 closure (phase 4)

- **Frozen release tree**: branch `release/2026-11-14` at mainline SHA `725e7bb`
  (fast-forwarded to `workbench-v3` after final gates). The exact artifact,
  acceptance and gate evidence for this SHA lives under
  `artifacts/capability-gap-audit-2026-11-14/`,
  `artifacts/coverage-closure-2026-11-14/`,
  `artifacts/provider-coverage-2026-11-14/` and
  `artifacts/provider-matrix-2026-11-14/`.
- **Artifact sync (P0-2)**: the committed audit artifacts were regenerated on the
  frozen tree and match the live audit (68 gaps / 55 closed / 1 mitigated /
  0 open / 12 non-goal; universe 240 cells, unknown 0; static view 62 gaps with
  `dynamic_unverified=6`). The coverage gate now fails on stale artifacts,
  claims/measurement drift and unmapped non-goal ids.
- **Release gate (P0-1)**: `scripts/release_gate.py --release --release-sha
  <sha>` requires a clean frozen tree and re-runs static gate, claims/measurement
  diff, acceptance contract (capacity 21/21, heap 19/19, target-scoped 20/20,
  safe-default controls), local gate (`dynamic_unverified=0`, universe
  `unknown=0`, meta-audit, invariants), provider-matrix schema and the full
  pytest suite; nightly mode adds a fresh real-Lima capture into a temp
  directory. Release claims require this gate, never a static-only green.
- **Provider dimension (P1-1)**: `artifacts/provider-coverage-2026-11-14/`
  records 11 sha256-bound evidence rows. Completed 12-case matrices: 4 models
  across 2 providers (DeepSeek official 2 models, exact identity, 6/12 verified,
  3 runs each; SiliconFlow CN 2 free Qwen models, exact identity, 0/12 verified
  — a capability result, not a pass). SiliconFlow international is blocked
  (HTTP 402 insufficient balance); GLM-Z1 probe timed out; DashScope has no
  key/artifact. The Lead's `provider-matrix` run requested `deepseek-chat` but
  was served `deepseek-flash` (identity_ok=false); its 6/12 verified repairs are
  attributed to the served model and excluded from requested-model coverage.
  The 5-6 model international matrix is explicitly **not satisfied**.
- **Non-goal productization (P2-1)**: `docs/acceptance/non-goals-2026-11-14.md`
  and `claims.json["non_goals"]` carry the 12 ids with affected cells,
  detected-input behaviour, owner, review-by date, productization criteria,
  fallback, `roadmap_stage`, `owning_area`, `research_acceptance` and
  `quarterly_review` (next 2027-02-14); the 11th detail (direct copy sink
  cross-function/offset alias capacity inference) is explicit, and the
  graduation path requires fixture + runtime oracle + evidence profile + gate
  check + claims/measurement update.
- **Capability contract (P2-2)**: `runtime/capabilities.contract()` is the single
  source of truth; declared-vs-measured gaps carry explicit reasons and
  unavailable platforms stay `unavailable`/`not_run` (PE and 32-bit Mach-O
  external PoC; Mach-O x86_64 Rosetta is function-level only).
- **Audit of the audit (P3-3)**: `scripts/meta_audit.py` now injects 12+
  scenarios (missing target check, unverified rewrite, provider identity
  mismatch, stale artifacts, inconclusive download, fabricated contract
  capability, plus earlier ones) and keeps recall/precision 1.0; the invariant
  engine fail-closes every relevant inconsistency.
- **CI/nightly/browser (P1-2)**: CI runs the static coverage gate and PR release
  gate; the self-hosted Lima nightly job remains inert by default
  (`vars.BINARYREPAIR_RELEASE_GATE`) and is documented as not-run; browser e2e
  skips with an explicit reason when Chromium is absent. A local `--nightly`
  attempt and its outcome are recorded in the release report.
- **Environment/flake (P3-1/P3-2)**: Lima tests run serially; flake quarantine
  policy and rerun rules are documented in the release-gate operations doc;
  static mode keeps `dynamic_unverified` visible and release/local requires 0.

## 3.6 Engine capability gaps found by the audit

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

## 5. Residual gaps after phase-2 closure: zero open, honest non-goals only

Frozen-release audit status: **0 open, 1 mitigated (host-dependent
`native_run` tier declaration for the ELF x86_64 cell: measured `emulated_run`
on this host, explained by the capability contract; it is a transparent platform
declaration, not a hidden closure), 11 productized non-goals, 240-cell universe
with unknown=0**. Provider/nightly/browser dimensions and their honest
limitations are recorded in §3.5 and §5.

Phase-2 closed the former actionable residuals with measured proof (see
`gap-report.md` and `artifacts/coverage-closure-2026-11-14/`):

1. `EG-target-scope` / `OG-wrong-function-candidate` — **closed**. The pipeline
   accepts an explicit `target` (symbol/substring/explicit VA range) and
   `require_target`; `containers.resolve_function_scope` resolves it fail-closed;
   sink/capacity output is filtered to the scope and the unified gate now emits
   and enforces a required `patch.target_scope` check (non-empty actions, every
   numeric `site_va` inside `[va,end)`, scope hashed into `report_sha256`).
   Target-mode probes: heap fixture `target="heap_bad"` verified with
   `patch.target_scope=passed` (20/20 checks, candidate `ea222605...`); wrong or
   missing target fails closed with no whole-image candidate. The default
   manifest/-target-less product policy remains whole-image and does **not**
   claim target identity (documented in `target_policy`, claims and
   LIMITATIONS); target-strict mode is available via `--target/--require-target`
   and the benchmark now records `baseline_target_strict`.
2. `RG-external-poc::macho/x86_64` — **closed as a measured platform
   limitation**. `app/services/runtime/capabilities.py` probes host/arch and
   reports `poc_available=False` with an explicit reason on this arm64 host
   (`emulated_run`, Rosetta/function-level only); `poc_runner._select_runner`
   consults the same probe, so the native and external-PoC paths agree and
   `run_poc` stays `unavailable` (never a fabricated pass/fail).
   `matrix_payload` exposes the measured `runtime_capabilities` next to the
   declared tiers.
3. `GM-legacy-gate-poc-manifest` — **closed**. Manifest-bearing ELF x86-64
   requests never reach the legacy stack/emulated engine (pipeline guard before
   `repair_elf`, verified by a body-start source census: guard position <
   legacy engine position); the legacy builder additionally fails closed when
   given external PoC evidence (`manifest.legacy_gate_unsupported=failed`), and
   review/API manifest requests use the unified evidence-profile gate only.
   The audit detector was corrected to require a real guard (the earlier
   signature-token false positive is regression-tested).

The eleven honest **non-goals** are unchanged and explicitly mapped in
`docs/acceptance/non-goals-2026-11-14.md` and `claims.json["non_goals"]`, with
enforcement (unsupported / analysis_only / not_run / no download / no verified):
direct-copy sink capacity not recoverable by same-function analysis, global and
struct-member capacity inference (runtime oracle catches over-estimation),
sprintf/format-expansion, UAF/lifetime, integer/loop deterministic templates,
PE/32-bit Mach-O external PoC, full whole-program proof, non-loop AI verified
success (0/6), multi-provider statistics, single-function candidate policy, and
the AI leaf-only path (target-mode selective whitelist as declared).

Release-governance guards: `scripts/release_gate.py` PR/nightly/release stages
with frozen-SHA + clean-tree enforcement, artifact/claims sync checks,
meta-audit and invariant engine; `scripts/verify_coverage_gate.py` (static CI mode with
`dynamic_unverified` visibility + `--local` acceptance mode with
`dynamic_unverified=0`, universe `unknown=0`, meta-audit and invariant checks),
`scripts/release_gate.py` (PR/nightly/release stages: static gate, claims/
measurement diff, acceptance role/sha contract, provider-matrix schema,
invariant engine, meta-audit, full pytest), CI `coverage-gate` +
`release-gate-pr` jobs (nightly self-hosted-lima job documented and inert by
default), target-mode probes, capability-probe/runner negatives, legacy
manifest routing regression tests, and the real Lima acceptance bundle
(`artifacts/coverage-closure-2026-11-14/`).

Non-goals are productized in `docs/acceptance/non-goals-2026-11-14.md` and
`claims.json["non_goals"]`: all 11 carry affected cells, detected-input
behaviour, owner, review-by date, productization criteria and fallback; the
coverage gate fails if any mapping/field is missing.

Honest non-goals (unchanged or newly documented): sprintf/format-expansion,
UAF/lifetime, integer/loop deterministic templates, arm32/riscv/mips/ppc/
big-endian, fat/32-bit Mach-O rewrite, full global/struct-member capacity
inference (allocation-size over-estimation is caught by the runtime oracle, not
solved statically), one-function-per-candidate policy, whole-program proof,
non-loop AI verified success (0/6), and multi-provider model statistics.

## 6. Reproduction

```bash
# phase-2 ownership / convergence / capability checks
.venv/bin/python -m pytest -q tests/test_target_scope.py tests/test_legacy_manifest_gate.py \
  tests/test_runtime_capabilities.py tests/test_coverage_gate.py
.venv/bin/python scripts/verify_coverage_gate.py --static-only
.venv/bin/python scripts/verify_coverage_gate.py --local
# deterministic engine/gate checks
.venv/bin/python -m pytest -q tests/test_capacity_repair.py tests/test_binary_pipeline_capacity.py \
  tests/test_repair_heap.py tests/test_code_cave.py tests/test_gate_profiles.py tests/test_repair_matrix.py
# real guest acceptance (Lima VM `binaryrepair`)
.venv/bin/python scripts/repair_binary.py fixtures/elf/vuln-capacity-confusion-x86_64.elf /tmp/marcx.fixed \
  --poc fixtures/poc/marcx-capacity.json --json
.venv/bin/python scripts/repair_binary.py fixtures/hard-cases/vuln-heap-malloc-x86_64.elf /tmp/heap.fixed \
  --poc fixtures/poc/heap-malloc.json --json
# target-scoped ownership proof (strict target mode)
.venv/bin/python scripts/repair_binary.py fixtures/hard-cases/vuln-heap-malloc-x86_64.elf /tmp/heap.fixed \
  --target heap_bad --require-target --poc fixtures/poc/heap-malloc.json --json
# self-discovery audit (bounded, no network)
.venv/bin/python scripts/audit_capability_coverage.py --out artifacts/capability-gap-audit-2026-11-14
```

Contracts preserved: the deterministic gate remains the only acceptance
authority; AI review can only tighten; missing evidence stays `not_run`; no
candidate download unless `decision.success` is true.
