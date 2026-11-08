# `POST /api/assistant/plan`

Builds an `AssistantPlan` from free text. A plan is advice: this writes at most
one `assistant_plans` row and never touches a contract, run, attempt, obligation
or verdict.

## Request

```json
{ "description": "...", "context": { } }
```

| Field | Required | Meaning |
|---|---|---|
| `description` | yes for a preview | defect text, at most 2000 characters |
| `context` | no | free-form caller state. **Accepted, not read.** The deterministic planner ignores it and a job id makes the plan use the job's stored context, so a caller cannot shift what the plan sees. The field exists so the call shape is stable when the LLM path returns. |
| `job_id` | no | when present the plan is stored against that job |
| `mode` | no | `deterministic` (default), `scripted` (alias), `llm` |

## Responses

```json
200 { "plan": { "plan_id": "...", "mode": "deterministic", "steps": [ ... ] } }
```

```json
503 {
  "plan": null,
  "error": "assistant_unavailable",
  "fallback_reason": "no LLM client is configured on this host"
}
```

The 200 body also carries `job_id`, `persisted` and an `agent` block
(`mode`, `fallback`, `fallback_reason`, `model`, `tokens`) as additive fields.
Clients must read `plan` and ignore the rest.

## Why 503 instead of a fallback flag

`mode: "llm"` means "use the model". When no client is configured there is no
LLM plan, and returning a deterministic one with `fallback: true` makes the
caller believe the model path ran. The two answers are different products, so
they get different status codes.

Omitting `mode` is a valid request for the deterministic planner. It is not a
substitute for the LLM result; it is what the caller asked for.

This is currently the only reachable branch for `mode: "llm"`: nothing on this
host constructs a client (`app/services/assistant.py` states that it never reads
the environment), so `503` is the honest answer until a provider is wired.

## Other status codes

| Code | When |
|---|---|
| 422 | no `description` and no `job_id`, or a blank description, or an unknown `mode` |
| 404 | `job_id` does not exist |
| 400 | the planner rejected its input |
| 500 | the plan was generated but not persisted (a bug, not a client error) |

## Scope note

With a `job_id`, `context` does not override the job's stored context. That is
deliberate: the plan the user sees for a job must reflect the job, not whatever
the caller happened to send.
