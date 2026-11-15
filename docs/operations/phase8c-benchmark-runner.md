# Phase-8C benchmark runner v2 (C6) and semantic regression (C10)

Status: implemented in the Phase-8C `feature/phase8c-ground-truth-v2` branch.
Consumers: C2 contract checker, C12/C14 evidence binding, the Lead-run hidden lane.

## Files

- `app/services/benchmark_runner.py` - public/hidden benchmark execution,
  layered metrics, deterministic artifacts, offline `check_artifact`.
- `app/services/semantic_regression.py` - C10 regression classification of
  declared PoC/regression evidence (accept / reject / not_run; never a full
  semantic-equivalence claim).
- `scripts/run_phase8c_benchmark.py` - CLI (`--manifest`, `--split`,
  `--verifier auto|none|path`, `--out`, `--hidden-root`,
  `--hidden-aggregate-out`, `--json`, `--repeat`, `--check-artifact`).
- `tests/test_phase8c_runner.py`, `tests/test_semantic_regression.py`.

Canonical outputs:

- `benchmark/phase8c/results.json` - C2 `benchmark-results-v2` document
  (validated by the `phase8c-results` integration in
  `scripts/check_contract_schemas.py`).
- `artifacts/phase8c-benchmark-2026-11-16/` - per-sample evidence
  (`samples/<id>/outcome.json`, verifier report, candidate sha256), layered
  `metrics.json`, `README.md`, `SHA256SUMS`.
- `artifacts/phase8c-hidden-2026-11-16/aggregate.json` - hidden lane only:
  counts and layered aggregates, commitment + private-report hashes. No
  per-sample hidden ids, paths, bytes or case details are ever published.

## Status matrix and metrics

Per sample status: `executed`, `not_run`, `blocked`, `unsupported`, `invalid`.
Samples are never silently dropped: every non-executed sample carries an
explicit `not_run_reason`.

Eligibility for repair rates (`verified_repair_rate` denominator):

1. `expected_scope` is `function` or `whole_program`;
2. the oracle is a real runtime oracle (`external_poc`, `native`, `emulated`);
3. the manifest declares judgeable expected behaviour (expected original and
   candidate behaviour, a PoC manifest path, or a required semantic-regression
   contract).

`analysis_only` samples are excluded from repair rates and reported separately
(detection is still measured). `not_run`/`blocked`/`unsupported`/`invalid`
samples stay in the status counts and count against detection/localization
rates; they never become a pass. A zero denominator yields `null`, never a
fabricated `0`.

Layered metrics (`metrics.json`) cover overall, per format, per arch and per
vulnerability family.

## Independent verification and false_verified

`verified_count` counts only `app.services.independent_verifier` decisions.
The deterministic engine's own gate is never accepted. A deterministic
"verified" claim that the independent verifier rejects is a
`false_verified` disagreement:

- default claim policy `withdraw`: the published C2 document withdraws the claim
  (`false_verified=false`, contract-valid), the disagreement is recorded in
  `evidence.disagreements` and the run exits 1;
- `--claim-policy fail_on_disagreement`: the claim is retained
  (`false_verified=true`) so the artifact intentionally fails the C2 checker,
  and the run exits 1.

Either way `false_verified` is never hidden, and a non-zero internal count is
always a non-zero exit.

## Guest serialization (C11)

Runtime-oracle samples are executed under the C11
`guest_coordinator.acquire_lima_guest_lock` lease (the PoC runner's own inner
lease is reentrant). A missing guest runner or a lock timeout/unavailable
condition yields `blocked`/`not_run` with the attempt evidence and an explicit
reason; no pass is fabricated.

## Stability / flake policy

C1 warning `B-POST-REBASE-REPRODUCTION-FLAKY` means a single run is not an
unconditional stability claim. `--repeat N` runs the benchmark N times
serially and records every attempt (`repeat_history`: per-attempt results
digest, exit code, status counts, verified count) in the evidence and summary.
The first attempt is canonical; differing repeat digests mark the run unstable
(exit 1) and add a limitation instead of hiding the flake.

## Hidden lane

`--hidden-root <private root>` consumes the C4 private hidden manifest
`<root>/hidden-manifest.json`
(`kind=phase8c_private_hidden_manifest`, opaque sha256 sample ids, `material`
with root-relative `binary_path`/`oracle_path`). Paths are resolved and must
stay inside the private root. `benchmark/phase8c/hidden-commitment.json` must
exist and match both the private manifest and the public manifest digest;
otherwise the lane is `not_run` (exit 2) and no aggregate is written. Hidden
execution uses the same repair/verifier/guest path but publishes only the
aggregate file.

## Offline artifact check

`python scripts/run_phase8c_benchmark.py --check-artifact` performs no sample
execution: it validates `benchmark/phase8c/results.json` through the C2
contract checker integration, re-derives aggregate counts, checks the manifest
digest/benchmark id/sample ids, verifies the evidence directory SHA256SUMS and
the hidden aggregate privacy/commitment consistency. Exit codes: 0 green,
1 violations, 2 unreadable/error.

## Reproduce

```bash
python scripts/run_phase8c_benchmark.py --repeat 2
python scripts/run_phase8c_benchmark.py --check-artifact
```

Limitations: evidence commits metadata/hashes only (raw binaries are not
duplicated); the runner is deterministic and offline (no AI provider, no
network, no wall clock - `generated_at` is inherited from the fixed manifest).
