# 65 - expected_sha256 is the approved candidate hash

**Status:** fixed on `fix/expected-sha256-approved-candidate` (not merged).
**Scope:** identity binding only. Gate 3/4/5, V4 and fixture status are unchanged.

## Defect

`orchestration.evaluate_attempt()` passed `job.original_sha256` as
`expected_sha256`. A normal repair candidate differs from the original input,
so every real candidate was rejected as `hash_mismatch` before the V0-V5
evidence could be judged.

## Decision

`expected_sha256` means **approved candidate hash**, not original input hash.
The current approval does not bind a candidate hash, so orchestration must pass
`None` and persist `"expected_sha256": null`.

The V0/attempt-writer identity checks remain in place. The acceptance engine
still fails closed when a caller explicitly supplies an approved candidate hash
that differs from the candidate under test.

## Changes

- `app/services/orchestration.py`
  - `_run_context()` no longer returns the original hash.
  - `evaluate_attempt()` passes `expected_sha256=None`.
  - the per-attempt verdict payload stores `"expected_sha256": null`.
- `app/domain/acceptance.py`
  - docstring now says approved candidate hash, explicitly not the original.
- `tests/integration/test_orchestration.py`
  - replaced the candidate-vs-original mismatch test with:
    candidate != original + V0-V5 all passed -> `success_within_scope`.
- `tests/unit/test_acceptance.py`
  - renamed the explicit approved-candidate mismatch test; it still expects
    `hash_mismatch` / `inconclusive`.
- `docs_BinaryRepair/handoffs/01-member-1-obligation-interface.md`
  - corrected `expected_sha256` semantics and the "call with real hashes" rule.

## Verification

```text
python -m pytest tests/unit/test_acceptance.py -q       -> 29 passed
python -m pytest tests/integration/test_orchestration.py -q -> 6 passed
python -m pytest -q --ignore=tests/e2e
  -> 265 collected / 262 passed / 2 skipped / 1 failed
  -> only failure: tests/test_routeb_executor.py::test_static_routeb_bundle
     (Windows lacks readelf/objdump; assert 7 >= 8)
python -m pytest -q
  -> browser e2e hangs on this host; full suite not completed
```

## Not changed

- No Gate 3/4/5 status change.
- V4 remains `not_run`.
- No merge, no tag.
