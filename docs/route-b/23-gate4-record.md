# Gate 4 record — Route B formal

**Status: DRAFT / NOT RUN.** Observed evidence only; this is not a pass claim.
**Record owner:** M5. **M4 verifier:** blank. **Lead approval:** blank.
**JOIN-1:** not completed.

## Inputs observed on main `d804474`

| Input | Observed value |
|---|---|
| P4 v3 `docs/handoffs/evidence/P4/` | checker PASS 26/26; `gate4-status=pass`, native `manifest-compare` 6/6; original `aa428157…8393`, patched `decdcdb8…954b` |
| P4 isolation | uid 1003, `CapEff=0`, `NoNewPrivs=1`, netns empty/egress blocked; wrapper `b232d60b…`; `gate4.conf` `a912e6b0…`; chain manifest `b7ded700…`; raw revert/fingerprint present |
| P3A v6 | checker PASS 26/26; candidate `c4a159…`; V0/V1/V3 pass; V2/V4/V5 `not_run` |
| P3B v5 | checker PASS 22/22; candidate `63fcafa6…`; V0/V1/V3/V5 pass; V2/V4 `not_run` |
| P2-real jobs | job1 `e2fe0f46…`: A/B `inconclusive` (V2 `not_run`); job2 `8b0f2856…`: A `inconclusive` (V4 `not_run`), B `rejected` (V2 failed, `extra_load_segments_within_contract`) |
| real p2 | `p2_acceptance.py` exit 0, `synthetic=false`; verdict is **not success** |
| V4 | `not_run` / NOT VERIFIED (v12 raw accounting: concrete bytes; `sat=0, unsat=0, unknown=0, eval=1`; Standard B not satisfied) |

## P3A/P3B adapter observed (not a gate pass)

```text
Route A: V0/V1/V3 passed; V2/V4/V5 not_run
Route B: V0/V1/V3/V5 passed; V2/V4 not_run
```

The newer v6 candidate `208574ab` (V2 fixed) and its fresh p2 are **not on this
main baseline**; they must be treated as a separate package/record, not folded
into this row.

Worker log (locatable/verifiable):

```text
docs/handoffs/logs/P3B-v3-worker-rerun-2026-10-29.log
SHA-256 f1c7c6dc79f2a34e42ae0864b8568d8ef90bf5c4ca07e7d9d57a752646122a14
```

Observation only; no gate pass.

## V0–V5

| Gate | Result | Evidence |
|---|---|---|
| V0 identity | `not_run` | — |
| V1 structure | `not_run` | — |
| V2 interface | `not_run` | — |
| V3 behaviour | `not_run` | — |
| V4 symbolic | `not_run` | — |
| V5 reproducibility | `not_run` | — |

Gate 4 formal remains NOT RUN: the table is for the formal gate record, not a
summary of partial adapter rows.

## Signatures / witness

| Role | Name | Date | Observation |
|---|---|---|---|
| M5 Gate 4 record | M5 | 2026-10-31 | Checker/isolation/P2-real observed; P4 v3 complete; V4 `not_run`; no `gate4_pass`; M4/Lead rows blank |
| Independent witness | M2 | 2026-10-29 | P3A/P3B/P4 checker PASS on `for-M5-v5`; witness only |
| M4 verifier | — | — | blank |
| Lead approval | — | — | blank |

## Boundaries

```text
gate4_pass: absent
Gate 4: DRAFT / NOT RUN
JOIN-1: not completed
Gate 5: BLOCKED (jobwrap gate5 + GATE5_SCRIPT_SHA256)
V4: NOT VERIFIED
MVP: NOT COMPLETE
```

No row above is a gate pass. P2 exit 0 means the snapshot is consistent, not
that a repair succeeded. V4 is not to be pointed at v4 evidence as `passed`.
