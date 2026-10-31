# Gate 4 record — Route B formal

**Status: DRAFT / NOT RUN.** Observed evidence only; this is not a pass claim.
**Record owner:** M5. **M4 verifier:** blank. **Lead approval:** blank.
**JOIN-1:** not completed.

## Inputs observed on main

| Input | Observed value |
|---|---|
| P4 v3 `docs/handoffs/evidence/P4/` | checker PASS 26/26; `gate4-status=pass`, native `manifest-compare` 6/6; original `aa428157…8393`, patched `decdcdb8…954b` |
| P4 isolation | uid 1003, `CapEff=0`, `NoNewPrivs=1`, netns empty/egress blocked; wrapper `b232d60b…`, `gate4.conf` `a912e6b0…`, chain `b7ded700…`, raw revert/fingerprint present |
| P3A v7 | `dist/m5-evidence/P3A-routea-2026-10-31-v7.zip` SHA-256 `6f16a933…bf24e`; checker PASS 29/29; candidate `c4a159…`; V0/V1/V2/V3/V5 pass |
| P3A sums | `docs/handoffs/evidence/P3A/SHA256SUMS` LF; sha256 `fa3e16b0…d48f`; 26/26 |
| P3B v6 | `dist/m5-evidence/P3B-package-v6-2026-10-31.zip` SHA-256 `ca8e1e50…97b6`; checker PASS 25/25; candidate `208574ab…`; V2 16/16 pass; V3 6/6; V5 pass |
| P3B sums | `docs/handoffs/evidence/P3B/SHA256SUMS` LF; sha256 `fa098a38…5a13`; 22/22 |
| fresh real p2 | job `5c04833b…`; `p2_acceptance.py` exit 0, `synthetic=false`; verdict **inconclusive / solver_unknown / symbolic** |
| V4 | **PASS (model-level, bound 64)** per Lead ruling; **not** candidate-binary symbolic execution and **not** whole-program equivalence; no V4 evidence file is inside the P3B zip; Gate 4 formal still NOT RUN |

## Route B candidate decision — contract preserved

P3B v6 candidate `208574ab…` reuses the existing R-X PT_LOAD tail:
`extra_load_segment_count=0`, `same_program_header_count=true`, V2 16/16.
The older `63fcafa6…` candidate (2 added PT_LOAD) is superseded and must not be
used for V2/p2.

## V4 observed (Lead ruling, not a formal gate pass)

```text
V4 = PASS (model-level, bound 64)
  scope: bounded function-level z3 model
  NOT: candidate-binary symbolic execution
  NOT: whole-program equivalence
  NOT: overall MVP success
```

No V4 evidence file was added to the P3B zip; this is an external Lead ruling,
recorded for traceability. Gate 4 formal remains NOT RUN.

## P3A/P3B adapter observed (not a gate pass)

```text
Route A: V0/V1/V2/V3/V5 passed; V4 passed (model-level, bound 64)
Route B: V0/V1/V2/V3/V5 passed; V4 passed (model-level, bound 64)
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
| V4 symbolic | `passed (model-level, bound 64)` | Lead ruling; bounded function-level z3 model only; **not candidate-binary symbolic execution**, **not whole-program equivalence**; `gate4_pass` absent |
| V5 reproducibility | `not_run` | — |

Gate 4 formal remains NOT RUN; the adapter rows are partial evidence, not the
formal gate.

## Signatures / witness

| Role | Name | Date | Observation |
|---|---|---|---|
| M5 Gate 4 record | M5 | 2026-10-31 | P4/P3A/P3B checker PASS; P3B v6 V2 16/16; fresh p2 exit 0 but verdict inconclusive; V4 model-level PASS per Lead; no `gate4_pass`; M4/Lead blank |
| Independent witness | M2 | 2026-10-29 | earlier cross-check; witness only |
| M4 verifier | — | — | blank |
| Lead approval | — | — | blank |

## Boundaries

```text
gate4_pass: absent
Gate 4: DRAFT / NOT RUN
JOIN-1: not completed
Gate 5: BLOCKED (jobwrap gate5 + GATE5_SCRIPT_SHA256)
V4: model-level PASS (bound 64); formal gate NOT RUN
MVP: NOT COMPLETE
```


## Packaging correction

`SHA256SUMS` in both P3A v7 and P3B v6 was regenerated with LF (no CRLF).
The packages were rezipped; their `SHA256SUMS` now pass a standard
`shasum -a 256 -c` (P3B 25/25, P3A 29/29) as well as `check_handoff.py`.
The P3B/P2 worker logs were not changed by this repack.
