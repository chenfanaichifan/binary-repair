# Root integration notes (Member 5 slice)

**Status:** 2026-10-20, the Member 5 slice has merged into the shared tree (`member-5/integration`).
**Rule:** the repository root is the only integration point; the old `agent/` snapshot is archived at tag
`archive/2026-10-22/pre-cleanup`, and main no longer contains those copies.

---

## 1. Module map

| Path | Owner | Purpose |
|---|---|---|
| `app/domain/candidates.py` | Member 5 | `validate_candidate` / `validate_candidate_for_context` / `may_leave_host`; the single entry point of the AI boundary |
| `app/domain/contracts.py` | Member 5 + Member 1 | `SecurityContract` and the canonical `sha256()`; does not touch persistence |
| `app/domain/manifests.py` | Member 5 | canonical index and file hashes for `manifest_sha256` |
| `app/services/provider.py` | Member 5 | `DeepSeekProvider`, `ProviderFailure(FailureReason)`, `require_candidate` |
| `app/db/connection.py`, `schema.sql` | Member 1 | v1 baseline (jobs + artifacts); initialized at startup |
| `app/db/migrate.py`, `migrations/002_ai_tables.sql`, `003_acceptance_verdict.sql` | Member 5 + Member 1 | v1 baseline + 002/003; the old 001 is retired, and detecting it is an error |
| `binaryrepair_ai/` | Member 5 | implementation details: client / prompts / pricing / Pydantic schema; outside code must not depend on it directly |
| `schemas/` | Member 5 | candidate/context JSON Schema v1, examples, drift check |
| `routeb/` | Member 5 | Route B synthetic fixture, oracle, Ghidra export, Patcherex2 experiments |
| `tests/test_ai_boundary_contract.py` | Member 5 | 22 AI-boundary contracts |
| `tests/test_provider_failures.py` | Member 5 | 6 kinds of typed failure |
| `tests/test_contracts.py` | Member 5 | SecurityContract v2, capacity fields, hash stability |
| `tests/test_manifests.py` | Member 5 | canonical hash of the manifest index |
| `archive/2026-10-22/pre-cleanup` (tag) | Team | old branch snapshot; check it out only when you need history, it is not maintained in main |

Outside code should only import `app.*`; `binaryrepair_ai.*` is an implementation detail and is not guaranteed stable across refactors.

---

## 2. Call chain (who calls whom)

```text
reviewer fills in the contract
      │  SecurityContract(...)
      ▼
  contract.sha256() ──────────────► stored in contracts.sha256 / run.reviewed_scope_sha256
      │
      ▼
job controller assembles RepairContext
  original_sha256 / contract_sha256 / analysis_sha256
  target_entry / contract_summary / allowed_calls / templates
      │
      ▼
provider.request_candidate(ctx)
      │  CandidateV1 (already past schema/scope) or ProviderFailure
      ▼
validate_candidate_for_context(payload, ctx)
      │  identity, evidence issuance, recovered hash binding
      ▼
verification (Member 4) → decide_attempt_outcome(...)
      │
      ▼
GUI only renders the verdict, it never decides success itself
```

**Hard rule:** the provider only proposes; a candidate must pass `validate_candidate_for_context`; the final conclusion comes only from the acceptance engine.

---

## 3. Contract hash: answering Member 1's open question

`reviewed_scope_sha256` is **opaque** to the acceptance engine (verification-design §4.1),
but the approval layer must be able to reproduce it. The definition given by `app/domain/contracts.py`:

```text
sha256( utf-8( json.dumps(canonical_payload,
                          sort_keys=True,
                          separators=(",", ":"),
                          ensure_ascii=False) ) )
```

- `canonical_payload`: a copy of `to_dict()` with the four list fields sorted first (order carries no semantics);
- text allows only printable ASCII (plus `\n`/`\t`), consistent with the team's "English ASCII in API/exported data" rule;
- same contract, different list order → the same hash;
- any field change → a different hash.

Member 1's usage:

```python
from app.domain.contracts import SecurityContract

contract = SecurityContract.from_dict(reviewed_body)
body_json = json.dumps(contract.to_dict(), ensure_ascii=False)
scope_sha = contract.sha256()          # store in contracts.sha256 and run.reviewed_scope_sha256
```

When loading, this is suggested:

```python
stored = SecurityContract.from_dict(json.loads(row["body_json"]))
assert stored.sha256() == row["sha256"]   # guards against a hand-edited body whose hash was not updated
```

`SecurityContract` does not contain `id` / `job_id` / `approved_at` / `reviewer_label`;
those are persistence fields, carried by Member 1's `contracts` table.

---

## 4. Merge order and current status

| Order | Content | Status |
|---|---|---|
| ① | Member 5: `candidates.py` + `provider.py` + schema + db | ✅ already in main (`1250169`) |
| ② | Member 4: `acceptance.py` + `outcomes.py` + tests | ⏳ waiting for their PR |
| ③ | Member 1: `app/services/jobs.py` + the 002 migration | ⏳ |
| ④ | Member 2: GUI wired to the real controller | ⏳ |
| ⑤ | Member 3: public sample fixture | ⏳ |

When Member 1 adds `app/services/jobs.py`, no module of this slice needs to change; they only need to:

- use `SecurityContract` to generate/verify the hash;
- fill in `contract_summary`, `allowed_calls`, `target_entry` correctly when assembling `RepairContext`;
- call `validate_candidate_for_context` before a candidate is persisted.

---

## 5. Verification commands

```bash
pytest -q                                  # whole repo; currently 149 passed, 2 skipped
pytest -q tests/test_ai_boundary_contract.py tests/test_provider_failures.py
pytest -q tests/test_contracts.py tests/test_db_schema.py
python schemas/generate.py --check
python -c "from app.db.connection import connect; connect('var')"
python scripts/smoke.py --mock             # pipeline self-check without a key
```

Current shared tree: **149 passed, 2 skipped**; `schema up to date (4 files)`.
The 2 skips are V3 runtime tests (they need Linux + a candidate ELF), not passes.
The old 3 identity skips are gone with the controller-v2 merge.

---

## 6. What we do not do

- Do not change code in the old snapshot tag; check out `archive/2026-10-22/pre-cleanup` when you need history.
- Do not let the GUI compute success/failure; it only renders the `Verdict`.
- Do not execute uploaded binaries on the host; execution belongs to the disposable VM + broker (delivered by Member 1).
- Do not put real DeepSeek calls into CI; all provider tests use a fake transport.
- Do not claim Route B has really round-tripped while Member 3's sample is missing; see
  [03-feasibility-checklist.md](03-feasibility-checklist.md).
