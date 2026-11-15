# Phase-8C C1 final baseline audit (2026-11-16)

Final C1 baseline record for release claims. The Phase-8C branch was rebased
twice: original audit baseline `227f45b...`, first rebase `f42e6c4...`, current
mainline `a1755a5e661665218da93e967a535e359932975a` (external P21-P24 landed
before the Phase-8C commits; clean rebase). Current branch HEAD is
`910e4f7b...` (10 first-parent commits after `a1755a5e`); the C1-C13 commits are
on top. This audit re-collected all facts on that tree, reran the two Phase-8B
sample reproductions into temporary output only, and incorporated the C6/C10
runtime repeat evidence. No production code, contracts, CI, claims, benchmark
v1, release gate or Phase-8A/B evidence was modified; no network or AI was
used. Machine-readable facts:
`artifacts/phase8c-baseline-2026-11-16/phase8c-baseline-audit.json`.

## Q01 - mainline, release tag, evidence refs, drift

- Original C1 baseline `227f45b...`; previous rebase `f42e6c4...`; current
  mainline `a1755a5e...`; current branch head `910e4f7b...` (parent
  `a97dd703...`; expected mainline found 10 first-parent commits back).
- Ref files: tag `release-2026-11-16-phase8b` = `1bfdf674...`, evidence tag
  `release-2026-11-16-phase8b-evidence` = `1edcce2d...`, evidence branch
  `release/2026-11-16-phase8b-evidence` = `528304a9...`; the referenced local
  gate artifact directory is still absent from this worktree.
- Post-audit drift: external P21-P24 artifacts are present
  (`p21-p16r3-profile`, `p22-artifact-audit`, `p23-smoke`,
  `p23-stability-partial`), claims/artifacts changed; contracts remain 17 with
  the four v2 contracts; `benchmark/phase8c/manifest.json` is `d46f06bf...`
  (32 public samples: 24 runtime / 8 analysis-only overall; core 28 = 20
  runtime + 8 analysis-only); hidden private root exists with mode 0700 and C1
  stats it only, never reading hidden content; C4 hidden commitment (8 samples
  = 6 runtime + 2 analysis-only) and C6 hidden aggregate (8/8 executed, 0
  verified, 0 false) are available.
- Warnings (no active blockers from C1): Phase-8B evidence is bound to gated
  SHA `c5d87b5...`, not current HEAD; Phase-8B local gate artifact is absent;
  Zig is not on PATH (corpus/compiler expansion remains limited); measured
  release-gate counts are release=12/nightly=13 vs the stated "13 required"
  premise (B-GATE-COUNT). The hidden-root blocker is resolved: C4/C6 landed
  aggregate evidence and C1 never reads hidden content.

## Q02 - v1 12-sample lossless v2 migration

- v1 manifest sha256
  `e7e7eca43518dc1b953faccead6f301f80eee4a59f1f0550dc8aad1bbd712052`,
  schema_version 1, 12 samples, dev=8/validation=4, hidden false.
- Result: **12/12 present and lossless** - binary sha, all 19 required sample
  fields, source/evidence refs, target/split/oracle preserved; 4/12
  reference_fix null remains optional evidence.
- v2 contract state: 17 contracts total including manifest-v2,
  results-v2, ground-truth-sample-v2 and hidden-commitment; C2 adopted them and
  C3 produced the public v2 manifest without v1 loss. Remaining gaps are the
  migration/binding details already implemented by C2/C3 and are not C1
  blockers.

## Q03 - Phase-8B verified-sample reproduction on the final tree

- Reproduced through `scripts/run_repair_benchmark.py --verifier auto` with a
  temporary two-sample v1 manifest copy into a **temporary output**; committed
  evidence was not overwritten.
- Result: **2/2 independently verified** on the current tree: stack
  `1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4`, heap
  `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2`; both
  match Phase-8B candidates; verifier decision `verified`, oracle `pass`,
  layout `passed`, false_verified=0. Guest/Lima available (`limactl` instance
  `binaryrepair`, tier `emulated_run`); if it had been unavailable this would be
  recorded not_run.
- Runtime repeat evidence (C6/C10, read from committed artifacts):
  - public benchmark: 32 samples (24 runtime / 8 analysis-only; core 28 = 20
    runtime + 8 analysis-only), dev 18 / validation 14;
  - two serialized repeats under the C11 lock are identical, same results sha
    `a477ea3c...`; 2 independently verified, published false_verified=0,
    internal false_verified=1;
  - 1 heap-malloc deterministic claim was withdrawn after the independent
    verifier rejected it (`independent_decision: rejected`, ABI/plan reason);
  - hidden aggregate: 8 samples (6 runtime + 2 analysis-only), 8 executed, 0
    verified, 0 false, aggregate counts only.
- Flake status: the earlier one-off f42 C1 flake (one default attempt aborted
  with false_verified=1, then reproduced) was **not reproduced across the two
  serialized repeats**. It remains a **documented warning, not a C12/C14
  blocker**; unconditional stability is still not claimed and the full attempt
  history is recorded. The published repeat results sha is `a477ea3c...`; the
  current `results.json` file sha is `22f19119...` after the hidden aggregate
  merge, and both are recorded instead of pretending they are the same file.

## Q04 - schema reuse/extension matrix

- Contracts: **17** (four v2 contracts from external P17/P16R3: manifest-v2,
  results-v2, ground-truth-sample-v2, hidden-commitment). Checker: 17/17 valid
  and 17/17 invalid fixtures, exit 0. Existing 13 contracts remain valid.
- Reuse: ground-truth-sample-v2 for samples, verification/patch-plan for
  repair evidence, manifest-v2/results-v2 for runner output, hidden-commitment
  for the opaque hidden commitment. C2/C3 already adopted them; C1 records the
  matrix and does not modify contracts.

## Q05 - hidden corpus isolation threat model

- Private root: default `$HOME/.binaryrepair/phase8c-hidden`, override
  `PHASE8C_HIDDEN_ROOT`, mode 0700. Current observed state: root **exists**
  mode 0700; C1 does **not** create/list/read hidden content
  (`hidden_corpus_created=false`, `hidden_corpus_read=false`).
- Public manifest `hidden_available` remains false and
  `hidden_commitment_sha256` null; hidden evidence is the separate committed
  commitment (8/6/2) and aggregate (8 executed, 0 verified, 0 false).
- Threat model: same-UID/root can read the private root; isolation is
  **operational, not cryptographic**. Public output is aggregate-only; no
  hidden ids/paths/hashes/content. Leak surfaces: logs, exceptions, temp files,
  CI artifacts, env dumps, crash reports. Fork PRs never receive the root.
- Commitment format: domain-separated SHA-256 over a canonical hidden manifest
  with opaque ids/digests and a salt outside the public tree; public commitment
  and aggregate only. Full plan: `phase8c-hidden-isolation-plan.md`.

## Q06 - Lima serialization inventory and plan

- Inventory: `app/services/guest_runner.py`, `app/services/poc_runner.py`,
  `scripts/run_hard_benchmark.py`, `scripts/run_repair_benchmark.py`,
  `scripts/run_phase8c_benchmark.py`, `scripts/release_gate.py`,
  `scripts/verify_repair_benchmark.py`, `scripts/verify_repair.py` /
  `independent_verifier`.
- C11 implemented a single advisory lock with lease/timeout/attempt evidence;
  the C6/C10 serialized repeats under that lock are identical and no deadlock
  was observed. C1 records the inventory/design and the repeat evidence rather
  than re-validating the lock implementation. Missing lock-specific tests are
  C9/C11 scope, not C1.

## Q07 - C2-C14 dependency graph and parallelism

- C1-C14 work breakdown remains in `phase8c-work-breakdown.json` with
  dependencies, write scopes, acceptance and blockers. Parallel groups after
  C1: G1={C02,C04,C05,C07,C09}; G2={C03,C06,C08}; G3={C10,C11};
  G4={C12,C13}; G5={C14}. Serial: C1 first; C2 before producers; C5 before
  hidden consumers; C9 before gate/CI real guest runs. C1-C13 are now
  implemented/committed; the breakdown remains the historical coordination
  record.

## Q08 - gate/CI impact

- v1 unchanged; measured release-gate checks: pr=4, release=12, nightly=13.
  The stated "13 required" premise is recorded as a warning (B-GATE-COUNT);
  C10 confirmed the implemented counts, not a C1 blocker.
- Phase-8C checks remain shadow/non-gating: readiness `--check`, v2 benchmark
  `--check`, contamination/quality checks. G29 stays not_run with
  hidden_available=false; no hidden capability claim is added.
- Claims/readiness: Phase-8B claims remain bound to their own gated SHA; C1
  records the current tree SHA and does not reuse Phase-8B evidence as
  covering Phase-8C.

## Q09 - Phase-8D gap/discovery data model preparation (not implemented)

Preserve for Phase-8D: benchmark_version/visibility; sample/authority/
provenance refs; oracle evidence refs; hidden commitment refs for aggregate
records; discovery_source/proposed_experiment (already in GapRecord);
dedup/lineage keys (sample sha + benchmark version + target); capability
dimension ids D01-D20 and universe cell refs. C1 implements none of these;
C13 prepared the alignment fields.

## Q10 - final work breakdown, hard acceptance and blocker verdict

- Work breakdown: C1-C14 retained; C1 is this final record, C2 contracts/
  migration, C3 public corpus, C4 hidden corpus+commitment, C5 contamination,
  C6 runner/results, C7 external ingestion, C8 variants, C9 Lima lock,
  C10 gate/CI repeat, C11 hidden isolation, C12 claims/readiness, C13 quality
  audit, C14 final evidence/gate.
- Hard acceptance: v2 contracts + 12/12 lossless migration; hidden only under
  the Lead-owned root with aggregate-only output and not_run when unavailable;
  single guest lock with repeat/attempt evidence; v1 gate checks unchanged;
  honest evidence with no capability promotion/verified auto-upgrade.
- Status: **ok_rebaselined**. Active blockers/warnings: B-P8B-EVIDENCE-BINDING
  (warning for C12/C14 evidence citation), B-TOOLCHAIN-ZIG (warning for C04),
  B-GATE-COUNT (warning for C10); the former hidden-root blocker is
  **resolved** (C4/C6 aggregate evidence landed; C1 never reads hidden
  content). The one-off flake is a **documented warning only**, not a blocker;
  the two serialized repeats are identical and published false_verified=0.
- Baseline facts: host darwin/arm64, Python 3.11.8, clang `/usr/bin/clang`, no
  Zig on PATH, limactl 2.3.0 + Lima guest available; test tree 237 files / 2232
  collected tests (full-suite duration not measured); corpora hard-cases 12,
  repair-benchmark 10, 4 public dirs, Mach-O/PE fixture dirs unchanged;
  contracts 17 with checker exit 0; public manifest sha `d46f06bf...`;
  hidden commitment sha `3ebf2901...` (8/6/2); public results sha
  `22f19119...`; repeat results sha `a477ea3c...`; hidden aggregate sha
  `18f7e39a...`.
- No new repair capability is claimed and no verified state is upgraded by
  this audit.
