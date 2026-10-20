# Handoffs: interface confirmation files for teammates

These are "ready to send" confirmation requests derived from the interface contracts in `docs_BinaryRepair/verification-design.md` (§4.1 and §4.3). Goal: the two slices develop in parallel against the same interface instead of guessing.

| File | Recipient | Confirm | Status | Unblocks after confirmation |
|---|---|---|---|---|
| `01-member-1-obligation-interface.md` | Member 1 | §4.1 Obligation / Verdict call interface + owner of `reviewed_scope_sha256` | Confirmed 2026-10-18 (contract in `verification-design.md` §4.1) | Write `app.services.jobs` without guessing the shape; once the module lands, `tests/integration/test_identity_state.py` moves from skip to run |
| `02-member-5-candidate-provider.md` | Member 5 | §4.3 candidate schema, data boundary, provider failure type | Confirmed 2026-10-18 (contract in `verification-design.md` §4.3) | Write `app.domain.candidates` against a clear acceptance standard; once the module lands, `tests/integration/test_ai_boundary.py` moves from skip to run |

## Confirmation log

- 2026-10-18 — Member 5 accepted §4.3 with these details:
  `validate_candidate(payload, allowed_targets=None)`; Route A is 12 top-level
  fields and Route B adds `recovered_function_sha256` and `replacement_c`
  (14 total); the default target allowlist includes `copy_input` and
  `copy_name`; limits are 512 characters per free-text string, 32 entries per
  list, and 20,000 characters for `replacement_c`, with pydantic
  `extra="forbid"`; `validate_candidate_for_context` carries the hash-ownership
  and evidence-signing checks; provider failures are
  `app.services.provider.ProviderFailure(reason: FailureReason)` with
  `TIMEOUT`, `QUOTA`, `BUDGET`, `EMPTY`, `MALFORMED_JSON`, `SCHEMA`.
  Tests for the limits, the Route B shape, the allowlist override, and the
  provider reason enum now live in `tests/integration/test_ai_boundary.py`; they
  stay skipped until the owning modules exist. Member 5's implementation is not
  on `origin` yet.
- 2026-10-18 — Member 5's branch moved everything to the shared root in commit
  `e175436` (`app/domain/candidates.py`, `app/services/provider.py`,
  `binaryrepair_ai/`, `schemas/`). Running the contract suite in an isolated
  worktree of that branch gives **17 passed, 0 skipped, 0 failed**. The
  member-4 branch still skips until the branch is merged. Earlier the code was
  under `route-b/`, which the tests in this repository could not import.
- 2026-10-18 — Member 1 confirmed §4.1 as-is:
  - 4.1.1: four fields are enough; gate id / evidence id / timestamps stay in
    the database row or `detail`.
  - 4.1.2: direct keyword-only call; a thin adapter may only map a job record
    to arguments.
  - 4.1.3: both rows store the scope hash; the **run row is authoritative** and
    the decision reads only it. Contract row is the source at freeze time; run
    creation copies it in the same transaction.
  - 4.1.4: V0–V5 kind names accepted.
  - Member 1 asked whether the hash must come from a canonical serialization.
    Answer: no — the engine treats `reviewed_scope_sha256` as opaque and only
    checks presence, so verification imposes no format. The contract/approval
    layer owns correctness; the engine would not detect a wrong non-empty hash.

## Measured state (2026-10-18)

- `python -m pytest tests/unit -q -p no:cacheprovider` -> **29 passed**
- `python -m pytest tests/integration -q -p no:cacheprovider` on the member-4 branch -> **2 skipped** (`app.services.jobs` and `app.domain.candidates` are not on this branch; skip is not a pass)
- Contract suite against member 5's branch (`e175436`, isolated worktree `var/wt-member5`) -> **17 passed, 0 skipped, 0 failed**

## After a reply arrives

1. Apply the agreed changes to §4.1 / §4.3 of `verification-design.md` and to the corresponding implementation under `app/domain/`.
2. Update the "Status" column above to "confirmed (date)" and record any decision that deviates from the default answer in `MEMORY.md`.
3. Re-run the integration tests once the owning member lands the module and confirm skip becomes run; skip never counts as a pass.
