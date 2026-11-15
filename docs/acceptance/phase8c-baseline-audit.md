# Phase-8C C1 baseline & hidden benchmark readiness audit (2026-11-16)

Read-only readiness audit for Phase-8C ground-truth v2. This artifact was
originally generated on `227f45b39d85a7cd95e8589beb07dcfc89cd22d7`; after the
branch was rebased onto latest mainline `f42e6c4...` (external P16-R3) the C1
facts were re-collected and the two verified samples were reproduced again into
a temporary output. The current audit commit is `6d7ad861...` whose parent is
the rebased mainline `f42e6c4...`. No production code, contracts, CI, claims,
benchmark v1, release gate or Phase-8A/B evidence was modified; no network or
AI was used. Machine-readable facts:
`artifacts/phase8c-baseline-2026-11-16/phase8c-baseline-audit.json`.

## Q01 - mainline, release tag, evidence refs, drift

- Original C1 baseline: `227f45b39d85a7cd95e8589beb07dcfc89cd22d7`.
- Rebased mainline: `f42e6c4f39b584575f59b13d67f40572b3ca278c`; current audit
  commit (branch `feature/phase8c-ground-truth-v2`):
  `6d7ad861694e287cf446cdc195990bcf7889dd2c`, parent verified from the git
  commit object to be `f42e6c4...`.
- Ref files: tag `release-2026-11-16-phase8b` = `1bfdf674...`, evidence tag
  `release-2026-11-16-phase8b-evidence` = `1edcce2d...`, evidence branch
  `release/2026-11-16-phase8b-evidence` = `528304a9...` (the evidence branch ref
  is now present; the referenced local gate artifact directory is still absent
  from this worktree).
- Post-audit drift (recorded truthfully): branch rebased from 227f45b to f42e6c4;
  external P16-R3 added `app/services/elf_mapping.py`, changed
  `verification_semantics.py`, changed claims/artifacts, added four v2 contracts
  (contracts dir now 17) and changed
  `artifacts/phase8b-benchmark-2026-11-16/results.json` (still
  independently_verified=2, false_verified=0). The hidden private root also
  appeared with mode 0700 (Lead-owned); C1 stats it only and never reads it.
- Warnings: Phase-8B release evidence remains bound to gated SHA `c5d87b5...`,
  not current HEAD; Phase-8C must record its own base/gated SHA and may not
  reuse Phase-8B evidence as covering this tree. No mainline-parent mismatch.

## Q02 - v1 12-sample lossless v2 migration

- v1 manifest: `benchmark/phase8-v1/manifest.json`, sha256
  `e7e7eca43518dc1b953faccead6f301f80eee4a59f1f0550dc8aad1bbd712052`,
  schema_version 1, 12 samples, splits dev=8/validation=4, hidden_available
  false, hidden_commitment_sha256 null.
- Result: **12/12 samples present and lossless** - binary sha, all 19 required
  sample fields, source/evidence refs, target/split/oracle metadata preserved.
  4/12 reference_fix null (optional evidence, never an oracle substitute).
- Current v2 gaps after P16-R3: the four v2 contracts now exist
  (benchmark-manifest-v2, benchmark-results-v2, ground-truth-sample-v2,
  hidden-benchmark-commitment), so C2 must reconcile/adopt them rather than
  recreate; the v1->v2 migration builder/mapping artifact (C3) is still needed;
  v1 samples do not yet carry authority/plan binding; the runner/results writer
  does not yet emit v2 results; hidden_available remains false/commitment null;
  reference_fix stays optional. Verdict: no migration blocker; C2/C3 work
  narrowed to adoption + migration rather than contract creation.

## Q03 - reproduce the two Phase-8B independently verified samples on f42

- Guest/Lima available: `limactl 2.3.0`, instance `binaryrepair` Running
  (aarch64), tier `emulated_run`.
- Reproduced via `scripts/run_repair_benchmark.py --verifier auto` with a
  temporary two-sample v1 manifest copy and a **temporary output**; committed
  evidence untouched.
- Change after rebase: **candidate hashes are unchanged** and the successful
  run independently verifies both samples: stack
  `1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4`, heap
  `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2`; verifier
  decision `verified`, oracle `pass`, layout `passed`, false_verified=0.
- **Reproduction is flaky across attempts**: the first f42 default run aborted
  with `false_verified=1` (new verifier rejected a deterministic claim); the
  diagnostic `--claim-policy withdraw` attempts then verified both samples, and
  a second default run reproduced 2/2. `reproducibility_history` records both
  attempts; stability = `flaky_observed_1_of_2_default_runs`. Therefore Phase-8C
  must not claim unconditional 2/2 stability; blocker
  `B-POST-REBASE-REPRODUCTION-FLAKY` (warning for verification claims) blocks
  C12/C14 until the flake is triaged. If the guest had been unavailable the
  record would be `not_run` with the reason and no fabricated pass.

## Q04 - schema reuse/extension matrix

- Contracts: **17** (was 13): the original set plus
  `benchmark-manifest-v2`, `benchmark-results-v2`,
  `ground-truth-sample-v2`, `hidden-benchmark-commitment` from external P16-R3.
  Checker: 17/17 valid + 17/17 invalid fixtures, jsonschema, sums verified,
  exit 0.
- Reuse: `benchmark-sample`/`ground-truth-sample-v2` for samples; `verification`
  and `patch-plan` for verification/layout evidence; the new manifest-v2 and
  results-v2 contracts cover the previously missing wrapper/results surfaces;
  hidden commitment contract covers the hidden commitment format.
- Remaining matrix work: adopt these contracts in the Phase-8C producers
  (manifest migration, results writer, hidden campaign), bind v1 samples to the
  authority/plan fields additively, and keep v1 artifacts valid. No breaking
  change to `benchmark-sample` is needed.
- Verdict: contract matrix largely landed externally; C2 is now
  reconciliation + migration, not greenfield schema design.

## Q05 - hidden corpus isolation threat model

- Private root design: default `$HOME/.binaryrepair/phase8c-hidden`, override
  `PHASE8C_HIDDEN_ROOT`, mode `0700`. Current observed state: root **exists**
  with mode `0700`; env unset; C1 only stats it and never lists/reads hidden
  contents (`hidden_corpus_created=false`, `hidden_corpus_read=false`).
  `hidden_available` remains false and `hidden_commitment_sha256` null; no
  hidden run is claimed.
- Threat model: same-UID/root processes can read the private root; isolation is
  **operational, not cryptographic**. Leak surfaces: logs, exception messages,
  temp files, runner artifacts, CI artifact uploads, environment dumps, public
  manifest/evidence refs, crash reports. Public output must be aggregate-only
  (counts/rates/CI), never hidden sample ids/bytes/hashes. Fork PRs/untrusted CI
  never receive the root; trusted jobs mount it read-only and sanitize artifacts.
- Commitment format (proposal): domain-separated SHA-256 over a canonical hidden
  manifest (hmac sample id, binary sha, split, class, oracle refs, expected
  outcome kind) with a campaign salt outside the public tree; publish commitment
  before run, reveal aggregates after (salt only with Lead approval). Full
  plan: `phase8c-hidden-isolation-plan.md`.
- Verdict: root now provisioned, but C1 does not read it; C05/C06/C08/C11
  require Lead coordination and MUST record hidden results as not_run until an
  authorized campaign executes. `hidden_available` stays false.

## Q06 - Lima serialization inventory and plan

- Guest calls: `app/services/guest_runner.py` (limactl list/shell/run),
  `app/services/poc_runner.py` (runner selection + staged run),
  `scripts/run_hard_benchmark.py`, `scripts/run_repair_benchmark.py`,
  `scripts/release_gate.py` (identity probe + nightly real-Lima acceptance),
  `scripts/verify_repair_benchmark.py`, the verifier oracle path
  (`scripts/verify_repair.py` / `independent_verifier`).
- Current status: **no repository-wide global lock/lease**; concurrent guest
  invocations can interleave. Proposed C09: one advisory lock file at
  `$HOME/.binaryrepair/locks/lima-guest.lock`, `fcntl.flock` exclusive with a
  JSON lease `{run_id,pid,acquired_at,ttl_s,attempt,operation}`, reentrancy via
  per-run token, bounded acquire timeout with explicit `lock_timeout` not_run
  evidence, stale-pid/ttl recovery, attempt/wait/release evidence. Callers
  acquire around every limactl/guest run and release in `finally`; nested calls
  reuse the lease.
- Existing tests: `tests/test_guest_runner.py`, `tests/test_poc_runner.py`,
  `tests/test_verify_test_serial.py`,
  `tests/test_repair_benchmark_fixtures.py` and benchmark/verifier tests.
  Missing: lock acquire/release/timeout/reentrancy/stale-lease tests (C09).
- The flaky reproduction in Q03 strengthens the case for C09 serialization.
- Verdict: inventory complete; implementation C09; no blocker for C2.

## Q07 - C2-C14 dependency graph, parallelism and ownership

- Work breakdown C1-C14 is in `phase8c-work-breakdown.json` with dependencies,
  write scopes, hard acceptance and blockers. Parallel groups after C1:
  G1={C02,C04,C05,C07,C09}; G2={C03,C06,C08}; G3={C10,C11}; G4={C12,C13};
  G5={C14}. Serial: C01 first; C02 before producers; C05 before hidden
  consumers; C09 before gate/CI real guest runs. File ownership follows the
  breakdown write scopes; hidden root is Lead-owned.

## Q08 - gate/CI impact

- v1 unchanged; measured release-gate checks: pr=4, release=12, nightly=13.
  The task premise says 13 required; measured release is 12/nightly 13, so C10
  must confirm the intended counts (B-GATE-COUNT) instead of silently changing.
- Phase-8C checks remain shadow/non-gating: readiness `--check`, v2 benchmark
  `--check`, hidden isolation checks (hidden not_run until an authorized
  campaign). No Phase-8C check is added to the release-gate required set.
- Claims/readiness: Phase-8B claims still say hidden benchmark this phase false
  and no capability promotion; G29 remains not_run with hidden_available=false.
  Phase-8C keeps G29 not_run and adds no hidden aggregate claim before an
  authorized C05/C06 run. Evidence branch ref now exists; Phase-8B local gate
  artifact dir is still absent locally.

## Q09 - Phase-8D gap/discovery data model preparation (not implemented)

Preserve for Phase-8D: benchmark_version/visibility; sample/authority/provenance
refs; oracle evidence refs (runner/tier/manifest sha); hidden commitment refs
for aggregate-only records; discovery_source/proposed_experiment (already in
GapRecord); dedup/lineage keys (sample sha + benchmark version + target);
capability dimension ids D01-D20 and universe cell refs. C1 implements none;
C13 prepares them. With 17 contracts now present, C13 can align to
manifest-v2/results-v2/ground-truth-sample-v2 schemas directly.

## Q10 - final work breakdown, hard acceptance and blocker verdict

- Work breakdown: C01 baseline/readiness (this task); C02 v2 contract
  reconciliation; C03 v1->v2 migration; C04 public corpus; C05 hidden builder;
  C06 hidden commit/reveal; C07 results v2 adoption; C08 runner v2; C09 Lima
  lock; C10 gate/CI shadow; C11 hidden isolation red-team; C12
  claims/readiness; C13 Phase-8D data prep; C14 final evidence/gate/report.
- Hard acceptance: v2 contracts adopted + 12/12 lossless migration; hidden only
  under Lead-owned root with aggregate-only output and not_run until authorized;
  single guest lock with lease/timeout/attempt evidence; v1 gate checks
  unchanged; final evidence honest with no capability promotion/verified
  auto-upgrade.
- Blockers/warnings: B-HIDDEN-ROOT (coordination_required: root exists 0700 but
  C1 does not read it; hidden paths C05/C06/C08/C11 stay not_run until
  authorized); B-P8B-EVIDENCE-BINDING (warning C12/C14); B-TOOLCHAIN-ZIG
  (warning C04); B-GATE-COUNT (warning C10); **B-POST-REBASE-REPRODUCTION-FLAKY**
  (warning for verification claims C12/C14: one f42 default reproduction failed
  with false_verified=1 while diagnostic withdraw runs and a second default run
  verified 2/2; triage before unconditional claims).
- Status: `ok_rebaselined_with_flaky_reproduction`; C2 and C11 design/tests are
  unblocked, but any Phase-8C claim of stable 2/2 verification on f42 is
  blocked until the reproduction flake is triaged. No new repair capability is
  claimed and no verified state is upgraded.
- Baseline facts: host darwin/arm64, Python 3.11.8, clang /usr/bin/clang, no
  Zig, limactl 2.3.0 + Lima guest available; test tree 226 files / 2105
  collected tests (full-suite duration not measured); corpora hard-cases 12,
  repair-benchmark 10, 4 public dirs, 4 Mach-O fixture dirs, 7 PE fixture dirs;
  contracts 17 with checker exit 0; phase8b results sha
  `c9e74902abb909457bdc0e40505666e1c550fe92c616c50667d64261160a6f3f`.
