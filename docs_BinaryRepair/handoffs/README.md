# Handoffs: interface confirmation files for teammates

These are "ready to send" confirmation requests derived from the interface contracts in `docs_BinaryRepair/verification-design.md` (§4.1 and §4.3). Goal: the two slices develop in parallel against the same interface instead of guessing.

| File | Recipient | Confirm | Status | Unblocks after confirmation |
|---|---|---|---|---|
| `01-member-1-obligation-interface.md` | Member 1 | §4.1 Obligation / Verdict call interface + owner of `reviewed_scope_sha256` | To send | Write `app.services.jobs` without guessing the shape; once the module lands, `tests/integration/test_identity_state.py` moves from skip to run |
| `02-member-5-candidate-provider.md` | Member 5 | §4.3 candidate schema, data boundary, provider failure type | To send | Write `app.domain.candidates` against a clear acceptance standard; once the module lands, `tests/integration/test_ai_boundary.py` moves from skip to run |

## State before sending (measured 2026-10-18)

- `python -m pytest tests/unit -q -p no:cacheprovider` -> **29 passed**
- `python -m pytest tests/integration -q -p no:cacheprovider -rs` -> **2 skipped** (`app.services.jobs` and `app.domain.candidates` do not exist; skip is by design, not a pass)

## After a reply arrives

1. Apply the agreed changes to §4.1 / §4.3 of `verification-design.md` and to the corresponding implementation under `app/domain/`.
2. Update the "Status" column above to "confirmed (date)" and record any decision that deviates from the default answer in `MEMORY.md`.
3. Re-run the integration tests once the owning member lands the module and confirm skip becomes run; skip never counts as a pass.
