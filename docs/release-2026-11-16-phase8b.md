# Release 2026-11-16 Phase-8B: independent verification semantic closure

Status: Phase-8B release evidence for the verifier-semantics cycle.

- Gated code SHA: `c5d87b570e4a2d87816d482e22871a7a49a35f7a`
- Real GitHub-hosted CI: run 43703724955, conclusion success
  (https://github.com/chenfanaichifan/binary-repair/actions/runs/43703724955)
- Ubuntu verification: run 43703724942, conclusion success
  (https://github.com/chenfanaichifan/binary-repair/actions/runs/43703724942)
- Local frozen-tree nightly gate: recorded on the evidence branch for the
  final release commit (`artifacts/release-gate-2026-11-16-phase8b/`, branch
  `release/2026-11-16-phase8b-evidence`, tag
  `release-2026-11-16-phase8b-evidence`); the gate bundle carries the exact
  gated SHA, tree SHA, 13 required-check results and the unmodified timestamped
  evidence.
- The hosted CI evidence above is bound to the code SHA named there; the final
  release commit is separately frozen and gated on the release host. The
  self-hosted Lima nightly is `not_run` and is not claimed.

This note does not claim a new vulnerability-repair capability, capability
graduation, hidden-benchmark generalization, whole-program proof, or completion
of Phase-8C..16.

## What changed

- B1/B2 baseline: `artifacts/phase8b-baseline-2026-11-16/` reproduces the two
  Phase-8A verification disagreements with deterministic `repair_any` and the
  pre-fix verifier. It records candidate bytes, outcome/action/scope facts,
  verifier reports, experiments and gap registry V8B-01..V8B-07. No observed
  candidate defect; the baseline candidates are evidence-only and not verified.
- B3 contracts: new `contracts/patch-plan.schema.json`; compatible extensions to
  `verification.schema.json` (layout/oracle evidence) and
  `benchmark-sample.schema.json` (hash-bound authority). Acceptance adds
  AM25-AM28 (62 cases / 28 classes); meta-audit is 30 scenarios.
- B4 verifier: exact replay of write/insert/replace operations, plan-aware target
  scope and associated changes, executable cave/relocation checks, derived ABI
  evidence, independently executed `poc_runner` oracle, fail-closed resized
  candidates without a plan, and no whole-image verification in Phase-8B. The
  CLI supports `--plan` and `--poc`; selftest is 19 cases.
- B5/B6 pipeline/runner: deterministic candidates emit and gate a patch plan;
  resolved scope, plan, ABI and oracle evidence are exchanged; per-sample
  original/candidate bytes, plan, metadata and verifier report are persisted.
- B7 real verification: `artifacts/phase8b-benchmark-2026-11-16/` records a
  12/12 executed run with 2 candidates, **2 independently verified**
  (`stack-strcpy-x86_64`, `heap-capacity-x86_64`), `false_verified=0`,
  `verification_disagreements=0`, and a real guest oracle run
  (`runner=limactl`, `tier=emulated_run`). The other 10 samples are analysis-only
  and are not claimed as independently verified.

## Evidence layers

1. Local frozen-tree nightly gate on the final release SHA (release evidence
   bundle; 13 required checks).
2. Real GitHub-hosted CI run on the final SHA; Phase-8B shadow checks are
   non-gating.
3. Real reference-host Phase-8B benchmark evidence with the executed emulated
   guest oracle.
4. Self-hosted Lima nightly: not_run; no claim.

## Remaining limits

- Two deterministic fixture repairs are independently verified under declared
  target scope plus a function-level oracle differential; this is not arbitrary
  binary or arbitrary vulnerability-class evidence.
- The 10 non-candidate samples and the hidden benchmark are not verified; hidden
  set is unavailable.
- `whole_image` is never verified in Phase-8B. ABI evidence is required and
  unavailable ABI is `not_run`. Oracle availability is host-dependent.
- Phase-8C (hidden/external corpus), Phase-8D (open-world discovery/Acceptance
  2.0), Phase-9/10 (cross-function and remaining families), and Phase-11..16
  remain future work.

See `docs/acceptance/phase8b-disagreement-analysis.md`,
`docs/operations/phase8b-real-verification.md`,
`docs/operations/phase8b-verifier-notes.md`,
`docs/operations/phase8b-contracts-notes.md`, and
`docs/acceptance/LIMITATIONS.md`.
