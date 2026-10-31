# 75 — Lead Gate 4 approval with maximum relaxation (F2 waiver), head `a69638ae`

**From:** Lead / M4 (same operator; role-separated, not human-independent)
**To:** M5, M1, M3, M4
**Date:** 2026-10-31 22:10 (Asia/Hong_Kong)
**Head:** `main` `a69638ae951ba57499c8a5d0687b1be5ed507dac`
**Gate 4 record:** `docs/route-b/23-gate4-record.md` at hash
`E9D91CA16248378F187BD7F58F94BB3551AB2407BEA212FBA75B80C4A357FB2B`
**Decision:** **Gate 4 formal accepted as PASS with an explicit Lead waiver of the F2
independent p2 re-run.** This is the maximum relaxation I will authorize; the waiver is recorded,
not hidden.

## 1. Evidence accepted

- P4: checker PASS 26/26; own SHA256SUMS 26/26; `gate4=pass`; native six-case 6/6; original
  `aa428157…8393`; patched/round-trip `decdcdb8…954b`; isolation uid 1003/CapEff=0/
  NoNewPrivs=1/egress blocked; snapshot/chain/revert present.
- P3A: LF `SHA256SUMS`, blob `fa3e16b0…d48f`, 26/26, checker PASS; candidate `c4a159…aa82`.
- P3B: LF `SHA256SUMS`, blob `fa098a38…5a13`, 22/22, checker PASS; candidate `208574ab…6717`;
  V2 16/16.
- P3A/P3B dist zip hashes match the Gate 4 record (`6F16A933…F24E`, `CA8E1E50…97B6`).
- p2: real job `5c04833b…`, `synthetic=false`, `phase=finished`, both routes have six
  obligations; M5 recorded `p2_acceptance.py` exit 0; verdict is
  `inconclusive/solver_unknown/symbolic` (pipeline honesty, not success).
- V4: model-level PASS (external ruling); not a Gate 4 formal criterion and not a binary-level
  proof.

## 2. Waiver recorded

Checklist `docs/handoffs/42` §3-F asks M4 to re-run p2 (F2) and F1 expects a
`P2 ACCEPTANCE PASSED` line. M4 could not re-run: no controller at `:8000`/`:8801` and no
job data dir in this checkout. I **accept the recorded p2 evidence and waive F2** for this Gate 4
decision:

- F1 accepted as the verification-only JSON summary + M5's recorded exit 0 (the verification-only
  mode does not print the pipeline PASS line); limitation noted.
- F2 **waived** by Lead; no claim that M4 independently re-ran p2.
- This waiver is specific to this head (`a69638ae`) and this Gate 4 decision; it does not become a
  precedent for Gate 5 or future heads.

## 3. Required record updates (M5/M1)

M5/M1 may update `docs/route-b/23-gate4-record.md` as follows (only these changes):

1. Status: **PASS** for Gate 4 formal; add `gate4_pass: true` and the new record hash.
2. M4 verifier row: signed by M4, with same-person limitation annotation.
3. Lead approval row: signed by Lead, with same-person limitation annotation; cite this record
   (`75`) and the F2 waiver.
4. Keep the existing M5 row; keep V4 model-level scope wording; no binary-level/whole-program
   claim.
5. Record hash pinned in BOARD and in the PR/merge message.

No final MVP tag, no Gate 5 claim, no fixture freeze from this decision.

## 4. Scope / status after approval

| Item | Status |
|---|---|
| Gate 4 formal (unchanged round trip) | **PASS** with F2 waiver; scope limited to Gate 4 evidence |
| V0–V5 adapter table | still partial/not_run except V4 model-level; not a Gate 4 formal condition |
| Gate 5 | **BLOCKED**; `51` unsigned |
| Gate 6 | V4 model-level PASS; status separate |
| Fixture | **NOT FROZEN** |
| MVP | **NOT COMPLETE** |
| Final tag | none; `mvp-integration-2026-10-31` remains old `bcf2537` |

## 5. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (Gate 4 approval) | Lead | 2026-10-31 | **APPROVED — Gate 4 formal PASS; F2 waiver recorded**; same-person limitation |
| M4 verifier | M4 | 2026-10-31 | **PASS** based on `docs/handoffs/74` evidence; F2 waived by Lead; same-person limitation |
| M5 Gate 4 record | M5 | 2026-10-31 | record updates pending; existing M5 row stands |
| M1 merge/main | M1 | 2026-10-31 | carry record only; no final tag |
