# Bounded AI adjudication in the workbench

## Rule

The AI may plan, propose, accept, reject, repair and stop. It may not turn a
failed or incomplete deterministic gate into `success_within_scope`.

This is implemented in `app/services/ai_adjudication.py`:

```text
gate success + AI accept  -> success_within_scope
gate failure + AI accept  -> gate outcome (never promoted)
gate success + AI reject  -> rejected (AI veto)
gate failure + AI reject  -> gate outcome + veto reason
```

The AI's positive decision is necessary for the final success label, but not
sufficient: the deterministic gate remains the evidence authority. The AI has a
one-way veto and can force another repair attempt.

## Runtime guards

- `guard_model_payload()` recursively rejects model-produced `verdict`,
  `outcome`, `evidence`, `obligations`, `checks`, `gate` and `final` fields;
- `GateResult.validate()` rejects a success gate without a complete evidence
  hash and without zero required `not_run`;
- `preflight_key_binding()` fails closed when a custom key file is configured
  but the adapter cannot see the same environment (N-10);
- `supervisor_step()` allows bounded retries but cannot promote a failure.

APIs:

```text
GET  /api/ai/boundary
POST /api/ai/adjudicate
```

`POST /api/ai/adjudicate` is a simulation endpoint; it never calls a model and
does not write a job/evidence record.

## What still requires real infrastructure

- A real guest executor and signed V0–V5 evidence;
- real provider/Windows replay (not fabricated here);
- N-10 environment wiring in the deployed adapter;
- N-11 remaining documentation-to-runtime checks outside this API (the guard
  here is enforced for this workbench's adjudication path).

## Public v1.2.1 review

The public snapshot docs are corrected by
[`artifacts/delivery/public-v1.2.1-docs.patch`](../artifacts/delivery/public-v1.2.1-docs.patch).
It fixes v1.2.0/730/728 drift, records v1.2.1's 741/739 stable run, and adds the
public AI boundary note.
