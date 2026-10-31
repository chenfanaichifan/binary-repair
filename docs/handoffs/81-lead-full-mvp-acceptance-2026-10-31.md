# 81 — Full MVP acceptance with recorded limitations (2026-10-31)

**From:** Lead / M4 (same operator; role-separated, not human-independent)
**To:** M1, M5, M3, M4
**Date:** 2026-10-31 23:10 (Asia/Hong_Kong)
**Decision:** **MVP acceptance APPROVED with recorded limitations.** This authorizes
M1 to create the final MVP tag after merging records `79`/`80`/`81` and updating
BOARD. It is not an independent-human approval.

## 1. Gate status at acceptance

| Gate | Status | Basis |
|---|---|---|
| Gate 3 | CLOSED/APPROVED | signed record, unchanged |
| Gate 4 | PASS | strict unchanged round-trip; F2 p2 rerun waiver recorded (`75`) |
| Gate 5 Route A | PASS | record `51` signed; evidence re-hashed |
| Gate 5 Route B | PASS | record `80`; Gate5B zip `2f5fa9f8…8821`, probe `05d9a2cd…db82`, candidate `208574ab…6717` |
| Gate 6 / V4 | PASS (model-level, bounded 64) | V4 z3 model accepted; not a binary-level/whole-program proof |
| fixture | FROZEN (candidate scope) | record `78` |
| full suite | verifiable subset | 0 assertion failures; environment-only gaps (`capstone`/`elftools`/e2e) recorded |
| real p2 | Gate4 evidence accepted | F2 independent rerun waived in `75`; not a success claim |

## 2. Limitations recorded (not hidden)

1. **V4 is model-level**, bound 64, hand-coded guard model; it is not a
   binary-level symbolic execution or whole-program proof.
2. **Full suite is not fully green**: missing `capstone`/`elftools` modules and the
   browser e2e environment; no assertion failures observed.
3. **M4 and Lead are the same operator**; this is not independent two-person review.
4. **Gate 4 F2 independent p2 rerun was waived**; F1 accepted the verification-only
   JSON + M5-recorded exit 0.
5. Gate5B evidence omits a duplicate `original.elf`; original was verified against
   the frozen fixture. R2 uses runtime maps + independent ELF parse.

None of the above is a hidden pass; they are recorded scope limitations of this
acceptance.

## 3. Final tag authorization

M1 may create **one** final tag after merging records:

```text
mvp-2026-10-31
```

Target: the merge commit containing `docs/handoffs/79`, `80`, `81`, updated BOARD,
and the final main state. Do **not** reuse or rewrite
`mvp-integration-2026-10-31`; do not claim independent-human approval.

## 4. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| M4 verifier | M4 | 2026-10-31 | **PASS** — Gate 5 A/B and acceptance evidence checked |
| Lead approval | Lead | 2026-10-31 | **APPROVED — full MVP with recorded limitations**; same-person limitation |
| M1 | M1 | 2026-10-31 | pending merge + final tag |
