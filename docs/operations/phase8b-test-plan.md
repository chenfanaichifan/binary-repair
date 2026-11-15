# Phase-8B B2 test plan: verifier semantics and evidence exchange

Derived from the B1 baseline audit (task-33). Tests are specified before
implementation; every gap V8B-01..V8B-07 has positive, negative and tamper
coverage. No test may make a candidate pass by weakening target scope.

## 1. Test layers

1. **Contract tests** (unit): parse/validate patch plan, associated changes,
   ABI evidence, oracle evidence, resolved scope; reject unknown versions,
   duplicate action ids, missing hashes, out-of-order actions.
2. **Replay tests** (unit): plan replay equals candidate bytes for equal-size
   rewrites, cave insertions and associated `.rodata` changes; extra undeclared
   raw-diff bytes fail closed; tampered bytes fail closed.
3. **Exchange tests** (integration): runner -> verifier metadata carries
   resolved target scope, abi_block, plan, associated changes and oracle
   evidence; missing fields are not_run, never pass.
4. **Oracle tests** (integration): CLI `--poc` executes run_poc; the report
   records runner/tier/status/evidence hash; declared-but-unexecuted oracle can
   never verify; oracle failure rejects.
5. **Artifact tests** (integration): benchmark disagreement artifacts contain
   candidate bytes, plan, metadata and verifier report; SHA256SUMS verify;
   `--check` detects tamper and stale reports.
6. **Regression tests**: baseline benchmark samples keep their expected
   decisions; unrelated acceptance/release gates remain unchanged.

## 2. Must-pass acceptance cases

| id | case | expected |
|---|---|---|
| V8B-01-a | CLI --poc with a valid manifest | oracle executed, evidence recorded, decision reflects all checks |
| V8B-01-b | CLI --poc with runner unavailable | runtime-oracle not_run, no verified decision |
| V8B-01-c | CLI --poc declared but not injected | fail closed (not_run) |
| V8B-02-a | stack candidate with exchanged resolved va/end | target-scope passed |
| V8B-02-b | unresolved symbol without scope | target-scope not_run/failed, never pass |
| V8B-03-a | stack cave/insertion candidate (B1 candidate sha) | plan replay matches candidate bytes; action-replay passed |
| V8B-03-b | one byte changed in candidate | replay mismatch, rejected |
| V8B-03-c | heap equal-size rewrite | action-replay passed |
| V8B-04-a | heap capacity candidate with declared .rodata associated change | associated change replayed and scope-checked |
| V8B-04-b | undeclared out-of-scope action | target-scope failed |
| V8B-04-c | associated change with wrong hash/bounds | rejected |
| V8B-05-a | derived abi_block in metadata | abi check runs and reports evidence |
| V8B-05-b | missing abi_block | abi not_run, never verified |
| V8B-06-a | valid patch plan round-trip | plan digest recorded |
| V8B-06-b | plan tamper (action/offset/hash) | rejected |
| V8B-07-a | artifact has candidate/plan/metadata/report | hashes match and reproduce offline |
| V8B-07-b | report changed after write | --check exit 1 |

## 3. Fixtures and harness

- Reuse the B1 artifacts (`artifacts/phase8b-baseline-2026-11-16/`) as frozen
  fixtures: original.elf, candidate.bin, outcome.json, metadata.json,
  verifier-report.json for both samples.
- Add hermetic unit fixtures for plan replay (no real binary execution).
- Keep dynamic oracle tests behind the existing capability probe: record
  not_run when Lima/host is unavailable; never fabricate pass.
- Determinism: same inputs produce identical verifier report hashes; tests must
  not depend on wall clock, network, provider or AI.

## 4. Commands

```
pytest -q tests/test_phase8b_verifier_semantics.py \
          tests/test_phase8b_audit.py
python scripts/audit_phase8b_verifier_semantics.py --check
python scripts/verify_repair.py --selftest --json
python scripts/check_language_policy.py
```

## 5. Exit criteria

B2 is complete only when: all V8B acceptance cases pass; the Phase-8A benchmark
re-run records the two disagreements either as independently verified with the
new contracts or as explicit fail-closed not_run/rejected reasons (never
false_verified); the disagreement artifacts are reproducible offline; and the
release gate/acceptance/claims files remain untouched by this work.
