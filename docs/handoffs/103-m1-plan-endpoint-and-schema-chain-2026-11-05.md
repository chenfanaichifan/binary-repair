# M5 plan contract merged; schema chain compacted to 1..7

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Head before this pass: `0c3708a`
- Suite: `380 passed / 3 skipped / 1 failed` (host has no `readelf`)

## Concurrency note

While this pass was merging `c50ca04`, a second M1 session committed the same
merge plus two follow-ups (`cae7459`, `c07334a`, `9eb33bb`). Its `git add -A`
carried this working tree's changes into `c07334a`, so the endpoint here is the
one written in this pass. Per the operator's decision, this session then took
over and compacted the numbering; the other session stops writing.

Nothing from that session was discarded. `c07334a`'s model_calls correction and
`9eb33bb`'s record 102 remain, and record 102 now carries the compaction note.

## Migrations: the chain is 7, not 6

M5 `0072197` added a fourth migration this branch never had
(`assistant_plan_superseded`), and `c50ca04` moved `assistant_messages` to 007 to
dodge this branch's 006. Merging that verbatim produced

```
002, 003, 004, 006, 007, 008      # version 5 unused
```

which works (`apply_migrations` skips `version <= current`) but leaves seven
files reaching version 8. Compacted to

```
002_ai_tables
003_acceptance_verdict
004_assistant
005_assistant_messages
006_obligation_scope
007_assistant_plan_superseded
```

and `schema_migrations` is `[1, 2, 3, 4, 5, 6, 7]`.

**Schema version 6 was not achievable.** Counting from 3, the merge brings four
migrations, so the ceiling is 7. Reaching 6 would require dropping the
superseded migration, which removes `assistant_plans.superseded_by` and
`model_calls.job_id` / `plan_id` — the columns M2 needs to link a plan to the
row that replaced it. The number in the task was written before `0072197`
existed.

## Regression the merge introduced

M5 changed `generate_plan` to return an `AssistantPlan` instead of a stored
record dict. The existing endpoints passed that object to `_assistant_payload`,
which calls `.get`, so every assistant POST raised `AttributeError`. They now
generate, then read the row back with `get_plan` (rowid DESC) so the response
still carries `id`, `version` and the message link.

M5 also reshaped `AssistantPlan` for the M2 UI: no `schema_version`, and steps
carry `kind`/`prompt` instead of `detail`/`state`. The endpoint assertions follow
the new contract rather than the old shape.

## `POST /api/assistant/plan`

Request: `description`, optional `job_id`, optional `mode`
(`scripted|deterministic|llm`; `scripted` maps to M5's `deterministic`).

Response: `{job_id, persisted, plan, agent}` where `agent` is
`{mode, fallback, fallback_reason, model, tokens}`.

| Case | Behaviour |
|---|---|
| no `job_id` | `deterministic_plan` result, `persisted: false`, nothing written |
| `job_id` | plan stored, `persisted: true`, exactly one `assistant_plans` row |
| no description and no job | 422 |
| `mode=llm` without a client | `fallback: true` with a reason, never a silent pass |
| unknown job | 404 |

`agent.tokens` is M5's `{prompt, completion}`. It is **not** the `ai_usage`
`{input_tokens, output_tokens}` shape used for job calls; the two are different
contracts and are documented as such in the handler.

`test_plan_does_not_touch_a_running_job` holds the line that matters: with a
queued run, generating a plan changes no `contracts`, `runs`, `attempts` or
`obligations` row and no snapshot verdict.

## Unchanged

T6.0 baseline guards stay as listed in record 100; V3's two kinds, the auth
guard and the single data dir are untouched. T8.3 remains blocked and is not
recorded as complete anywhere.
