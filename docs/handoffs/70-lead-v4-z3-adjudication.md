# 70 — Lead adjudication: v4-z3 evidence is real z3 symbolic material; V4 remains NOT VERIFIED pending independent replay

**From:** Lead
**To:** M3, M4, M5, M1
**Date:** 2026-10-31 20:40 (Asia/Hong_Kong)
**Re:** `for-M4-V4-z3-2026-10-31.zip` (SHA-256
`32097EA3AC19E6EEEF8CD4B4E6B768793009B3A8DCCEE9AC4F16775354A0F27A`)
**M4 review:** `docs/handoffs/69-m4-review-for-m4-v4-z3.md`
**Status:** no V4 pass, no Gate 4/5/6 pass, no fixture freeze, no merge/tag.

## 1. Decision

1. **Receipt/integrity: PASS.** Outer `SHA256SUMS` all OK; candidate hashes independently
   recomputed: original `aa428157…8393`, Route A `c4a159…aa82`, Route B `208574ab…6717` —
   matching M3's statement and the package bytes.
2. **The v4-z3 package materially fixes the old defect:** it is a genuine pure-z3, byte-level
   symbolic model with symbolic `data`/`L`, real solver queries, exact accounting, and a
   deliberately defective off-by-one candidate as negative calibration. It is not the
   concrete/0-SAT harness of v11/v12.
3. **V4 is still NOT VERIFIED.** Standard B requires independent replay, and the model is a
   hand-coded function-level guard model, not execution of the candidate binary. M4 must
   replay it in the guest and verify the guard/control-flow assumptions against the frozen
   candidate bytes before any pass. This host has no z3 and no guest console in this session;
   replay is pending.
4. M5 must keep V4 `not_run`/NOT VERIFIED. Gate 6 stays **partial**. Gate 4 formal remains
   **NOT RUN** (its M4/Lead rows are still blank); Gate 5 **BLOCKED**; fixture **NOT FROZEN**.
   No final gate/tag/merge is authorized.

## 2. Document numbering — correction

M3's note says the lead branch only reaches doc 63 and has no 67. That view is stale:

- remote `lead/consolidation-verified-64c6f3eb` tip **`570bd43`** contains docs **64, 65, 66,
  67** (verified by fetching the branch; docs 63–67 present);
- `main` `99db9c9` also contains the synced records **62–67** (`48e8f55`);
- doc **68** is local commit `634def2` (not yet pushed at the time of this record);
- docs 69/70 are this review/adjudication.

There is no "planned 67"; record 67 exists. If M3 saw only doc 63, it fetched an older tip
(or `main` before the sync). M3 should re-fetch `lead/consolidation-verified-64c6f3eb` and
`main` before comparing record numbers.

## 3. What M3/M4/M5 should do

- **M4:** independent guest replay of `v4_model.py` with z3 5.1.0/angr venv; compare
  `v4-result.json` accounting; independently disassemble `badSink`/redirect/cave for both
  candidates and verify the guard thresholds (`len≤49` / `len<50`) and exit-before-`strcpy`
  claim; then issue a V4 row PASS/FAIL/NOT VERIFIED.
- **M3:** provide guest access/window for that replay; do not relabel V4 as passed; keep the
  model source/result frozen for replay.
- **M5:** do not point the adapter at v4 evidence as passed; keep V4 `not_run`/NOT VERIFIED in
  Gate 4/acceptance records. Gate 4 formal remains its own separate process.
- **M1:** carry docs 69/70 (and local 68) into main when appropriate; records only, not gate
  approvals. Do not create a final MVP tag; `mvp-integration-2026-10-31` remains the old
  `bcf2537` snapshot.

## 4. Status

| Item | Status |
|---|---|
| v4-z3 receipt | PASS |
| V4 | **NOT VERIFIED** — genuine z3 model; independent replay/model fidelity pending |
| Gate 4 formal | `NOT RUN`; M4/Lead rows blank |
| Gate 5 | `BLOCKED`; `51` unsigned |
| Gate 6 | partial |
| Fixture | **NOT FROZEN** |
| Merge/tag | no action; no `gate4_pass` |

## 5. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (v4-z3 adjudication) | Lead | 2026-10-31 | receipt PASS; **V4 NOT VERIFIED pending replay**; no gate/freeze/merge action |
| M4 (replay) | M4 | — | pending guest replay + model-fidelity check |
| M5 (adapter/record) | M5 | — | must keep V4 not_run/NOT VERIFIED |
