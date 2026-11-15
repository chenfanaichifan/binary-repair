# Phase-8C C1 baseline & hidden benchmark readiness audit (2026-11-16)

Read-only readiness audit on branch `feature/phase8c-ground-truth-v2` at
`227f45b39d85a7cd95e8589beb07dcfc89cd22d7`. No production code, contracts,
CI, claims, benchmark v1, release gate or Phase-8A/B evidence was modified; no
network or AI was used. Machine-readable facts:
`artifacts/phase8c-baseline-2026-11-16/phase8c-baseline-audit.json`; work
breakdown: `.../phase8c-work-breakdown.json`; plans:
`.../phase8c-hidden-isolation-plan.md`, `.../phase8c-lima-coordination-plan.md`;
verdict: `.../phase8c-readiness.md`.

## Q01 - mainline, release tag, evidence refs, drift

- Branch head measured from read-only git metadata files (no git commands):
  `227f45b39d85a7cd95e8589beb07dcfc89cd22d7`, which equals the expected
  Phase-8C baseline; branch is `feature/phase8c-ground-truth-v2`.
- Ref files present: tag `release-2026-11-16-phase8b` = `1bfdf674...`,
  tag `release-2026-11-16-phase8b-evidence` = `1edcce2d...`; the
  `release/2026-11-16-phase8b-evidence` branch ref is not present in this
  worktree (evidence-branch only).
- Claims Phase-8B block: phase8b base `dad21c98...`; gated CI SHA
  `c5d87b57...`; local gate artifact
  `artifacts/release-gate-2026-11-16-phase8b` is referenced but absent from
  this worktree.
- Drift: the expected mainline match is exact, so C1 uses `227f45b` as its
  baseline. There is an **evidence-binding drift/warning**: Phase-8B release
  evidence is bound to `c5d87b5` (and evidence tag `1edcce2d...`), not to the
  current HEAD. Phase-8C artifacts must record their own base/gated SHA and
  must not reuse Phase-8B evidence as if it covered this tree. This does not
  block C2/C11 start; it blocks any final Phase-8C evidence claim that would
  cite Phase-8B artifacts for the Phase-8C tree.

## Q02 - v1 12-sample lossless v2 migration

- v1 manifest: `benchmark/phase8-v1/manifest.json`, sha256
  `e7e7eca43518dc1b953faccead6f301f80eee4a59f1f0550dc8aad1bbd712052`,
  schema_version 1, 12 samples, splits dev=8/validation=4, hidden_available
  false, hidden_commitment_sha256 null.
- Migration matrix result: **12/12 samples present and lossless** - every
  binary sha matches the committed bytes, source refs and evidence refs
  resolve, all 19 required sample-schema fields are present, target/split/
  oracle metadata are preserved. 4/12 samples have `reference_fix=null`
  (analysis-only/negative-control or captured capacity sample); that is
  optional evidence, never an oracle substitute.
- v2 gaps to close in C2/C03 (no v1 loss): (a) manifest wrapper lacks an
  explicit benchmark_version/v1->v2 mapping block; (b) hidden split/aggregate
  policy and public-visibility contract are absent; (c) samples have no
  optional authority block (contract supports it) for plan/associated-change
  authorization; (d) results are not contract-pinned (Phase-8B added plan/
  oracle/layout fields without a results-v2 contract); (e) no hidden commitment
  contract; (f) reference_fix null must stay optional. Verdict: no migration
  blocker; v2 contracts are C2 work.

## Q03 - reproduce the two Phase-8B independently verified samples

- The two Phase-8B independently verified samples are
  `stack-strcpy-x86_64` and `heap-capacity-x86_64` (Phase-8B results summary:
  independently_verified=2, false_verified=0).
- C1 reproduced them through `scripts/run_repair_benchmark.py --verifier auto`
  using a temporary two-sample v1 manifest copy and a **temporary output
  directory**; the committed Phase-8A/B evidence was not written.
- Guest/Lima was available: `limactl 2.3.0`, instance `binaryrepair` Running
  (aarch64), guest runner tier `emulated_run`.
- Result: **2/2 reproduced and independently verified**:
  stack candidate `1bc66b2ee28e2370cca1fcea624378e72afcafeac02c1da4eead689cd64ff6f4`
  and heap candidate `93e27f2fc543b2c9652efe638adafbf239ba58965b07b5beda3e516817b033a2`,
  both matching the Phase-8B committed candidate hashes; verifier decision
  `verified`, oracle status `pass`, layout status `passed`, false_verified=0.
  If the guest had been unavailable this record would be `not_run` with the
  reason and no fabricated pass.

## Q04 - schema reuse/extension matrix

- Existing contracts: 13 (`capability`, `gap`, `acceptance`, `repair`,
  `evidence`, `reflection`, `benchmark-sample`, `verification`, `binary-target`,
  `vulnerability-finding`, `root-cause`, `patch-candidate`, `patch-plan`);
  checker: 13/13 valid and 13/13 invalid fixtures, jsonschema validator, sums
  verified, exit 0.
- `benchmark-sample` (v1) has 19 required properties plus optional `authority`,
  `hidden_available` const false and `hidden_commitment_sha256` (64-hex or
  null). This is reusable for v2 samples with additive fields only.
- Missing/extension needs: manifest-wrapper schema (benchmark_version,
  v1->v2 map, corpus visibility, aggregate policy), hidden-commitment schema
  (format/salt/reveal rules), results-v2 schema (benchmark_version,
  visibility, plan/oracle/layout evidence, verifier id, hidden aggregate
  fields), and optional per-sample v2 fields (authority, hidden eligibility,
  plan binding, provenance/license). Existing 13 contracts must remain valid;
  no breaking change to `benchmark-sample`.
- Verdict: reuse the sample/verification/patch-plan contracts, add 3-4 new
  contracts in C2, keep v1 artifacts valid.

## Q05 - hidden corpus isolation threat model

- Private root design: default `$HOME/.binaryrepair/phase8c-hidden`, override
  `PHASE8C_HIDDEN_ROOT`, mode `0700`; C1 observed the default root **absent**,
  env unset; C1 neither created nor read any hidden corpus. `hidden_available`
  remains false and the hidden commitment is null.
- Threat model: same-UID/root processes can read the private root; the
  isolation is **operational, not cryptographic**. Leak surfaces: logs,
  exception messages, temp files, runner artifacts, CI artifact uploads,
  environment dumps, public manifest/evidence refs, crash reports. Public
  output is aggregate-only (counts/rates/CI only), never per-sample hidden ids,
  bytes or hashes. Fork PRs/untrusted CI never receive the root or its secrets;
  trusted jobs mount it read-only and sanitize artifacts by allowlist.
- Commitment format (proposal): domain-separated SHA-256 over a canonical
  hidden manifest (hmac sample id, binary sha, split, class, oracle refs,
  expected outcome kind) with a campaign salt held outside the public tree;
  publish the commitment before the run, reveal aggregate metrics after the
  run (salt only if the Lead approves). Full plan:
  `phase8c-hidden-isolation-plan.md`.
- Verdict: design executable, but C05/C06/C08/C11 hidden execution remains
  blocked until the Lead provisions the Lead-owned root. C2/C11 design/tests
  can start without it.

## Q06 - Lima serialization inventory and plan

- Guest calls measured in `app/services/guest_runner.py` (limactl list/shell,
  guest run), `app/services/poc_runner.py` (runner selection + staged run),
  `scripts/run_hard_benchmark.py`, `scripts/run_repair_benchmark.py`,
  `scripts/release_gate.py` (identity probe + nightly real-Lima acceptance),
  `scripts/verify_repair_benchmark.py` and the verifier oracle path
  (`scripts/verify_repair.py` / `independent_verifier`).
- Current status: **no repository-wide global lock/lease** - concurrent
  limactl invocations can interleave. Proposed C09: one advisory lock file at
  `$HOME/.binaryrepair/locks/lima-guest.lock`, `fcntl.flock` exclusive with a
  JSON lease `{run_id,pid,acquired_at,ttl_s,attempt,operation}`, reentrancy via
  a per-run token, bounded acquire timeout with explicit `lock_timeout`
  not_run evidence, stale-pid/ttl recovery, and attempt/wait/release evidence
  fields. Callers must acquire around every limactl/guest run and release in a
  `finally` block; nested calls reuse the lease.
- Existing tests: `tests/test_guest_runner.py`, `tests/test_poc_runner.py`,
  `tests/test_verify_test_serial.py`,
  `tests/test_repair_benchmark_fixtures.py` and benchmark/verifier tests.
  Missing: lock acquire/release/timeout/reentrancy/stale-lease tests (C09).
- Verdict: inventory complete; implementation is C09, no blocker for C2.

## Q07 - C2-C14 dependency graph, parallelism and ownership

- Work breakdown (C1-C14) is in `phase8c-work-breakdown.json` with
  dependencies, write scopes, hard acceptance and blockers. Parallel groups:
  G1 can start together after C1: C02 contracts, C04 public corpus, C05 hidden
  builder, C07 results v2, C09 Lima lock; G2 after contracts/root: C03
  migration, C06 hidden commit/reveal, C08 runner v2; G3: C10 gate/CI shadow +
  C11 hidden isolation tests; G4: C12 claims/readiness + C13 Phase-8D data prep;
  G5: C14 final evidence/gate/report (Lead).
- Serial constraints: C01 first; C02 before all v2 producers; C05 before
  hidden consumers; C09 before gate/CI real guest runs. File ownership follows
  the write scopes in the breakdown; hidden corpus/root is Lead-owned.

## Q08 - gate/CI impact

- v1 benchmark and its results stay unchanged; the release gate keeps its
  current required-check matrix. Measured from `release_gate --list-checks`:
  pr=4 checks, release=12 checks, nightly=13 checks. The task premise says
  "release gate still 13 required"; measured release mode is 12 and nightly is
  13 - C10 must confirm the intended release-mode count with the Lead and
  document it, not silently change it.
- Phase-8C checks are proposed as **shadow/non-gating** in CI:
  `audit_phase8c_readiness.py --check`, v2 benchmark `--check`, hidden
  isolation/commitment checks (hidden stays not_run until the root exists).
  No Phase-8C check is added to the release gate required set in C1.
- Claims/readiness: Phase-8B claims already say hidden benchmark this phase
  false, no capability promotion; readiness G29 is `not_run` with
  `hidden_available=false`. Phase-8C must keep G29 not_run until a Lead-owned
  hidden run exists, and must not add a hidden aggregate claim before C05/C06.

## Q09 - Phase-8D gap/discovery data model preparation (not implemented)

Fields that Phase-8C outputs must preserve so Phase-8D discovery can consume
them without rework: benchmark_version (v1/v2) and sample visibility
(public/hidden); sample/binary sha plus authority/provenance refs; oracle
evidence refs (runner/tier/manifest sha) to separate oracle gaps from detector
gaps; hidden commitment refs for aggregate-only records; discovery_source and
proposed_experiment (already in GapRecord); dedup/lineage keys (sample sha +
benchmark version + target); capability dimension ids D01-D20 and universe
cell refs. GapRecord required fields are recorded in the baseline JSON. C1
implements none of these; C13 prepares them.

## Q10 - final work breakdown, hard acceptance and blocker verdict

- Work breakdown: C01 baseline/readiness (this task, done); C02 v2
  contracts/migration; C03 v1->v2 migration; C04 public corpus; C05 hidden
  builder; C06 hidden commit/reveal; C07 results v2; C08 runner v2; C09 Lima
  lock; C10 gate/CI shadow; C11 hidden isolation red-team; C12
  claims/readiness; C13 Phase-8D data prep; C14 final evidence/gate/report.
- Hard acceptance: v2 contracts + 12/12 lossless migration; hidden only under
  Lead-owned root with aggregate-only public output and not_run when absent;
  single guest lock with lease/timeout/attempt evidence; v1 gate checks
  unchanged and Phase-8C checks shadow; final evidence honest with no
  capability promotion/verified auto-upgrade.
- Blockers: B-HIDDEN-ROOT (hidden execution C05/C06/C08/C11 blocked until
  Lead provisions the root; C1 did not create/read it); B-P8B-EVIDENCE-BINDING
  (Phase-8B evidence bound to c5d87b5, not current HEAD; Phase-8C must bind its
  own SHA; warning for C12/C14); B-TOOLCHAIN-ZIG (Zig absent, C04 limited to
  clang/system toolchain); B-GATE-COUNT (release=12 vs stated 13; C10 must
  confirm). Warnings: v1 manifest/reference-fix optionality, hidden aggregate
  policy needs Lead approval, full-suite duration not measured in C1.
- Verdict: C1 is **ready with warnings**; C2 (v2 contracts/migration) and C11
  (hidden isolation design/tests) are unblocked to start. No new repair
  capability is claimed and no verified state is upgraded by this audit.
- Baseline facts collected: host darwin/arm64, Python 3.11.8, clang
  `/usr/bin/clang`, no Zig, limactl 2.3.0 + Lima guest available; test tree:
  222 test files / 2053 collected tests (full-suite duration not measured);
  corpora: hard-cases 12 cases, repair-benchmark 10 cases, 4 public dirs,
  4 Mach-O fixture dirs, 7 PE fixture dirs; contracts 13 with checker exit 0.
