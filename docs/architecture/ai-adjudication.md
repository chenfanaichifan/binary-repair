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

In the policy simulation below an AI `accept` is necessary for the joint success
label. In the real direct-ELF review path (§ after the API list) the review is
opt-in: the deterministic gate alone can succeed, but an AI `hold` can still
veto and an AI `accept` can never promote a failed or incomplete gate. The AI
has a one-way veto; it never owns the acceptance decision.

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

## Direct ELF review path (real provider)

The direct ELF repair route has a separate, review-only path:

```text
POST /api/binary/repair-review   multipart: binary, csrf, ai_review=0|1
GET  /api/binary/review-contract
```

The flow is:

```text
repair_elf
  -> build_verification(): checks, report_sha256, GateResult
  -> optional review_verification(): model sees the same packet a human sees
  -> decide(): deterministic gate + review
```

### Packet the model sees

`app/services/binary_verification.py` emits the same JSON packet the UI renders:

- `scope` — format, arch, mode, strategy, capacity, strict, claim, statement;
- `candidate` — original/patched hashes, size, unchanged flag;
- `patch` — reviewed offsets/findings or strict-template hash;
- `runtime` — Unicorn cases and availability;
- `checks` — `format`, `candidate.*`, `patch.scope`, `runtime.*`, and strict-only
  `strict.reviewed_template` / `runtime.boundary_semantics`;
- `missing` — required checks that did not pass;
- `limitations`;
- `report_sha256` — a stable hash of the packet body;
- `gate` — the outcome produced by the existing
  `app.domain.acceptance.decide_attempt_outcome()` rules.

Success requires every required check to pass and a complete evidence hash. A
missing runtime case is `not_run` → `inconclusive`; an actual sentinel/identity
failure is `rejected`; a non-ELF or unsupported pattern is `unsupported`.

### Review contract

The model returns only:

```json
{
  "recommendation": "accept | hold | needs_more_checks",
  "summary": "...",
  "concerns": [{"check_id": "...", "why": "..."}],
  "missing_evidence": ["..."],
  "further_checks": ["..."]
}
```

`app/domain/binary_review.py` uses `extra="forbid"`, bounded lengths and
`guard_model_payload()`; check references must resolve to the packet (or the
virtual `scope` id). The model never sees raw binary bytes, source, file paths or
provider keys. `app/services/model_calls.py` records `route="binary_review"` rows
for real provider attempts: status, model, tokens, latency and request id. The
prompt/response content is not stored in the audit row.

### Decision table

```text
gate success + AI accept          -> success_within_scope  (authority: deterministic gate)
gate success + AI hold/reject     -> rejected              (authority: AI veto)
gate success + needs_more_checks  -> inconclusive          (authority: AI more checks)
gate failure + AI accept          -> gate outcome, false   (accept cannot promote)
gate failure + AI hold            -> gate outcome, false
review unavailable / invalid      -> gate outcome         (AI status is explicit)
review not requested              -> gate outcome
```

A scripted reviewer used by tests/demos is marked `mode="scripted"`,
`called=false`, and is never presented as AI evidence.

### API/UI

`POST /api/binary/repair-review` returns 200 for a valid upload even when the
gate is non-successful; the body's `ok`, `decision`, `verification` and `review`
carry the truth. `patched_base64` is included only when `decision.success` is
true. The legacy `POST /api/binary/quick-repair` now fails closed when
verification does not pass, so it cannot hand back a candidate with missing
evidence.

The workbench checkbox is opt-in, explains that the structured report is sent
to the configured provider, and states that AI is review-only.

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
