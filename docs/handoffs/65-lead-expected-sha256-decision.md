# 65 — Lead decision: `expected_sha256` must bind the approved candidate, not the original input

**From:** Lead
**To:** M1 (job controller / acceptance owner), cc M3, M5, M4
**Date:** 2026-10-31 17:55 (Asia/Hong_Kong)
**Re:** M3 report "acceptance 的 `expected_sha256` 语义缺陷（hash_mismatch 必现）"
**Status:** defect **confirmed**; fix assigned to M1. No gate status change: Gate 3 closed;
Gate 4 `NOT RUN`; Gate 5 `BLOCKED`; Gate 6 `partial`; fixture `NOT FROZEN`.

## 1. Finding: confirmed

Reproduced with the pure acceptance function (all six required obligations `passed`,
candidate hash different from original):

```text
candidate = aaaa… (64)
original/expected = aa428157…8393
result = inconclusive / hash_mismatch
```

The source chain is exactly as M3 reports:

- `app/services/orchestration.py` `_run_context`: `"input_sha256": job["original_sha256"]`;
- `evaluate_attempt`: `expected_sha256=body.get("input_sha256")`;
- `app/domain/acceptance.py` step 6: `candidate_sha256 != expected_sha256` → `HASH_MISMATCH`.

The approval record binds the **original input hash** and contract scope
(`jobs.approve_contract` validates `input_sha256 == job.original_sha256`; `scope_sha256` is the
contract). It does **not** bind a candidate, because the candidate does not exist at F1
approval time. Therefore any candidate that actually repairs the binary differs from the
approved input hash and can never reach `success_within_scope`. The current success tests hide
this by passing `candidate_sha256 = record.original_sha256`; the mismatch test encodes the same
wrong semantics.

## 2. Decision

**`expected_sha256` means "hash of the approved candidate artifact", not "hash of the original
input".** The original hash is an *identity input* only (V0/attempt writer checks it); it must
never be used as the candidate equality target.

For the current MVP lifecycle there is **no candidate-approval binding**: approval covers the
job's original bytes + contract/scope, and the candidate is generated later. So:

1. `evaluate_attempt` must **not** pass `job["original_sha256"]` as `expected_sha256`. Pass
   `None` (or, if a future candidate-approval record exists, that approved candidate hash).
2. Step 6 in `decide_attempt_outcome` stays in place for the future/explicit case, but its
   contract is clarified: it compares the validated candidate to an **approved candidate hash**
   only when that hash exists. No current caller may pass the original input hash.
3. Candidate identity is enforced where it already belongs: V0/attempt-writer checks the
   declared candidate against the actual candidate bytes and the job original; artifact
   registration binds evidence to the attempt. Do not weaken those checks.
4. Reporting payload must stop labelling the original hash as `expected_sha256`; record it as
   `original_sha256` (or keep `input_sha256` as a distinct input field) so reports do not imply
   a candidate approval that never happened.
5. No "success if candidate == original" behaviour may remain; a real repair candidate must be
   able to pass when all required evidence is present.

## 3. Required changes (M1)

- `app/services/orchestration.py`:
  - `_run_context`: do not supply original hash as the candidate expectation; keep it as
    `input_sha256` for reporting/identity only.
  - `evaluate_attempt`: call `decide_attempt_outcome(..., expected_sha256=None)` in the current
    flow (or `approved_candidate_sha256` when a genuine candidate approval exists); remove the
    mistaken `body.get("input_sha256")` argument and payload label.
- `app/domain/acceptance.py`: update the `expected_sha256` docstring to "approved candidate hash";
  keep step 6 fail-closed for an explicitly supplied approved candidate hash.
- `app/services/jobs.py` / approval contract: no need to bind candidate now; if a future
  candidate-approval flow is added, it must be a separate explicit binding.
- Tests:
  - Replace `tests/integration/test_orchestration.py::test_candidate_hash_mismatch_is_inconclusive`
    (which encodes candidate-vs-original and would forbid real repairs) with a **real-repair
    regression**: all V0–V5 passed, `candidate_sha256 != record.original_sha256`, valid scope →
    `success_within_scope`.
  - Keep/rename a unit test in `tests/unit/test_acceptance.py` for an explicit **approved
    candidate hash mismatch** → `inconclusive/hash_mismatch` (this still proves fail-closed
    behaviour when a candidate approval exists).
  - Add an integration/unit assertion that an all-passed attempt with a different candidate hash
    can reach success; do not use `candidate == original` as the only success case.
- Update `docs_BinaryRepair/handoffs/01-member-1-obligation-interface.md` §2 `expected_sha256`
  wording and the acceptance docstring so the API cannot be re-misread.
- Run: acceptance unit suite, orchestration integration tests, and the relevant full suite;
  record observed results.

M1 owns the change; M3/M5 must not edit `app/domain/acceptance.py` or its tests.

## 4. Boundaries

- This defect does **not** change Gate 4/5/6 statuses or V4 status. V4 remains `not_run`/
  NOT VERIFIED under Standard B (`docs/handoffs/62`); this fix is a prerequisite for a future
  real `success_within_scope`, not a gate pass.
- Do not "fix" by passing the candidate hash as both candidate and expected (that would make the
  check vacuous). Do not remove step 6; make its semantics correct.
- No waiver, no fixture freeze, no merge/tag action.

## 5. Signature

| Role | Name | Date | Signature |
|---|---|---|---|
| Lead (semantics decision) | Lead | 2026-10-31 | expected_sha256 = approved **candidate** hash; current flow must not pass original; M1 to fix/tests |
| M1 (implementation) | M1 | — | pending |
| M3/M5 (no core edits) | — | — | pending acknowledgement |
