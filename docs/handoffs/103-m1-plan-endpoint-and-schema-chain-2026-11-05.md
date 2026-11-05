# M5 plan contract merged; schema chain is [1..8]

- Date: 2026-11-05
- Owner: Member 1 (host backend)
- Base: `0c3708a` + M5 `c50ca04`
- Suite: `400 passed / 3 skipped / 1 failed` (host has no `readelf`)

## Migrations: both numberings kept

The two sides never disagreed about content, only about the slot. This branch
already carried M5's assistant migration as `005_assistant_messages`; M5 then
renamed its copy to `007` to dodge it, and `0072197` added `008` for the plan
superseded link. Keeping both numberings gives

```
002_ai_tables
003_acceptance_verdict
004_assistant
005_assistant_messages          <- this branch, body applied here
006_obligation_scope            <- this branch
007_assistant_messages          <- M5's slot, empty on this branch
008_assistant_plan_superseded   <- M5's new columns
```

and `schema_migrations` is `[1, 2, 3, 4, 5, 6, 7, 8]`.

`005` and `007` were **byte-identical**. Their `ALTER TABLE ... ADD COLUMN`
statements are not idempotent, so running 007's body after 005 fails with
`duplicate column name: version`. 007 is therefore an empty placeholder: it
keeps M5's numbering visible and the chain contiguous without re-running 005.
The placeholder file says so, and says not to move content back into it.

A database that only ever followed M5's numbering (007 applied with its body,
no 005) cannot be migrated by this chain and must be rebuilt. That case did not
exist here; the only databases are this branch's and the test fixtures.

## Regression the merge introduced

M5 changed `generate_plan` to return an `AssistantPlan` instead of a stored
record dict. The existing endpoints passed that object to `_assistant_payload`,
which calls `.get`, so every assistant POST raised `AttributeError`. They now
generate, then read the row back with `get_plan` (rowid DESC), so the response
still carries `id`, `version` and the message link.

M5 also reshaped `AssistantPlan` for the M2 UI: no `schema_version`, and steps
carry `kind`/`prompt` instead of `detail`/`state`. The assertions follow the new
contract.

## `POST /api/assistant/plan`

Request: `description`, optional `job_id`, optional `mode`
(`scripted|deterministic|llm`; `scripted` maps to M5's `deterministic`).

Response: `{job_id, persisted, plan, agent}` where `agent` is
`{mode, fallback, fallback_reason, model, tokens}`.

| Case | Behaviour |
|---|---|
| no `job_id` | `deterministic_plan` result, `persisted: false`, nothing written |
| `job_id` | stored, `persisted: true`, exactly one `assistant_plans` row |
| no description and no job | 422 |
| `mode=llm` without a client | `fallback: true` with a reason, never a silent pass |
| unknown job | 404 |

`agent.tokens` is M5's `{prompt, completion}`, not the `ai_usage`
`{input_tokens, output_tokens}` shape. The two remain separate contracts.

`mode: "llm"` with no client answers `503 {"plan": null, "error":
"assistant_unavailable", "fallback_reason": "..."}`. That is settled, not
provisional: a caller must be able to tell "no plan" from "a deterministic plan
wearing the LLM's clothes". The 200 body still carries `agent`, but clients read
`plan`.

`test_plan_does_not_touch_a_running_job` holds the line that matters: with a
queued run, generating a plan changes no `contracts`, `runs`, `attempts` or
`obligations` row and no snapshot verdict.

## data_dir: the project-root `var/` fallbacks are gone

`assistant_context` already carried `data_dir`, but three call sites still fell
back to a literal `"var"`, which resolves relative to the process cwd — the
repository root under `python -m` and under pytest.

| Site | Before | Now |
|---|---|---|
| `assistant_llm.generate_plan` | `context.get("data_dir") if context else "var"` | raises if the job's `data_dir` is missing |
| `app.db.migrate` CLI | `--db` default `"var"` | defaults to `BINARYREPAIR_DATA_DIR`, errors if neither is set |
| `app.services.worker` CLI | `--data-dir` default `os.environ.get(..., "var")` | same env default, errors if neither is set |

`test_llm_call_without_a_data_dir_writes_nothing` pins the first: an assistant
model call without a `data_dir` raises and writes no `model_calls` row.

## Concurrency note

A second M1 session committed this same merge plus two follow-ups
(`cae7459`, `c07334a`, `9eb33bb`) while this pass was running. Its `add -A`
carried this working tree's changes into `c07334a`. Nothing was discarded: the
model_calls correction, record 102 and the fixture intake tooling all remain.
The operator then put this session in charge of the numbering.

## Shipped

Pushed to `origin/canonical/m1-m5-integration` at `33fc145`; the remote branch
was at `5a13b6b` before, so 23 commits became visible to M4/M5, including
`delivery/` and the assistant interface documents.

GCM was not on PATH: `git` lives at `D:\tools\PortableGit\cmd\git.exe` and the
credential manager at `ucrt64\bin\git-credential-manager.exe` complains
`Failed to locate 'git.exe'` unless that `cmd` directory is prepended. Worth
remembering for any script that pushes from this host.

## Unchanged

T6.0 baseline guards stay as listed in record 100; V3's two kinds, the auth
guard and the single data dir are untouched. T8.3 remains blocked and is not
recorded as complete anywhere.
