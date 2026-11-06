# 133 — M5 partial usage semantics merged into canonical

- Date: 2026-11-06
- Owner: Member 1 (canonical integration)
- Base: `canonical/m1-m5-integration` @ `1938c31`
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

```
canonical full suite: 410 passed / 2 skipped / 0 failed
```

## 4. Constraints

CWE121 v2 hash and the 120 contract gate are unchanged. T8.3 blocked. No merge
to `main`, no tag, no live-success claim.
