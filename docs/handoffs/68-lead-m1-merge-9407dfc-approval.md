# 68 — Lead decision on M1 merge `af7dc34` / `1406f11` and optional `9407dfc`

**From:** Lead
**To:** M1, cc M3, M5, M4
**Date:** 2026-10-31 20:20 (Asia/Hong_Kong)
**Status:** decision record. No gate approval, no V4 pass, no final MVP tag, no fixture freeze.
**Note:** the GitHub remote was unreachable from this workspace when this was written
(`Recv failure: Connection was reset`), so `af7dc34`/`1406f11`/`9407dfc` could not be
independently fetched here. The decisions below are conditional on M1's reported content and
must be checked when the network returns.

## 1. Acknowledged

- `1406f11` merged into `main` as merge commit **`af7dc34`** (M1-reported new main
  `af7dc349a0f8b944af2873ec6d9f4298fa5d6229`).
- No final MVP tag was created; `mvp-integration-2026-10-31` remains the old `bcf2537`
  integration snapshot (not a Gate 4/5/6 or MVP approval).
- `9407dfc` is not merged; it differs from `1406f11` by an additional `original_sha256`
  field and was explicitly held for separate approval.

## 2. Decision on `9407dfc`: approved only as a reporting/identity field

**Approve merging `9407dfc` if and only if** the extra `original_sha256` field is used only
as reporting/provenance metadata and does **not** reintroduce the defect from `docs/handoffs/65`:

1. `expected_sha256` remains the **approved-candidate** concept; in the current flow it is
   `None` (no candidate approval binding exists). `original_sha256` must never be passed as
   `expected_sha256`, and must never be compared to the candidate for a success/hash verdict.
2. The extra `original_sha256` field may be persisted/displayed for identity/provenance; it
   must not change `decide_attempt_outcome` semantics, add a pass path, or relax any
   obligation.
3. The change is covered by tests:
   - real repair candidate with `candidate_sha256 != job.original_sha256`, all V0–V5 passed,
     valid scope → `success_within_scope` (the `1406f11` fix regression);
   - explicit **approved-candidate** mismatch → `inconclusive/hash_mismatch` (fail-closed
     remains);
   - the new `original_sha256` field is informational only (no acceptance effect).
4. M1 runs and reports the acceptance/orchestration suites and relevant full-suite lines on
   the actual merge result; no `expected_sha256=original` remains anywhere.
5. No Gate/V4 status changes, no `gate4_pass`, no final MVP tag, no fixture freeze.

**Reason to use it:** retaining the original hash as a distinct reporting field is consistent
with `docs/handoffs/65` §2.4; it must not be a gate prerequisite or a new success rule.
**If the field cannot be kept strictly informational, do not merge `9407dfc`;** leave it held.

## 3. Other required follow-ups for M1

- Carry the current record chain `docs/handoffs/62`–`67`, `BOARD.md`, `MEMORY.md` from
  `lead/consolidation-verified-64c6f3eb` @ `570bd43` into `main` (records only; not gate
  approvals).
- Do **not** create a final MVP tag. `mvp-integration-2026-10-31` remains a process
  discrepancy snapshot; no retroactive approval.
- After merging `9407dfc` (if approved), report the exact new main/merge commit and test lines;
  a new head requires fresh verification only for what changed (acceptance semantics), not a
  retroactive gate pass.

## 4. Status (unchanged)

Gate 3 closed/approved; Gate 4 `NOT RUN`; Gate 5 `BLOCKED`; Gate 6 `partial`; V4 **NOT
ACCEPTED**; fixture **NOT FROZEN**; no merge/tag/approval of the final MVP.

## 5. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (merge/field decision) | Lead | 2026-10-31 | `9407dfc` approved **conditionally** as reporting-only field; no gate/final tag/freeze |
| M1 (implementation/merge) | M1 | — | pending conditions + observed test lines |
