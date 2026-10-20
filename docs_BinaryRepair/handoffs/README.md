# Handoffs: interface confirmation files for teammates

These are "ready to send" confirmation requests derived from the interface contracts in `docs_BinaryRepair/verification-design.md` (§4.1, §4.3) and the fixture/VM requirements in `TechDesign-BinaryRepair-MVP.md` (§5, §14). Goal: the slices develop in parallel against the same interface instead of guessing.

| File | Recipient | Confirm | Status | Unblocks after confirmation |
|---|---|---|---|---|
| `01-member-1-obligation-interface.md` | Member 1 | §4.1 Obligation / Verdict call interface + owner of `reviewed_scope_sha256` | Confirmed 2026-10-18 (contract in `verification-design.md` §4.1) | Write `app.services.jobs` without guessing the shape; once the module lands, `tests/integration/test_identity_state.py` moves from skip to run |
| `02-member-5-candidate-provider.md` | Member 5 | §4.3 candidate schema, data boundary, provider failure type | Confirmed 2026-10-18; contract in `verification-design.md` §4.3. Merge deferred: `main` layout is being reorganized by the owner | Implemented on `member-5-deepseek-schema` `ea29e56`: `app/domain/candidates.py`, `app/services/provider.py`, `tests/test_ai_boundary_contract.py` (22 tests) |
| `03-member-3-fixture-vm.md` | Member 3 | §5 fixture profile, frozen test manifest, VM or explicit blocker | To send | A real ELF and frozen input manifest unlock V1–V4 checks; a recorded blocker also unblocks planning |
| `04-member-3-oracle-freeze.md` | Member 3 | §4.4 behavioural oracle: `DEST_CAPACITY`, measured original behaviour, exact `ERROR_STDERR`, harness call shape | To send (blocking the fixture freeze) | Freezing the oracle lets Route A and Route B implement one shared V3 assertion set |

## Confirmation log

- 2026-10-20 — Duplicate AI-boundary tests are settled as **deleted, not
  restored from git history**. Member 5 migrated the four boundary assertions
  that were unique to the member-4 suite (512 accepted / 513 rejected, 33-entry
  list rejected, 20,001-char `replacement_c` rejected, `allowed_targets`
  override) into `tests/test_ai_boundary_contract.py`; it now has 22 tests and
  the full branch suite reports 107 passed on `ea29e56`. Drift is prevented by
  the generated schema (`schemas/generated/candidate.v1.json`) plus
  `python schemas/generate.py --check`, not by keeping a second assertion copy.
  `main` is being reorganized by the owner (only `agent/`, `run.bat`,
  `start.ps1` remained at the time of writing), so the acceptance engine is not
  merged there until the layout is confirmed.
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
  provider reason enum now live in `tests/test_ai_boundary_contract.py`; provider
  failures are covered by `tests/test_provider.py`. The member-4 skeleton
  `tests/integration/test_ai_boundary.py` was removed on 2026-10-20 as
  superseded.
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

## Measured state (2026-10-20)

- `python -m pytest tests -q -p no:cacheprovider` on the member-4 branch -> **40 passed, 1 skipped** (the skip is the identity/state suite without `app.services.jobs`; skip is not a pass)
- Member 5's branch `ea29e56` -> `tests/test_ai_boundary_contract.py` has **22 tests**; the full branch suite is reported at **107 passed** (reported by member 5, not independently re-run here: remote fetch from this sandbox fails on a TLS CA-bundle path error)
- The stale `var/wt-member5` worktree from 2026-10-18 was removed on 2026-10-20 so it no longer breaks pytest collection

## After a reply arrives

1. Apply the agreed changes to §4.1 / §4.3 of `verification-design.md` and to the corresponding implementation under `app/domain/`.
2. Update the "Status" column above to "confirmed (date)" and record any decision that deviates from the default answer in `MEMORY.md`.
3. Re-run the integration tests once the owning member lands the module and confirm skip becomes run; skip never counts as a pass.
