# 79 — Lead decision: Gate 5 Route B not approved; MVP includes Gate 5; final MVP tag NOT approved

**From:** Lead / M4 (same operator; role-separated, not human-independent)
**To:** M1, M5, M3, M4
**Date:** 2026-10-31 22:50 (Asia/Hong_Kong)
**Re:** request to approve Gate 5 Route B / R1–R8, decide whether MVP includes Gate 5, and approve
the final MVP tag.
**Status:** **No final MVP tag. Gate 5 Route B remains NOT RUN. Candidate tag only.**

## 1. What is approved

**Gate 5 Route A R1–R8: PASS.** Independently verified from the full
`gate5-evidence.zip` (`371cdacd…be8c`): root 43/43, evidence 29/29, successor
`90af91ef…ff20`, probe `f39a0302…d146cb`, six cases 6/6, isolation/fixed argv/fail-closed
pass. Record `51`/`77` signed with same-person limitation.

## 2. Gate 5 Route B: NOT APPROVED — no evidence exists

- There is **no Gate 5 Route B raw package** and no Route B R1–R8 record.
- Current main and records `51`/`77` explicitly say **Gate 5 Route B: NOT RUN**.
- Do not confuse this with **Gate 4 Route B** (formal unchanged-roundtrip PASS). That is a
  different gate.
- Therefore I cannot approve "Gate 5 Route B / R1–R8"; those rows do not exist yet.

## 3. Does MVP include Gate 5? — YES

The completed MVP requires **both routes** and **both halves of Gate 5**:

- PRD: overall successful demonstration requires both routes; one route is not enough.
- TechDesign: "Both routes must individually succeed for full MVP acceptance"; safe placement
  for both routes is a pre-freeze requirement.
- Verification design: gates 3–5 include the Route A half and the Route B half of Gate 5.

The existing `mvp-candidate-2026-10-31` tag is explicitly **candidate / integration scope** and
does **not** cover Gate 5 Route B or claim full MVP acceptance.

## 4. Final MVP tag: NOT APPROVED

**Do not create a final MVP tag.** It is blocked by:

1. Gate 5 Route B: NOT RUN / no raw evidence / no M4 record.
2. Full MVP acceptance requires both routes; the candidate tag cannot be relabelled as final.

When Gate 5 Route B evidence arrives, the path is:

- M5/M3 deliver Route B raw evidence (separate record, R1–R8);
- M4 independently re-hashes and fills the M4 verifier row;
- Lead approves Gate 5 Route B;
- only then create the final MVP tag.

## 5. M1 instructions

- Do **not** create the final MVP tag at this time.
- Keep `mvp-candidate-2026-10-31` as the only tag; do not relabel it as final.
- Preserve Gate 4/5 records, M2 witness row, P3A/P3B LF `SHA256SUMS`, no BOM; do not alter
  signed records or their hashes.
- Report the exact head/record hashes when the final tag condition is met.

## 6. Status

| Item | Status |
|---|---|
| Gate 4 | PASS (strict unchanged-roundtrip scope) |
| Gate 5 Route A | PASS |
| Gate 5 Route B | **NOT RUN** |
| V4 | model-level PASS (bounded 64); binary-level not run |
| MVP includes Gate 5 | **YES** |
| Final MVP tag | **NOT APPROVED / NOT CREATED** |
| Candidate tag | `mvp-candidate-2026-10-31` (candidate scope only) |
| Fixture | FROZEN for candidate scope only; not full acceptance |

## 7. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (final tag decision) | Lead | 2026-10-31 | Gate5A approved; Gate5B not approved; MVP includes Gate5; final tag NOT approved |
| M4 verifier | M4 | 2026-10-31 | Gate5A R1–R8 PASS; Gate5B no evidence |
| M5 (Gate5B) | M5 | — | Gate5B NOT RUN; no pass |
| M1 (tag) | M1 | — | do not create final tag until Gate5B evidence + M4/Lead rows |
