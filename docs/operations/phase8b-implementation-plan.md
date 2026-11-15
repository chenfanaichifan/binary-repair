# Phase-8B B2 implementation plan: verifier semantics and evidence exchange

Status: plan derived from the B1 baseline audit (task-33). It is not an
implementation; phase B2 work is gated on Lead approval of this plan. The plan
does not change any generator claim or acceptance rule merely to make the two
known candidates pass.

## 1. Scope and non-goals

Scope: make the independent verifier able to receive and replay the facts a
deterministic repair actually produces (resolved target scope, patch plan,
associated changes, ABI evidence, executed oracle evidence, persisted
candidate/plan/report), while keeping fail-closed semantics.

Non-goals: no AI/provider call in verification; no loosening of target scope;
no hidden-benchmark claim; no production acceptance rule change based only on a
generator self-claim; no benchmark v1 rewrite.

## 2. Work packages

### P1 - Exchange contracts (V8B-02, V8B-04, V8B-05, V8B-06)

1. Define a versioned **patch plan** contract: plan id/version, generator id,
   original sha256, target sha256, resolved target scope (va/end or file range),
   ordered actions (kind/site_va/offset/size/before/after), insertions/cave
   regions, declared **associated changes** (kind, scope, before/after sha,
   reason), ABI evidence block, oracle-evidence digest.
2. Extend runner metadata to carry: pipeline-resolved target scope, abi_block,
   patch plan reference, declared associated changes, oracle evidence digest.
3. Keep a compatibility path: missing contract fields produce an explicit
   not_run/failed check, never a silent pass.

### P2 - Verifier replay semantics (V8B-01, V8B-03)

1. Implement plan replay: start from original bytes, apply rewrites/insertions/
   cave actions in plan order, require the result to equal candidate bytes
   exactly; reject any extra raw diff not declared by the plan.
2. Keep rewrite-only replay as a fast path for equal-size plans.
3. Verify associated changes against the plan and an explicit scope rule;
   undeclared raw-diff bytes fail closed.

### P3 - Oracle and ABI wiring (V8B-01, V8B-05)

1. Wire `run_poc` into the CLI (`--poc`) and the module adapter; persist the
   oracle report (runner/tier/status/evidence hash) in the verifier report.
2. Derive ABI evidence from the patched block (function range, arch, ABI id),
   exchange it and keep the verifier authoritative; unavailable ABI remains
   not_run.

### P4 - Artifact exchange and reproducibility (V8B-07)

1. Persist per-sample candidate bytes, patch plan, runner metadata and verifier
   report in the benchmark disagreement artifact, bound by SHA256SUMS.
2. Add a deterministic `--check` that re-verifies hashes/plan/report offline.

## 3. Acceptance criteria

- `V8B-01` acceptance: CLI `--poc` executes `run_poc`; a declared-but-not-run
  oracle can never yield `verified`; report records oracle evidence.
- `V8B-02` acceptance: exchanged resolved scope makes the stack sample
  `target-scope=passed`; an unresolved symbol still fails closed.
- `V8B-03` acceptance: a cave/insertion candidate replays from the declared
  plan and reaches the remaining checks; replay mismatch fails closed; the heap
  equal-size rewrite still passes.
- `V8B-04` acceptance: declared associated changes are replayed and scope-checked
  explicitly; undeclared out-of-scope changes still fail closed; the pipeline
  gate and verifier use the same declared change set.
- `V8B-05` acceptance: ABI check runs on a derived block; missing/unsupported
  ABI is not_run (never pass).
- `V8B-06` acceptance: plan contract round-trips, plan tamper fails closed, and
  the verifier reports the plan digest.
- `V8B-07` acceptance: every disagreement artifact contains candidate/plan/
  metadata/report files with matching hashes and offline reproduction.

## 4. Phase and dependency order

1. Phase B2a: contracts + plan production (P1) - no verifier behavior change yet.
2. Phase B2b: verifier replay semantics + oracle/ABI wiring (P2/P3) behind
   explicit contract presence checks.
3. Phase B2c: artifact exchange + `--check` (P4) and re-run the Phase-8A
   benchmark with `--verifier auto`.
4. Phase B2d: re-adjudicate the two B1 disagreements; a candidate remains
   unverified unless all required checks pass with the new contracts, and the
   independent oracle must execute.

Dependencies: P1 -> P2; P1 + P3 -> P4; B2 must not merge before the patch-plan
contract tests land. The baseline artifact and this plan are inputs; they gate
implementation start.

## 5. Risks

- Contract creep: every new field must have a fail-closed test and a version.
- Scope bypass risk: associated changes must not become a generic escape from
  target scope; they need kinds, bounds and an explicit allow/deny rule.
- Host-dependent oracle: verifier tests must record not_run honestly and CI
  must not require a real Lima run except in the designated acceptance lane.
