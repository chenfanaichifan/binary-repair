# Schema changelog

Only **contract-layer** changes are recorded here; for database changes see `db/migrations/`.

## v1 — 2026-10-18

The first frozen candidate contract.

**Aligned with the verification skeleton the same day (`verification-design` §4.3):**

- the JSON value of `route` changed to `route_a` / `route_b` (consistent with `tests/integration/test_ai_boundary.py`);
  "Route A/B" in the documents is narrative only and no longer appears in the data.
- free-text limits: 512 characters per entry, 32 entries per list; instruction-like text (ignore previous / run: / rm -rf / URL)
  rejects the whole document.
- new public entry points in `app.domain.candidates`: `validate_candidate(payload)`,
  `may_leave_host(classification, derived=False)`, returning `CandidateV1` and raising `CandidateRejected` on failure.
- new `app.services.provider.ProviderFailure(FailureReason)`, mapping the four failure classes timeout / quota / empty /
  malformed JSON.

- `candidate.v1.json`: the closed object for Route A (`template_id` + `parameters`) and Route B
  (`recovered_function_sha256` + `replacement_c`), with `additionalProperties: false`.
- `context.v1.json`: the context the server is allowed to send (identity triple, contract excerpt, closed template set,
  recovered function, call allowlist).
- semantic rules (Pydantic + `check_candidate`): identity hashes must match; `target_entry` must be in scope;
  `evidence_ids` must come from the server; Route A parameters must match the template exactly and be within range;
  Route B must define the target function, must not use constructs such as `#include`/`asm`/`system`, and may call only allowlisted functions.
- explicitly out of scope: JSON Schema does not express cross-field route rules (Pydantic owns that), nor does it promise that the model will comply.

Author: Role 5 (AI / Route B / schema)
Reviewers: GUI (member 2), verification (member 4) — pending sign-off
