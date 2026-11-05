# model_calls: correcting my own record, and wiring the aggregate

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Suite: `380 passed / 3 skipped / 1 failed` (host has no `readelf`/`objdump`)

## The correction

I previously wrote "the v2 schema has no `model_calls` table, only a comment". That
was wrong, and the cause is worth recording: I checked `004_assistant.sql` and the
header of `schema.sql`, saw no table, and did not open `002_ai_tables.sql`.

`002_ai_tables.sql:79` creates it with 14 columns. `007` adds
`assistant_plan_id`, `008` adds `job_id` and `plan_id`. A fresh `init_db` produces

```
id, attempt_id, route, model_requested, model_returned, status,
prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd,
latency_ms, request_id, usage_json, created_at,
assistant_plan_id, job_id, plan_id
```

17 columns, verified by creating a throwaway database, not by reading the files.

## Why `schema.sql` looked like a second path

`schema.sql` is the v1 baseline: `jobs` + `artifacts` only, plus a header saying the
AI tables come from `002`. `init_db` always applies the baseline and then every
migration, so there is one path, not two. A database that contains only what
`schema.sql` creates is not a state the code produces.

`tests/test_db_v2.py` now asserts the usage columns exist after `init_db`
(`prompt_tokens`, `completion_tokens`, `total_tokens`, `usage_json`,
`assistant_plan_id`, `job_id`, `plan_id`). If anyone moves `model_calls` out of the
migration chain, the test fails instead of T8.2 discovering it at write time.

## Wiring `aggregate_usage`

`ai_usage` used to read `assistant_plans.usage_json` only, which is why it was
empty for jobs that never generated a plan. Now:

1. `app/services/model_calls.py::aggregate_job_usage(job_id)` sums rows bound by
   `model_calls.job_id` **or** by an attempt belonging to that job's runs. The
   `OR` cannot double count a row.
2. Any row with a missing count makes the result `None`. A partial record is
   unavailable, not zero.
3. If the job has model_calls rows at all, that answer is authoritative even when
   it is `None` - the controller does not silently fall back to the plan and mix
   two sources under one label.
4. Jobs that predate `model_calls` still fall back to the plan, which is the only
   real record they have.

`tests/integration/test_ai_usage_sources.py` covers: both bindings counted,
partial row -> `None`, plan-only fallback, and no-source -> `None`.

## Merge note

M5 `c50ca04` renumbered its assistant migrations to `007`/`008` to avoid this
branch's `006_obligation_scope.sql`. The chain is `002, 003, 004, 006, 007, 008`;
version 5 is unused on purpose, and `test_db_v2` pins `[1, 2, 3, 4, 6, 7, 8]` with
that reason in the test.

## Ledger answers accepted

- `scope`: V1/V2 = `binary`, agreed. Screening output will be a separate `source`
  field, not a second scope axis; no code change needed (the mapping already
  matches).
- `attempt_no` / `status`: keep the API names. No change; the DB columns
  `sequence` / `phase` stay internal.

## Open

- Push still needs a token.
- The `readelf`/`objdump` failure is environmental.
