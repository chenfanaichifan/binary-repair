# 62 — M5 consume v9: supplements + fresh real p2

**Source:** M3 `43-m5-consume-response-2026-10-31.md`
**Evidence head:** `origin/member-3-route-a` `9b0fa23505d646e0f6daae91f1c5920e6eec61f2`
**No success / no gate4_pass.**

## Checker

```text
P3A v7 evidence: PASS 29/29, sums 2580c232…5ec0
P3B v6 evidence: PASS 25/25, sums df58f968…91ba
P4 v3:           PASS 26/26, sums e4b81b34…6c5e
```

## Adapter changes

- Route A adapter reads `v2-routea-supplement.json` and
  `v5-routea-supplement.json`; validates candidate identity; registers each
  supplement as evidence.
- Route B adapter reads `v2-routeb-fixed.json`; validates candidate identity;
  registers it as V2 evidence.
- Missing/mismatched supplements stay `not_run` or fail closed; V4 remains
  `not_run` in all cases.

Tests:

```text
tests/integration/test_supplement_mapping.py  2 passed
p2 + writer + supplements                      13 passed
```

## Fresh real p2

Job `d62287af76d5441dbbe83c4e6ce1bd1c` (candidate A `c4a159…`, B `208574ab…`):

```text
Route A: V0/V1/V2/V3/V5 passed; V4 not_run
Route B: V0/V1/V2/V3/V5 passed; V4 not_run
p2_acceptance.py: exit 0, synthetic=false
verdict: inconclusive / required_check_not_run / route_a V4 symbolic not_run
```

This is a fresh p2, not the old `63fcafa6` job1/job2.

## Remaining blockers

```text
V4 bounded symbolic: not_run for both routes
P4: execution evidence complete; Gate 4 acceptance NOT RUN
Gate 5: BLOCKED (no jobwrap gate5 + no GATE5_SCRIPT_SHA256)
MVP: NOT COMPLETE
```

Gate 4 record may record observed values only; no M4/Lead signature and no
gate4_pass.


## v11 addendum: P2-real V4 evidence

v11 adds `P2-real/v4/v4-evidence.json` and runners. M5 adapter accepts an
explicit `--v4-evidence` path:

- candidate-matching valid/free runs are required;
- the result is recorded as `unknown` (detail: self-verified, Lead adjudication
  pending), **not passed**;
- counterexample => failed; timeout => unknown; missing mismatch => not_run.

Fresh real p2 (job `22b49d494fbb4b3784d9adcf05401261`):

```text
Route A/B: V0/V1/V2/V3/V5 passed; V4 unknown
p2 exit 0, synthetic=false
verdict: inconclusive / solver_unknown / symbolic
```

Logs: `delivery/M5-v11-adapter-worker.log`,
`delivery/M5-v11-real-p2.log`.

This preserves the rule: a single-agent V4 self-check is evidence, not a Lead
adjudication and not `success_within_scope`.
