# Phase-8C release note: Ground Truth v2, Hidden Benchmark and Benchmark Integrity

Release identity: the final release SHA/tree and hosted-CI run are recorded in
`docs/status/claims.json`, `artifacts/release-gate-2026-11-16-phase8c/` and the
evidence branch. This note does not claim a capability promotion.

## What Phase-8C delivers

- **Ground Truth v2** (`contracts/ground-truth-sample-v2.schema.json`): 36-field
  structured sample contract; public manifest, hidden commitment and benchmark
  results have separate v2 contracts (17 contracts total, old 13 unchanged).
- **Lossless v1 migration**: all 12 Phase-8A samples map to v2 without changing
  sample ids, binary hashes, splits, targets, oracles, references or evidence.
- **Public benchmark v2**: 32 samples = 28 core + 4 validated Zig compiler/
  optimization variants; 24 runtime-oracle and 8 analysis-only; dev 18 /
  validation 14. The 28 core samples are 12 migrations, 12 committed hard/repair
  cases, and 4 cross-architecture analysis-only samples. Four compiler variants
  were admitted only after the original PoC oracle actually executed in the
  guest; failed probes are recorded with reasons.
- **Private hidden benchmark**: 8 samples = 6 validated runtime + 2
  analysis-only, built from distinct private variants. Only an opaque
  commitment, aggregate counts and private-report hash are published; no hidden
  binary, PoC, reference fix, path or per-sample id enters the repository. The
  initial hidden build contained one binary identical to a public variant; it
  was regenerated and the hidden/public contamination audit is clean.
- **Contamination audit**: public/hidden exact binary/PoC/reference/source SHA
  checks, normalized executable-section fingerprints, capstone opcode 4-gram
  Jaccard and text similarity. Public verdict clean; hidden verdict clean; 0
  unresolved hidden/public overlaps.
- **Benchmark runner v2**: layered detection, root-cause, localization,
  strategy, candidate, independent-verification and regression metrics; explicit
  denominators and `not_run`/`blocked`/`unsupported`/`analysis_only` accounting;
  a zero denominator yields `null`, never a fabricated zero; published
  `false_verified=0`.
- **Semantic regression**: declared PoC regression cases are executed for
  original/candidate; stdout/stderr/exit/crash changes reject the candidate;
  unavailable cases are `not_run`. This is bounded behavioural evidence, not a
  semantic-equivalence proof.
- **Lima guest coordination**: cross-process `flock` lease with reentrant
  process-local locking, bounded timeout, typed `blocked` state and attempt
  evidence. All `run_path`/`run_poc` Lima executions are serialized. External
  direct `limactl` probes outside those paths remain unguarded.
- **CI/audit shadow checks**: public-only Phase-8C checks are non-gating; the
  release gate remains the existing 13 required nightly checks. Hidden and real
  Lima evidence is reference-host evidence and is not reproduced by CI.

## Measured results (reference host)

Public benchmark, final manifest `d46f06bf...`:

- 32 samples, 24 runtime-oracle, 8 analysis-only; 30 executed, 2 unsupported
  (`variant-cwe122-O2-stripped`, `variant-cwe125-Os-static-stripped` target
  resolution), 0 not_run/blocked/invalid.
- 3 verification attempts: 2 independently verified, 1 rejected, published
  false_verified=0. One deterministic claim (`heap-malloc`) was withdrawn after
  the independent verifier's ABI check rejected it
  (`branch_target_unknown`, `call_target_not_allowed`, `no_ret`); the
  disagreement is preserved in `disagreements.json` and is not counted as a
  pass.
- Eligible repair cases 24; verified-repair rate 2/24 = 0.0833; detection,
  root-cause and localization 3/24. Analysis-only detection 6/8.
- Two serialized repeats produced identical result digests
  (`a477ea3c...`); unconditional stability is not claimed. The earlier one-off
  C1 reproduction flake was not reproduced under the C11 lock; it remains a
  documented warning.

Hidden benchmark, final commitment `eaec60aa...` / file sha `3ebf2901...`:

- 8 samples = 6 runtime + 2 analysis-only; all 8 executed; 0 candidates,
  0 independently verified, 0 rejected, 0 false_verified.
- This is measured deterministic-engine coverage, not a hidden-generalization
  capability claim. Hidden material remains private; the aggregate is bound to
  the commitment and private-report hash only.

## Honest limitations

- Hidden corpus material is not distributed; isolation is operational
  (0700 root, no CI access, aggregate-only output), not cryptographic against a
  same-UID/root reader. The public manifest intentionally keeps
  `hidden_commitment=null` so the separate commitment does not create a circular
  manifest/commitment digest; full quality records this as one warning.
- Hidden verification coverage is 0 independently verified repairs. The public
  benchmark's two verified repairs remain two deterministic fixture repairs
  under declared target scope; they do not establish arbitrary-binary,
  arbitrary-vulnerability or whole-program capability.
- `heap-malloc` exposes a real engine/plan-vs-verifier ABI disagreement; the
  deterministic claim is withdrawn, not repaired or relabelled.
- External-sample ingestion is `not_run` because no local external corpus was
  supplied. Cross-compiler verification is not claimed: the four variants use
  Zig 0.17.1 only; a second Linux compiler was not available. Cross-architecture
  samples are analysis-only.
- Self-hosted Lima nightly is `not_run`; international provider matrix is not
  run. Host-dependent guest contention can affect reference-host measurements;
  no unconditional reproducibility claim is made.
- Phase-8D (open-world discovery/Acceptance 2.0) and Phase-9-16 are not
  implemented or claimed. No new vulnerability-repair capability, automatic
  upgrade or capability promotion occurred in this phase.

## Evidence

| Evidence | Path |
|---|---|
| Baseline/readiness audit | `artifacts/phase8c-baseline-2026-11-16/` |
| Public corpus v2 | `benchmark/phase8c/manifest.json`, `PROVENANCE.json`, `SHA256SUMS` |
| Public benchmark | `benchmark/phase8c/results.json`, `artifacts/phase8c-benchmark-2026-11-16/` |
| Hidden commitment/aggregate | `benchmark/phase8c/hidden-commitment.json`, `artifacts/phase8c-hidden-2026-11-16/aggregate.json` |
| Contamination | `artifacts/phase8c-contamination-2026-11-16/` |
| Quality audit | `artifacts/phase8c-quality-2026-11-16/` |
| Release evidence | `artifacts/phase8c-release-2026-11-16/` |
| Release gate | `artifacts/release-gate-2026-11-16-phase8c/` |
