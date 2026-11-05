# M1: `ai_usage.partial` pass-through and the helper tests

- Date: 2026-11-05
- Owner: M1 (host backend)
- Boundary: T8.3 stays blocked; no merge to `main`, no tag, no live-success claim

## Change

`app/controller_api.py::_ai_usage_for_job`

- Return type is now `dict[str, Any] | None`. It was `dict[str, int] | None`,
  which was already wrong once the aggregate grew a boolean flag.
- The authoritative branch returns `aggregate_job_usage(...)` untouched, so
  `partial` is passed through rather than reconstructed. The query behind it is
  still the wide one — `job_id = ? OR attempt_id IN (...)` — and was not
  narrowed to `job_id` only.
- The plan fallback now returns
  `{input_tokens, output_tokens, partial: False}`.

## Pinned semantics

| Situation | `input_tokens` / `output_tokens` | `partial` |
|---|---|---|
| every recorded call has both counts | sum of all calls | `False` |
| some calls have a NULL count | sum of the calls that do | `True` |
| every call has a NULL count | — (whole value is `null`) | — |
| no `model_calls` rows, plan has both counts | the plan's counts | `False` |
| no `model_calls` rows, plan missing a count | — (whole value is `null`) | — |

`True` does not mean "the number is wrong"; it means "the sum covers only the
calls that reported real tokens". A NULL count is never read as zero, and one
incomplete call does not erase its siblings' real usage.

The plan fallback is always `partial: False` because it reads a single stored
plan record: there are no sibling rows that could be missing. Reporting `True`
there would imply an incomplete sum that does not exist.

## Tests

`tests/integration/test_ai_usage_helper.py` (new, 6 cases, all direct calls to
the helper):

1. complete rows are summed, `partial: False`
2. a NULL sibling keeps the real sum, `partial: True`
3. all rows NULL -> `None`
4. attempt-bound rows are counted
5. assistant rows bound by `job_id` are counted
6. plan fallback -> `partial: False`

Existing assertions updated to the new shape:
`tests/integration/test_contract_gaps.py::test_ai_usage_reports_recorded_tokens`
(the plan-fallback case) and `docs/controller-integration.md` now documents the
three-key block.

The GUI reads only `input_tokens` / `output_tokens`, so the extra key does not
break rendering. Whether to surface "partial" in the UI is M2's call; this
change does not touch templates.

## Result

`418 passed / 3 skipped / 0 failed` on `integration/live-bridge` at the commit
that carries this change. No binary was executed.
