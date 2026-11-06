# 133 — M5 partial usage semantics merged into canonical

- Date: 2026-11-06
- Owner: Member 1 (canonical integration)
- Base: `canonical/m1-m5-integration` @ `dc3bcd3` (partial usage on `1938c31`)
  merged with `40a4153` (v3 no-input baseline `d56cbdc`/`40a4153`), so the 120
  contract gate is present and measured rather than assumed
- Source: M5 `9940c64` (`fix(m5): include attempt-bound usage and mark partial aggregates`)
- Scope: usage aggregation/controller rendering. No gate result change.

## 1. Aggregation

`aggregate_job_usage` keeps the wide canonical query:

```sql
WHERE job_id = ? OR attempt_id IN (
  SELECT a.id FROM attempts a JOIN runs r ON r.id = a.run_id
  WHERE r.job_id = ?
)
```

Semantics:

- no calls -> `None`
- calls but no real tokens -> `None`
- some NULL, some real -> sum real, `partial=True`
- all real -> sum, `partial=False`

A NULL row never erases real sibling usage and is never counted as zero.

## 2. Controller

`_ai_usage_for_job` returns `aggregate_job_usage` **unchanged**, including
`partial`. The legacy plan fallback returns:

```json
{"input_tokens": ..., "output_tokens": ..., "partial": false}
```

The fallback is complete by construction: it reads one stored plan record that
either has both counts or is not used at all.

## 3. Tests

- `tests/integration/test_assistant_plan.py` — partial and attempt-bound rows.
- `tests/integration/test_ai_usage_sources.py` — controller keeps
  `partial=True`, all-NULL remains `None`, plan fallback has `partial=False`.
- `tests/integration/test_contract_gaps.py` — plan fallback shape.

## 4. Gates re-run on the merged tree

The partial-usage commit first existed on the bare `1938c31` remote tip, which
does not carry the v3 no-input baseline; the canonical branch therefore merges
`40a4153` before this record is read. "The 120 gate is unchanged" is a measured
statement here, not an assumption. No fixture byte or contract rule is touched.

| Check | Command | Observed |
|---|---|---|
| CWE121 v2 hash + 120 contract gate | `pytest tests/test_fixture_contract.py tests/test_contracts.py tests/test_fixture_intake.py tests/test_v3_no_input_e2e.py` | **84 passed** |
| usage/controller suite | `pytest tests/integration/test_ai_usage_sources.py tests/integration/test_contract_gaps.py tests/integration/test_assistant_plan.py` | **19 passed** |
| full suite | `pytest --ignore=tests/e2e` | **449 passed / 2 skipped / 0 failed** |

The two skips are `tests/test_fixture_v3_manifest.py:141` and `:163`, both
`ELF execution requires Linux`; a skip is not a pass. The CWE121 v2 contract
hash `24bfe568…4e37` is reproduced by `test_fixture_contract.py`, and the
`v3 none` no-input contract/intake tests (`test_v3_none_*`,
`test_v2_rejects_input_mode_field`, the intake no-input cases) are present and
green. These gates are unchanged by this task: only `ai_usage` aggregation and
its tests move.

## 5. Constraints

CWE121 v2 hash and the 120 contract gate are unchanged. T8.3 blocked. No merge
to `main`, no tag, no live-success claim.
