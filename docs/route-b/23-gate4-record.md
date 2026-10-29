# Gate 4 record — Route B formal

**Status: DRAFT / NOT RUN.** This is a record skeleton, not a pass claim.

## Inputs

| Input | Required | Observed |
|---|---|---|
| P4 package `427dd71d…` | yes | received; checker PASS 15/15; native `manifest-compare.json` 6/6; **incomplete** (missing original/candidate ELF, before/after, snapshot/chain/timestamp, raw revert, refreshed harness manifest; `hashes.json.original_sha256=null`; harness/isolation contradiction) |
| P3B v3 `72d789c6…` | yes | checker PASS 18/18; candidate `63fcafa6…`; source `a2e4ff8f…`; jobwrap exit 0; audit pass; V3 6/6 |
| real p2 exit 0 | yes | not run |
| M4 verifier | yes | blank |
| Lead approval | yes | blank |

## P3B adapter observed (not a gate pass)

```text
V0 passed; V1 passed; V2 not_run; V3 passed; V4 not_run; V5 passed
outcome: inconclusive
reason: required_check_not_run
failing_obligation: interface
```

P3B v3 is structurally accepted; V2/V4 remain not_run, so this is not success.

## V0–V5

| Gate | Result | Evidence |
|---|---|---|
| V0 identity | `not_run` | — |
| V1 structure | `not_run` | — |
| V2 interface | `not_run` | — |
| V3 behaviour | `not_run` | — |
| V4 symbolic | `not_run` | — |
| V5 reproducibility | `not_run` | — |

## Signatures / witness

| Role | Name | Date | Observation |
|---|---|---|---|
| Independent witness | M5 | 2026-10-29 | P3A v4 checker PASS/hash; P3B v3 checker PASS (V0/V1/V3/V5, V2/V4 not_run); P4 checker PASS, native manifest 6/6 but incomplete; Gate5 blocked; witness only, not a gate pass |
| Independent witness | M2 | 2026-10-29 | Cross-person rerun on `for-M5-v5` with main checker `caeffc2e…`: P3A v4 PASS 25/25 (`d9c33b42…`); P3B v3 PASS 18/18 (`8bec86e0…`, candidate `63fcafa6…`, jobwrap exit 0/audit pass, source `a2e4ff8f…`); P4 PASS 15/15 (`5c7ab9aa…`, native manifest 6/6 but incomplete); Gate5 A blocked 1/1; witness only, no gate pass; commands in `docs/handoffs/49-m2-independent-witness.md` |
| M5 Gate 4 record | — | — | wait for real p2 exit 0 |
| M4 verifier | — | — | blank |
| Lead approval | — | — | blank |

Do not fill any row from a checker-only observation, synthetic p2, static bundle,
or verbal approval. P4/P3B/Gate5 remain NOT RUN.

## Lead sign-off observed-values section (D1–D6)

```text
P4 received: 427dd71d…, checker PASS, 15/15, sums 5c7ab9aa…
native manifest-compare: gate4_pass=true, 6/6 same,
  original aa428157…8393, patched decdcdb8…954b
derived cases: runner_native=false, derived_from=manifest-compare.json
MISSING: original.elf, candidate/roundtrip.elf, before/after,
  snapshot/chain/timestamp, raw revert, refreshed harness manifest;
  hashes.json.original_sha256=null;
  harness-manifest contradicts isolation (b037 vs b232; f240 vs a912)
Gate 4 status: DRAFT / NOT RUN (no pass)
```

The D6 permission is to record observed values only. No `gate4_pass` is written;
M4 verifier and Lead approval remain blank.
