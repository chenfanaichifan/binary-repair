# Gate 4 record — Route B formal

**Status: DRAFT / NOT RUN.** Observed evidence only; this is not a pass claim.
**Record owner:** M5. **M4 verifier:** blank. **Lead approval:** blank.
**JOIN-1:** not completed.

## Inputs observed on main

| Input | Observed value |
|---|---|
| P4 v3 `docs/handoffs/evidence/P4/` | checker PASS 26/26; `gate4-status=pass`, native `manifest-compare` 6/6; original `aa428157…8393`, patched `decdcdb8…954b` |
| P4 isolation | uid 1003, `CapEff=0`, `NoNewPrivs=1`, netns empty/egress blocked; wrapper `b232d60b…`, `gate4.conf` `a912e6b0…`, chain `b7ded700…`, raw revert/fingerprint present |
| P3A v7 | checker PASS 29/29; candidate `c4a159…`; V0/V1/V2/V3/V5 pass; V4 `unknown` |
| P3B v6 | checker PASS 25/25; candidate `208574ab…`; V2 16/16 pass; V3 6/6; V5 pass; V4 `unknown` |
| fresh real p2 | job `5c04833b…`; `p2_acceptance.py` exit 0, `synthetic=false`; verdict **inconclusive / solver_unknown / symbolic** |
| V4 | `not_run`/NOT VERIFIED; v12 accounting `sat=0, unsat=0, unknown=0, eval=1`; concrete worst-case bytes, not symbolic proof |

## Route B candidate decision — contract preserved

P3B v6 candidate `208574ab…` reuses the existing R-X PT_LOAD tail:
`extra_load_segment_count=0`, `same_program_header_count=true`, V2 16/16.
The older `63fcafa6…` candidate (2 added PT_LOAD) is superseded and must not be
used for V2/p2.

## P3A/P3B adapter observed (not a gate pass)

```text
Route A: V0/V1/V2/V3/V5 passed; V4 unknown
Route B: V0/V1/V2/V3/V5 passed; V4 unknown
```

## P3B worker log

```text
docs/handoffs/logs/P3B-v6-worker.txt
SHA-256 624ac02dbb38279f4f794e92568dbe01b2a2590623764fc732c80122920f1198
```

## Fresh p2 log

```text
docs/handoffs/logs/P2-v6-acceptance.txt
SHA-256 9682825572f4784702245a3fe4498e7fc7b00eb81db006a14e29bb63c9f29011
```

p2 exit 0 means the snapshot is complete/consistent; it is **not success**.

## V0–V5 formal gate table

| Gate | Result | Evidence |
|---|---|---|
| V0 identity | `not_run` | — |
| V1 structure | `not_run` | — |
| V2 interface | `not_run` | — |
| V3 behaviour | `not_run` | — |
| V4 symbolic | `not_run` | — |
| V5 reproducibility | `not_run` | — |

Gate 4 formal remains NOT RUN; the adapter rows are partial evidence, not the
formal gate.

## Signatures / witness

| Role | Name | Date | Observation |
|---|---|---|---|
| M5 Gate 4 record | M5 | 2026-10-31 | P4/P3A/P3B checker PASS; P3B v6 V2 16/16; fresh p2 exit 0 but verdict inconclusive; V4 unknown; no `gate4_pass`; M4/Lead blank |
| Independent witness | M2 | 2026-10-29 | earlier cross-check; witness only |
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
